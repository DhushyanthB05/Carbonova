"""
Unit and Integration Tests for NESORealTraceCarbonDataProvider:
- Trace loading, validation, and metadata extraction
- Native 30-minute settlement period resolution
- Aggregated 60-minute hourly resolution (arithmetic mean of constituent half-hours)
- Error handling on unsupported resolutions and out-of-range dates
- Forecast isolation: predicted vs realized values
- Full end-to-end multi-policy scheduling with real NESO data
- API integration through the provider-injection mechanism
"""

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.storage import (
    get_carbon_provider,
    reset_carbon_provider,
    set_carbon_provider,
    store,
)
from backend.carbon.neso_provider import NESORealTraceCarbonDataProvider
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
    MarginUnit,
    PolicyType,
    SchedulerConfig,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_env():
    store.clear_jobs()
    reset_carbon_provider()
    yield
    store.clear_jobs()
    reset_carbon_provider()


def test_neso_provider_initialization():
    provider = NESORealTraceCarbonDataProvider()
    assert provider.min_timestamp <= datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert provider.max_timestamp >= datetime(2024, 12, 31, 23, 0, tzinfo=timezone.utc)


def test_neso_provider_30min_native_grid():
    provider = NESORealTraceCarbonDataProvider()
    start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 13, 0, tzinfo=timezone.utc)

    # 3 hours at 30-min resolution = 6 slots
    grid = provider.get_carbon_grid(start, end, time_step_minutes=30)
    assert grid.time_step_minutes == 30
    assert len(grid.points) == 6

    for p in grid.points:
        assert p.provenance == "NESO_Great_Britain_Carbon_Intensity"
        assert p.predicted_carbon_intensity > 0.0
        assert p.realized_carbon_intensity is not None
        assert p.realized_carbon_intensity > 0.0
        assert p.slot_specific_uncertainty > 0.0
        assert p.lower_bound_ci is not None and p.upper_bound_ci is not None
        assert p.lower_bound_ci <= p.upper_bound_ci
        # Check uncertainty matches half-width
        half_width = round((p.upper_bound_ci - p.lower_bound_ci) / 2.0, 2)
        assert abs(p.slot_specific_uncertainty - half_width) <= 0.05


def test_neso_provider_60min_aggregated_grid():
    provider = NESORealTraceCarbonDataProvider()
    start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 13, 0, tzinfo=timezone.utc)

    # 3 hours at 60-min resolution = 3 slots
    grid_60 = provider.get_carbon_grid(start, end, time_step_minutes=60)
    assert grid_60.time_step_minutes == 60
    assert len(grid_60.points) == 3

    # Compare against native 30min grid to verify aggregation rule
    grid_30 = provider.get_carbon_grid(start, end, time_step_minutes=30)
    p30 = {p.timestamp: p for p in grid_30.points}

    for p60 in grid_60.points:
        t0 = p60.timestamp
        t1 = t0 + timedelta(minutes=30)
        expected_pred = round((p30[t0].predicted_carbon_intensity + p30[t1].predicted_carbon_intensity) / 2.0, 2)
        expected_real = round((p30[t0].realized_carbon_intensity + p30[t1].realized_carbon_intensity) / 2.0, 2)

        assert abs(p60.predicted_carbon_intensity - expected_pred) <= 0.02
        assert abs(p60.realized_carbon_intensity - expected_real) <= 0.02
        assert p60.metadata.get("aggregation_rule") == "two_half_hour_settlement_period_mean"


def test_neso_provider_diurnal_uncertainty_variation():
    """
    Verifies that uncertainty_mode='diurnal' (default) assigns slot-specific
    conformal quantiles that vary by time-of-day across the 4 calibrated regimes:
    night_baseload (11.28), morning_ramp (9.32), afternoon_solar (8.28), evening_peak (10.46).
    """
    provider = NESORealTraceCarbonDataProvider(uncertainty_mode="diurnal")
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 2, 0, 0, tzinfo=timezone.utc)
    grid = provider.get_carbon_grid(start, end, time_step_minutes=30)

    assert len(grid.points) == 48
    uncertainties = [p.slot_specific_uncertainty for p in grid.points]
    unique_unc = set(uncertainties)
    assert len(unique_unc) == 4
    assert min(uncertainties) == pytest.approx(8.2760, abs=1e-3)
    assert max(uncertainties) == pytest.approx(11.2830, abs=1e-3)

    # Check regimes in metadata
    regimes = {p.metadata["diurnal_regime"] for p in grid.points}
    assert regimes == {"night_baseload", "morning_ramp", "afternoon_solar", "evening_peak"}


