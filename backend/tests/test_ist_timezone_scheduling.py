"""
Regression tests for timezone-offset input timestamps (IST +05:30),
discrete slot alignment, non-deferrable job immediate execution,
and accurate feasibility classification (missing forecast coverage vs capacity contention).
"""

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.storage import store
from backend.carbon.synthetic import SyntheticCarbonDataProvider, create_mock_carbon_grid
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
    PolicyType,
    SchedulerConfig,
)
from backend.scheduler.policies import (
    evaluate_job_feasibility,
    run_carbonova_policy,
    run_fifo_policy,
    run_naive_green_policy,
    run_oracle_policy,
)
from backend.scheduler.time_grid import get_candidate_start_slots

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    store.clear_jobs()
    yield
    store.clear_jobs()


def test_ist_three_jobs_reproduction_via_api():
    """
    Directly reproduces and verifies the user's reported three-job scenario:
    - Jobs arrive at 12:00 IST (+05:30) = 06:30 UTC
    - Deadlines are between 14:00 and 18:00 IST
    - Capacity is 4.0
    - All three jobs must schedule successfully across all four policies
    - Non-deferrable job-1 must execute at its earliest feasible opportunity (07:00 UTC = 12:30 IST)
    """
    jobs_payload = [
        {
            "job_id": "job-1",
            "job_type": "training",
            "arrival_time": "2026-10-26T12:00:00+05:30",
            "deadline": "2026-10-26T14:00:00+05:30",
            "duration_minutes": 60,
            "energy_kwh": 10.0,
            "priority": 1,
            "deferrable": False,
            "resource_requirement": 1.0,
        },
        {
            "job_id": "job-2",
            "job_type": "inference",
            "arrival_time": "2026-10-26T12:00:00+05:30",
            "deadline": "2026-10-26T16:00:00+05:30",
            "duration_minutes": 60,
            "energy_kwh": 8.0,
            "priority": 2,
            "deferrable": True,
            "resource_requirement": 2.0,
        },
        {
            "job_id": "job-3",
            "job_type": "batch",
            "arrival_time": "2026-10-26T12:00:00+05:30",
            "deadline": "2026-10-26T18:00:00+05:30",
            "duration_minutes": 120,
            "energy_kwh": 15.0,
            "priority": 1,
            "deferrable": True,
            "resource_requirement": 1.0,
        },
    ]

    # 1. POST /api/jobs validates initial feasibility
    submit_res = client.post("/api/jobs", json=jobs_payload)
    assert submit_res.status_code == 200
    init_map = submit_res.json()["initial_feasibility"]
    assert init_map == {"job-1": True, "job-2": True, "job-3": True}

    # 2. POST /api/schedule/run schedules all three jobs
    run_res = client.post("/api/schedule/run", json={"run_all_policies": True})
    assert run_res.status_code == 200
    data = run_res.json()

    for pol in ["fifo", "naive_green", "carbonova", "oracle"]:
        policy_res = data["results"][pol]
        decisions = {d["job_id"]: d for d in policy_res["decisions"]}

        # All jobs must be SCHEDULED, not capacity_infeasible
        assert decisions["job-1"]["feasibility_status"] == FeasibilityStatus.SCHEDULED.value
        assert decisions["job-2"]["feasibility_status"] == FeasibilityStatus.SCHEDULED.value
        assert decisions["job-3"]["feasibility_status"] == FeasibilityStatus.SCHEDULED.value

        # Non-deferrable job-1 must start at earliest feasible slot: 07:00 UTC (12:30 IST)
        assert decisions["job-1"]["scheduled_start"] == "2026-10-26T07:00:00Z"
        assert decisions["job-1"]["scheduled_finish"] == "2026-10-26T08:00:00Z"

        # Check deadline adherence
        assert decisions["job-1"]["scheduled_finish"] <= "2026-10-26T08:30:00Z"
        assert decisions["job-2"]["scheduled_finish"] <= "2026-10-26T10:30:00Z"
        assert decisions["job-3"]["scheduled_finish"] <= "2026-10-26T12:30:00Z"

        # Metrics must reflect scheduled jobs and emissions
        metrics = policy_res["metrics"]
        assert metrics["scheduled_jobs_count"] == 3
        assert metrics["deadline_success_rate_pct"] == 100.0
        assert metrics["total_realized_emissions_gco2"] > 0


