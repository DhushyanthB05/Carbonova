"""
Tests for Carbon Data Provider integration and injection mechanism:
- Verifies synthetic provider remains the default.
- Verifies type validation on provider registration.
- Verifies custom provider injection via set_carbon_provider / reset_carbon_provider.
- Verifies GET /api/carbon and POST /api/schedule/run obtain data through the registered provider.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.storage import (
    InMemoryStore,
    get_carbon_provider,
    reset_carbon_provider,
    set_carbon_provider,
    store,
)
from backend.carbon.interface import (
    CarbonDataProvider,
    CarbonForecastPoint,
    CarbonGrid,
)
from backend.carbon.synthetic import SyntheticCarbonDataProvider
from backend.scheduler.models import FeasibilityStatus, Job
from backend.scheduler.time_grid import align_to_next_slot, align_to_prev_slot

client = TestClient(app)


class MockMember1CarbonProvider(CarbonDataProvider):
    """
    Mock implementation adhering strictly to Member 1's CarbonDataProvider interface.
    Emits custom values with provenance 'MOCK_MEMBER_1_GRID'.
    """

    def __init__(self, fixed_intensity: float = 77.0, provenance: str = "MOCK_MEMBER_1_GRID") -> None:
        self.fixed_intensity = fixed_intensity
        self.provenance = provenance
        self.call_count = 0

    def get_carbon_grid(
        self,
        start_time: datetime,
        end_time: datetime,
        time_step_minutes: int = 60,
    ) -> CarbonGrid:
        self.call_count += 1
        start_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        end_utc = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)
        start_aligned = align_to_prev_slot(start_utc, time_step_minutes)
        end_aligned = align_to_next_slot(end_utc, time_step_minutes)
        if start_aligned >= end_aligned:
            end_aligned = start_aligned + timedelta(minutes=time_step_minutes)

        step = timedelta(minutes=time_step_minutes)
        points: List[CarbonForecastPoint] = []
        current = start_aligned
        while current < end_aligned:
            points.append(
                CarbonForecastPoint(
                    timestamp=current,
                    predicted_carbon_intensity=self.fixed_intensity,
                    slot_specific_uncertainty=5.0,
                    realized_carbon_intensity=self.fixed_intensity,
                    lower_bound_ci=max(0.0, self.fixed_intensity - 10.0),
                    upper_bound_ci=self.fixed_intensity + 10.0,
                    provenance=self.provenance,
                )
            )
            current += step

        return CarbonGrid(points, time_step_minutes=time_step_minutes)


@pytest.fixture(autouse=True)
def reset_provider_and_store():
    store.clear_jobs()
    reset_carbon_provider()
    yield
    store.clear_jobs()
    reset_carbon_provider()


def test_default_provider_is_synthetic():
    provider = get_carbon_provider()
    assert isinstance(provider, SyntheticCarbonDataProvider)
    assert isinstance(store.get_carbon_provider(), SyntheticCarbonDataProvider)

    grid = store.get_default_carbon_grid()
    assert len(grid.points) > 0
    assert all(p.provenance == "SYNTHETIC" for p in grid.points)


def test_set_carbon_provider_type_validation():
    class InvalidProvider:
        pass

    with pytest.raises(TypeError) as exc_info:
        set_carbon_provider(InvalidProvider())  # type: ignore
    assert "CarbonDataProvider" in str(exc_info.value)

    with pytest.raises(TypeError):
        store.set_carbon_provider("not-a-provider")  # type: ignore


def test_provider_injection_and_grid_query():
    mock_provider = MockMember1CarbonProvider(fixed_intensity=99.5, provenance="TEST_CUSTOM_FEED")
    set_carbon_provider(mock_provider)

    active = get_carbon_provider()
    assert active is mock_provider
    assert store.get_carbon_provider() is mock_provider

    base_time = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    grid = store.get_default_carbon_grid(
        start_time=base_time,
        end_time=base_time + timedelta(hours=3),
        time_step_minutes=60,
    )
    assert mock_provider.call_count == 1
    assert len(grid.points) == 3
    for pt in grid.points:
        assert pt.predicted_carbon_intensity == 99.5
        assert pt.provenance == "TEST_CUSTOM_FEED"


def test_api_carbon_endpoint_with_injected_provider():
    mock_provider = MockMember1CarbonProvider(fixed_intensity=123.4, provenance="LIVE_FEED_MEMBER_1")
    set_carbon_provider(mock_provider)

    res = client.get("/api/carbon?time_step_minutes=60")
    assert res.status_code == 200
    points = res.json()
    assert len(points) > 0
    assert all(p["provenance"] == "LIVE_FEED_MEMBER_1" for p in points)
    assert all(p["predicted_carbon_intensity"] == 123.4 for p in points)


def test_api_scheduling_with_injected_provider():
    # Configure custom provider where slot 1 has lower carbon than slot 0
    # Generates a grid respecting the requested time range and discrete slot boundaries
    class DynamicMockProvider(CarbonDataProvider):
        def get_carbon_grid(self, start_time: datetime, end_time: datetime, time_step_minutes: int = 60) -> CarbonGrid:
            start_utc = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
            end_utc = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)
            start_aligned = align_to_prev_slot(start_utc, time_step_minutes)
            end_aligned = align_to_next_slot(end_utc, time_step_minutes)
            if start_aligned >= end_aligned:
                end_aligned = start_aligned + timedelta(minutes=time_step_minutes)

            step = timedelta(minutes=time_step_minutes)
            pts: List[CarbonForecastPoint] = []
            current = start_aligned
            slot_idx = 0
            while current < end_aligned:
                # Slot 1 is the green dip (100.0 gCO2eq/kWh), slot 0 is 300.0, other slots are 250.0
                if slot_idx == 1:
                    ci = 100.0
                elif slot_idx == 0:
                    ci = 300.0
                else:
                    ci = 250.0

                pts.append(
                    CarbonForecastPoint(
                        timestamp=current,
                        predicted_carbon_intensity=ci,
                        slot_specific_uncertainty=2.0,
                        realized_carbon_intensity=ci,
                        lower_bound_ci=max(0.0, ci - 10.0),
                        upper_bound_ci=ci + 10.0,
                        provenance="MEMBER_1_DYNAMIC",
                    )
                )
                current += step
                slot_idx += 1

            return CarbonGrid(pts, time_step_minutes=time_step_minutes)

    set_carbon_provider(DynamicMockProvider())

    t0 = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    job_payload = [
        {
            "job_id": "job-dyn-1",
            "arrival_time": t0.isoformat(),
            "deadline": (t0 + timedelta(hours=3)).isoformat(),
            "duration_minutes": 60,
            "energy_kwh": 5.0,
            "deferrable": True,
            "resource_requirement": 1.0,
        }
    ]

    client.post("/api/jobs", json=job_payload)
    res = client.post("/api/schedule/run", json={"run_all_policies": True})
    assert res.status_code == 200
    data = res.json()

    # Carbonova and Naive Green should delay to t1 (13:00) because 100.0 < 300.0
    naive_dec = data["results"]["naive_green"]["decisions"][0]
    carb_dec = data["results"]["carbonova"]["decisions"][0]

    assert naive_dec["feasibility_status"] == FeasibilityStatus.SCHEDULED.value
    assert naive_dec["scheduled_start"] in ["2026-10-26T13:00:00Z", "2026-10-26T13:00:00+00:00"]
    assert naive_dec["predicted_carbon_intensity"] == 100.0

    assert carb_dec["feasibility_status"] == FeasibilityStatus.SCHEDULED.value
    assert carb_dec["scheduled_start"] in ["2026-10-26T13:00:00Z", "2026-10-26T13:00:00+00:00"]
    assert carb_dec["predicted_carbon_intensity"] == 100.0


def test_store_init_with_explicit_provider():
    custom_prov = MockMember1CarbonProvider()
    store_custom = InMemoryStore(carbon_provider=custom_prov)
    assert store_custom.get_carbon_provider() is custom_prov

    store_default = InMemoryStore(carbon_provider=None)
    assert isinstance(store_default.get_carbon_provider(), SyntheticCarbonDataProvider)

    with pytest.raises(TypeError):
        InMemoryStore(carbon_provider="invalid")  # type: ignore


def test_reset_carbon_provider():
    custom_prov = MockMember1CarbonProvider(provenance="TEMP")
    set_carbon_provider(custom_prov)
    assert get_carbon_provider() is custom_prov

    reset_carbon_provider()
    active = get_carbon_provider()
    assert isinstance(active, SyntheticCarbonDataProvider)

    grid = store.get_default_carbon_grid()
    assert all(p.provenance == "SYNTHETIC" for p in grid.points)