def test_neso_provider_global_uncertainty_mode():
    """
    Verifies that uncertainty_mode='global' applies the single global conformal
    quantile (9.7424 gCO2/kWh) uniformly across all slots.
    """
    provider = NESORealTraceCarbonDataProvider(uncertainty_mode="global")
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 2, 0, 0, tzinfo=timezone.utc)
    grid = provider.get_carbon_grid(start, end, time_step_minutes=30)

    assert len(grid.points) == 48
    uncertainties = [p.slot_specific_uncertainty for p in grid.points]
    assert len(set(uncertainties)) == 1
    assert uncertainties[0] == pytest.approx(9.7424, abs=1e-3)


def test_neso_provider_invalid_uncertainty_mode_raises():
    with pytest.raises(ValueError) as exc_info:
        NESORealTraceCarbonDataProvider(uncertainty_mode="unsupported_mode")
    assert "Invalid uncertainty_mode" in str(exc_info.value)


def test_neso_provider_unsupported_resolution_raises():
    provider = NESORealTraceCarbonDataProvider()
    start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 13, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError) as exc_info:
        provider.get_carbon_grid(start, end, time_step_minutes=15)
    assert "Unsupported time_step_minutes" in str(exc_info.value)


def test_neso_provider_out_of_range_raises():
    provider = NESORealTraceCarbonDataProvider()
    start = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2020, 1, 1, 13, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError) as exc_info:
        provider.get_carbon_grid(start, end, time_step_minutes=60)
    assert "out of range" in str(exc_info.value).lower()


def test_neso_scheduling_engine_all_four_policies():
    """
    Executes SchedulingEngine.run_all_policies on a real Great Britain NESO 2024 trace:
    - Tests FIFO, Naive-Green, Carbonova, and Oracle on identical workload.
    - Verifies forecast isolation (online policies use predicted, Oracle uses realized).
    - Verifies comparative metrics, baseline reduction, and oracle gap.
    """
    provider = NESORealTraceCarbonDataProvider()
    start_time = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    end_time = datetime(2024, 6, 1, 18, 0, tzinfo=timezone.utc)

    grid = provider.get_carbon_grid(start_time, end_time, time_step_minutes=60)

    jobs = [
        Job(
            job_id="neso-job-1",
            arrival_time=start_time,
            deadline=start_time + timedelta(hours=4),
            duration_minutes=60,
            energy_kwh=10.0,
            deferrable=False,  # Non-deferrable -> must execute at earliest (10:00)
            resource_requirement=1.0,
        ),
        Job(
            job_id="neso-job-2",
            arrival_time=start_time,
            deadline=start_time + timedelta(hours=6),
            duration_minutes=60,
            energy_kwh=15.0,
            deferrable=True,
            resource_requirement=2.0,
        ),
        Job(
            job_id="neso-job-3",
            arrival_time=start_time,
            deadline=start_time + timedelta(hours=8),
            duration_minutes=120,
            energy_kwh=20.0,
            deferrable=True,
            resource_requirement=1.0,
        ),
    ]

    config = SchedulerConfig(
        risk_lambda=0.5,
        min_improvement_margin=0.05,
        cluster=ClusterConfig(total_capacity=4.0, time_step_minutes=60),
    )

    response = SchedulingEngine.run_all_policies(jobs, grid, config)

    # 1. Verify all 4 policies are present
    assert "fifo" in response.results
    assert "naive_green" in response.results
    assert "carbonova" in response.results
    assert "oracle" in response.results

    # 2. Non-deferrable job-1 must execute at 10:00 across all policies
    for pol_key, pol_res in response.results.items():
        d_map = {d.job_id: d for d in pol_res.decisions}
        assert d_map["neso-job-1"].feasibility_status == FeasibilityStatus.SCHEDULED
        assert d_map["neso-job-1"].scheduled_start == start_time
        assert d_map["neso-job-2"].feasibility_status == FeasibilityStatus.SCHEDULED
        assert d_map["neso-job-3"].feasibility_status == FeasibilityStatus.SCHEDULED

    # 3. Check metrics
    fifo_metrics = response.results["fifo"].metrics
    carb_metrics = response.results["carbonova"].metrics
    oracle_metrics = response.results["oracle"].metrics

    assert fifo_metrics["scheduled_jobs_count"] == 3
    assert fifo_metrics["total_realized_emissions_gco2"] > 0.0
    assert carb_metrics["total_realized_emissions_gco2"] > 0.0
    assert oracle_metrics["total_realized_emissions_gco2"] > 0.0

    # Comparative summary checks
    summary = response.comparative_summary
    assert "realized_emissions_gco2" in summary
    assert "emissions_reduction_vs_fifo_pct" in summary
    assert "oracle_gap_pct" in summary