def test_missing_forecast_coverage_vs_genuine_capacity_contention():
    """
    Verifies that:
    1. A job lacking carbon forecast points within its window is classified as INITIALLY_INFEASIBLE
       with an explanatory forecast coverage reason (NOT capacity infeasible).
    2. A job with valid forecast candidates that cannot schedule due to concurrency is classified
       as CAPACITY_INFEASIBLE.
    """
    base_time = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    # Grid covers only 10:00 to 11:00 (1 slot: [10:00, 11:00))
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[150.0],
        time_step_minutes=60,
    )

    # Job A needs 2 hours (needs slots 10:00 and 11:00, but 11:00 is missing from grid)
    job_missing_forecast = Job(
        job_id="job-no-horizon",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=120,
        energy_kwh=10.0,
        resource_requirement=1.0,
    )

    config = SchedulerConfig(policy=PolicyType.FIFO, cluster=ClusterConfig(total_capacity=1.0))
    res = run_fifo_policy([job_missing_forecast], grid, config)
    d_missing = res.decisions[0]
    # Must NOT be capacity_infeasible because capacity was never the blocker
    assert d_missing.feasibility_status == FeasibilityStatus.INITIALLY_INFEASIBLE
    assert "forecast coverage" in d_missing.reason.lower() or "grid" in d_missing.reason.lower()

    # Job B and Job C: Grid covers both, but Job B saturates capacity (1.0 of 1.0)
    grid_2slots = create_mock_carbon_grid(
        start_time=base_time,
        values=[150.0, 140.0],
        time_step_minutes=60,
    )
    job_b = Job(
        job_id="job-b",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=1),
        duration_minutes=60,
        energy_kwh=5.0,
        resource_requirement=1.0,
    )
    job_c = Job(
        job_id="job-c",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=1),
        duration_minutes=60,
        energy_kwh=5.0,
        resource_requirement=1.0,
    )

    res_contention = run_fifo_policy([job_b, job_c], grid_2slots, config)
    decisions = {d.job_id: d for d in res_contention.decisions}
    assert decisions["job-b"].feasibility_status == FeasibilityStatus.SCHEDULED
    # Job C is genuinely CAPACITY_INFEASIBLE because capacity at 10:00 was saturated
    assert decisions["job-c"].feasibility_status == FeasibilityStatus.CAPACITY_INFEASIBLE
    assert "cluster capacity" in decisions["job-c"].reason.lower()


def test_arrival_boundary_exact_and_between_slots():
    """
    Verifies that:
    - An arrival exactly on a slot boundary (e.g. 10:00:00Z) allows 10:00:00Z as a candidate start.
    - An arrival between slot boundaries (e.g. 10:00:01Z or 10:15:00Z) cannot start in the 10:00 slot,
      and its earliest candidate is the next discrete slot (11:00:00Z).
    """
    t0 = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    grid = create_mock_carbon_grid(
        start_time=t0,
        values=[200.0, 180.0, 160.0],
        time_step_minutes=60,
    )

    # Job on exact boundary: 10:00
    j_exact = Job(
        job_id="j-exact",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    candidates_exact = get_candidate_start_slots(j_exact, grid, 60)
    assert candidates_exact[0] == t0

    # Job between boundary: 10:15
    j_between = Job(
        job_id="j-between",
        arrival_time=t0 + timedelta(minutes=15),
        deadline=t0 + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    candidates_between = get_candidate_start_slots(j_between, grid, 60)
    # Earliest candidate must be 11:00, NOT 10:00
    assert candidates_between[0] == t0 + timedelta(hours=1)


def test_job_deadline_exact_completion_and_overrun():
    """
    Verifies that:
    - A job completing exactly on its deadline (finish == deadline) is valid.
    - A job that finishes even 1 second after its deadline (finish > deadline) is rejected.
    """
    t0 = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    grid = create_mock_carbon_grid(
        start_time=t0,
        values=[200.0, 180.0],
        time_step_minutes=60,
    )

    # Job A: starts 10:00, duration 60m, deadline 11:00 (exact finish at deadline)
    j_exact_finish = Job(
        job_id="j-exact-finish",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=1),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    c_exact = get_candidate_start_slots(j_exact_finish, grid, 60)
    assert len(c_exact) == 1
    assert c_exact[0] == t0

    # Job B: starts 10:00, duration 60m, deadline 10:59:59 (overruns by 1 second)
    j_overrun = Job(
        job_id="j-overrun",
        arrival_time=t0,
        deadline=t0 + timedelta(minutes=59, seconds=59),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    c_overrun = get_candidate_start_slots(j_overrun, grid, 60)
    assert len(c_overrun) == 0


def test_contiguous_coverage_vs_missing_intermediate_points_and_gaps():
    """
    Verifies that:
    - A multi-slot job requires contiguous slots.
    - A missing intermediate point or timestamp gap invalidates the candidate slot.
    """
    from backend.carbon.interface import CarbonForecastPoint, CarbonGrid
    t0 = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    step = timedelta(minutes=60)

    # Grid with 3 points, but 11:00 is missing! Points: 10:00, 12:00, 13:00 (gap between 10:00 and 12:00)
    points_with_gap = [
        CarbonForecastPoint(timestamp=t0, predicted_carbon_intensity=200.0, slot_specific_uncertainty=10.0),
        CarbonForecastPoint(timestamp=t0 + 2 * step, predicted_carbon_intensity=180.0, slot_specific_uncertainty=10.0),
        CarbonForecastPoint(timestamp=t0 + 3 * step, predicted_carbon_intensity=160.0, slot_specific_uncertainty=10.0),
    ]
    grid_gap = CarbonGrid(points_with_gap, time_step_minutes=60)

    # Job needing 120 minutes (2 contiguous slots) starting at 10:00 needs slots 10:00 and 11:00
    j_multi = Job(
        job_id="j-multi",
        arrival_time=t0,
        deadline=t0 + 4 * step,
        duration_minutes=120,
        energy_kwh=10.0,
    )
    candidates = get_candidate_start_slots(j_multi, grid_gap, 60)
    # 10:00 cannot be a candidate because 11:00 is missing.
    # 12:00 CAN be a candidate because 12:00 and 13:00 exist contiguously.
    assert t0 not in candidates
    assert (t0 + 2 * step) in candidates


def test_genuinely_initially_infeasible_fundamental_constraints():
    """
    Verifies fundamental initial infeasibilities:
    1. Duration longer than available deadline window.
    2. Resource requirement exceeding cluster total capacity.
    """
    t0 = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    grid = create_mock_carbon_grid(
        start_time=t0,
        values=[200.0, 180.0, 160.0],
        time_step_minutes=60,
    )
    cluster = ClusterConfig(total_capacity=4.0)

    # 1. Duration > window
    j_too_long = Job(
        job_id="j-too-long",
        arrival_time=t0,
        deadline=t0 + timedelta(minutes=30),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    res1 = run_fifo_policy([j_too_long], grid, SchedulerConfig(cluster=cluster))
    d1 = res1.decisions[0]
    assert d1.feasibility_status == FeasibilityStatus.INITIALLY_INFEASIBLE
    assert "exceeds submission-to-deadline window" in d1.reason

    # 2. Resource requirement > total capacity
    j_too_heavy = Job(
        job_id="j-too-heavy",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=5.0,
        resource_requirement=8.0,  # 8.0 > 4.0
    )
    res2 = run_fifo_policy([j_too_heavy], grid, SchedulerConfig(cluster=cluster))
    d2 = res2.decisions[0]
    assert d2.feasibility_status == FeasibilityStatus.INITIALLY_INFEASIBLE
    assert "exceeds cluster capacity" in d2.reason