def test_api_with_neso_provider_via_injection():
    """
    Verifies that injecting NESORealTraceCarbonDataProvider into the store:
    1. Directs GET /api/carbon to return real NESO trace points with NESO provenance.
    2. Directs POST /api/schedule/run to execute scheduling against the real NESO trace.
    """
    neso_provider = NESORealTraceCarbonDataProvider()
    set_carbon_provider(neso_provider)
    assert get_carbon_provider() is neso_provider

    # 1. Test GET /api/carbon
    res_carbon = client.get(
        "/api/carbon?start_time=2024-06-01T00:00:00Z&end_time=2024-06-01T06:00:00Z&time_step_minutes=60"
    )
    assert res_carbon.status_code == 200
    points = res_carbon.json()
    assert len(points) == 6
    assert all(p["provenance"] == "NESO_Great_Britain_Carbon_Intensity" for p in points)

    # 2. Test POST /api/jobs and POST /api/schedule/run
    t0 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    job_payload = [
        {
            "job_id": "neso-api-1",
            "arrival_time": t0.isoformat(),
            "deadline": (t0 + timedelta(hours=4)).isoformat(),
            "duration_minutes": 60,
            "energy_kwh": 8.0,
            "deferrable": True,
            "resource_requirement": 1.0,
        }
    ]

    sub_res = client.post("/api/jobs", json=job_payload)
    assert sub_res.status_code == 200

    run_res = client.post("/api/schedule/run", json={"run_all_policies": True})
    assert run_res.status_code == 200
    data = run_res.json()

    decisions = data["results"]["carbonova"]["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["feasibility_status"] == FeasibilityStatus.SCHEDULED.value
    assert decisions[0]["predicted_carbon_intensity"] > 0.0

    # 3. Reset provider restores synthetic
    reset_carbon_provider()
    assert get_carbon_provider() is not neso_provider


def test_neso_provider_regime_transition_boundaries():
    """
    Verifies that the diurnal regime boundaries are assigned strictly according
    to the 30-minute settlement period definitions:
      - Period 13 (06:00 UTC) -> night_baseload (11.2830)
      - Period 14 (06:30 UTC) -> morning_ramp (9.3182)
      - Period 23 (11:00 UTC) -> morning_ramp (9.3182)
      - Period 24 (11:30 UTC) -> afternoon_solar (8.2760)
      - Period 33 (16:00 UTC) -> afternoon_solar (8.2760)
      - Period 34 (16:30 UTC) -> evening_peak (10.4554)
    """
    provider = NESORealTraceCarbonDataProvider(uncertainty_mode="diurnal")
    start = datetime(2024, 6, 1, 5, 30, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 17, 30, tzinfo=timezone.utc)
    grid = provider.get_carbon_grid(start, end, time_step_minutes=30)
    p_map = {p.timestamp: p for p in grid.points}

    t_0600 = datetime(2024, 6, 1, 6, 0, tzinfo=timezone.utc)
    t_0630 = datetime(2024, 6, 1, 6, 30, tzinfo=timezone.utc)
    assert p_map[t_0600].metadata["diurnal_regime"] == "night_baseload"
    assert p_map[t_0600].slot_specific_uncertainty == pytest.approx(11.2830, abs=1e-3)
    assert p_map[t_0630].metadata["diurnal_regime"] == "morning_ramp"
    assert p_map[t_0630].slot_specific_uncertainty == pytest.approx(9.3182, abs=1e-3)

    t_1100 = datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc)
    t_1130 = datetime(2024, 6, 1, 11, 30, tzinfo=timezone.utc)
    assert p_map[t_1100].metadata["diurnal_regime"] == "morning_ramp"
    assert p_map[t_1100].slot_specific_uncertainty == pytest.approx(9.3182, abs=1e-3)
    assert p_map[t_1130].metadata["diurnal_regime"] == "afternoon_solar"
    assert p_map[t_1130].slot_specific_uncertainty == pytest.approx(8.2760, abs=1e-3)

    t_1600 = datetime(2024, 6, 1, 16, 0, tzinfo=timezone.utc)
    t_1630 = datetime(2024, 6, 1, 16, 30, tzinfo=timezone.utc)
    assert p_map[t_1600].metadata["diurnal_regime"] == "afternoon_solar"
    assert p_map[t_1600].slot_specific_uncertainty == pytest.approx(8.2760, abs=1e-3)
    assert p_map[t_1630].metadata["diurnal_regime"] == "evening_peak"
    assert p_map[t_1630].slot_specific_uncertainty == pytest.approx(10.4554, abs=1e-3)


def test_neso_provider_hourly_aggregation_metadata():
    """
    Verifies that 30-min native slots are marked as formal split-conformal intervals,
    while 60-min aggregated slots are explicitly labeled as conservative heuristic risk scores.
    """
    provider = NESORealTraceCarbonDataProvider(uncertainty_mode="diurnal")
    start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

    grid_30 = provider.get_carbon_grid(start, end, time_step_minutes=30)
    for p in grid_30.points:
        assert p.metadata["formal_conformal_calibrated"] is True
        assert "split_conformal" in p.metadata["uncertainty_type"]

    grid_60 = provider.get_carbon_grid(start, end, time_step_minutes=60)
    for p in grid_60.points:
        assert p.metadata["formal_conformal_calibrated"] is False
        assert p.metadata["uncertainty_type"] == "conservative_heuristic_risk_score"
        assert "calibration_note" in p.metadata


def test_policy_divergence_historical_neso_backfire_averted_by_carbonova():
    """
    Verifies meaningful policy divergence on historical NESO 2024-01-04 data:
    - Job arrives at 02:00, deadline 14:00 (60 min duration, 10 kWh).
    - At 02:00: Pred=91.22, Real=88.50.
    - At 03:00: Pred=89.44, Real=93.00.
    - Naive-Green delays to 03:00 chasing a 2.0% lower predicted intensity -> BACKFIRES (emissions: 930 gCO2 vs 885 gCO2).
    - Carbonova margin check (5.0% threshold) rejects the 1.8% risk reduction -> Schedules at 02:00, averting the backfire.
    - FIFO schedules at 02:00 (885 gCO2).
    - Oracle schedules at 02:00 (885 gCO2).
    """
    provider = NESORealTraceCarbonDataProvider(uncertainty_mode="diurnal")
    start_time = datetime(2024, 1, 4, 0, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=24)
    grid = provider.get_carbon_grid(start_time, end_time, time_step_minutes=60)

    job = Job(
        job_id="jan-04-job-1",
        arrival_time=start_time + timedelta(hours=2),
        deadline=start_time + timedelta(hours=14),
        duration_minutes=60,
        energy_kwh=10.0,
        deferrable=True,
        resource_requirement=1.0,
    )

    config = SchedulerConfig(
        risk_lambda=0.5,
        min_improvement_margin=0.05,
        margin_unit=MarginUnit.RELATIVE_PERCENTAGE,
        cluster=ClusterConfig(total_capacity=4.0, time_step_minutes=60),
    )

    response = SchedulingEngine.run_all_policies([job], grid, config)

    fifo_res = response.results["fifo"]
    naive_res = response.results["naive_green"]
    carb_res = response.results["carbonova"]
    oracle_res = response.results["oracle"]

    # 1. Verify scheduled start times
    assert fifo_res.decisions[0].scheduled_start == start_time + timedelta(hours=2)
    assert naive_res.decisions[0].scheduled_start == start_time + timedelta(hours=3)  # Delayed
    assert carb_res.decisions[0].scheduled_start == start_time + timedelta(hours=2)   # Protected by margin
    assert oracle_res.decisions[0].scheduled_start == start_time + timedelta(hours=2) # True minimum

    # 2. Verify emissions and backfire divergence
    fifo_em = fifo_res.metrics["total_realized_emissions_gco2"]
    naive_em = naive_res.metrics["total_realized_emissions_gco2"]
    carb_em = carb_res.metrics["total_realized_emissions_gco2"]
    oracle_em = oracle_res.metrics["total_realized_emissions_gco2"]

    assert naive_em > fifo_em, "Naive-Green must backfire on this historical window"
    assert carb_em == fifo_em == oracle_em == 885.0
    assert naive_em == 930.0

    # 3. Check backfire metric status
    assert naive_res.metrics["backfire_jobs_count"] == 1
    assert carb_res.metrics["backfire_jobs_count"] == 0
    assert "below 5.0% margin" in carb_res.decisions[0].reason


def test_policy_divergence_deterministic_four_policy_split():
    """
    Deterministic controlled grid test where all four policies diverge onto distinct decision paths:
      - Slot 0 (10:00, Earliest): Pred=100.0, Unc=10.0, Real=100.0 (Risk=105.0 with lambda=0.5)
      - Slot 1 (11:00): Pred=92.0, Unc=30.0, Real=125.0 (Risk=107.0) -> Naive-Green trap (Backfire)
      - Slot 2 (12:00): Pred=98.0, Unc=8.0, Real=70.0 (Risk=102.0) -> Margin blocks Carbonova (2.86% < 5%), Oracle picks it
    """
    from backend.carbon.interface import CarbonForecastPoint, CarbonGrid

    t0 = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

    points = [
        CarbonForecastPoint(
            timestamp=t0,
            predicted_carbon_intensity=100.0,
            slot_specific_uncertainty=10.0,
            realized_carbon_intensity=100.0,
        ),
        CarbonForecastPoint(
            timestamp=t1,
            predicted_carbon_intensity=92.0,
            slot_specific_uncertainty=30.0,  # High risk penalty
            realized_carbon_intensity=125.0, # Realized error spike
        ),
        CarbonForecastPoint(
            timestamp=t2,
            predicted_carbon_intensity=98.0,
            slot_specific_uncertainty=8.0,
            realized_carbon_intensity=70.0,  # True low carbon
        ),
    ]
    grid = CarbonGrid(points, time_step_minutes=60)

    job = Job(
        job_id="divergence-job-1",
        arrival_time=t0,
        deadline=t2 + timedelta(hours=1),
        duration_minutes=60,
        energy_kwh=10.0,
        deferrable=True,
        resource_requirement=1.0,
    )

    config = SchedulerConfig(
        risk_lambda=0.5,
        min_improvement_margin=0.05,
        margin_unit=MarginUnit.RELATIVE_PERCENTAGE,
        cluster=ClusterConfig(total_capacity=4.0, time_step_minutes=60),
    )

    response = SchedulingEngine.run_all_policies([job], grid, config)

    # 1. Verify distinct slot selections
    assert response.results["fifo"].decisions[0].scheduled_start == t0
    assert response.results["naive_green"].decisions[0].scheduled_start == t1
    assert response.results["carbonova"].decisions[0].scheduled_start == t0
    assert response.results["oracle"].decisions[0].scheduled_start == t2

    # 2. Verify realized emissions
    assert response.results["fifo"].metrics["total_realized_emissions_gco2"] == 1000.0
    assert response.results["naive_green"].metrics["total_realized_emissions_gco2"] == 1250.0 # Backfire
    assert response.results["carbonova"].metrics["total_realized_emissions_gco2"] == 1000.0   # Averted
    assert response.results["oracle"].metrics["total_realized_emissions_gco2"] == 700.0       # Optimal
