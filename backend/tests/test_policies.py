"""
Comprehensive unit tests for the four scheduling policies:
1. FIFO / earliest-feasible
2. Naive-green
3. Carbonova uncertainty-aware & minimum-improvement margin
4. Perfect-forecast greedy oracle
"""

from datetime import datetime, timedelta, timezone
import pytest

from backend.carbon.synthetic import create_mock_carbon_grid
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
    JobOrdering,
    MarginUnit,
    PolicyType,
    SchedulerConfig,
)
from backend.scheduler.policies import (
    run_carbonova_policy,
    run_fifo_policy,
    run_naive_green_policy,
    run_oracle_policy,
)


@pytest.fixture
def base_time():
    return datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)


def test_fifo_earliest_feasible(base_time):
    # Carbon values: 300, 100, 50
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[300.0, 100.0, 50.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-fifo",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=10.0,
    )
    config = SchedulerConfig(policy=PolicyType.FIFO, cluster=ClusterConfig(total_capacity=4.0))
    result = run_fifo_policy([job], grid, config)

    assert len(result.decisions) == 1
    d = result.decisions[0]
    assert d.feasibility_status == FeasibilityStatus.SCHEDULED
    # FIFO must schedule at base_time (earliest) despite high carbon (300)
    assert d.scheduled_start == base_time
    assert d.waiting_time_minutes == 0.0


def test_naive_green_selects_lowest_predicted(base_time):
    # Carbon values: 300 at 10:00, 100 at 11:00, 200 at 12:00
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[300.0, 100.0, 200.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-naive",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=10.0,
    )
    config = SchedulerConfig(policy=PolicyType.NAIVE_GREEN, cluster=ClusterConfig(total_capacity=4.0))
    result = run_naive_green_policy([job], grid, config)

    d = result.decisions[0]
    assert d.feasibility_status == FeasibilityStatus.SCHEDULED
    # Naive green selects 11:00 (value 100.0)
    assert d.scheduled_start == base_time + timedelta(hours=1)
    assert d.predicted_carbon_intensity == 100.0
    assert d.waiting_time_minutes == 60.0


def test_carbonova_uncertainty_penalty(base_time):
    """
    Candidate 10:00: predicted 200, unc 10 -> risk = 200 + 1.0 * 10 = 210
    Candidate 11:00: predicted 150, unc 100 -> risk = 150 + 1.0 * 100 = 250 (high uncertainty!)
    Candidate 12:00: predicted 180, unc 10 -> risk = 180 + 1.0 * 10 = 190 (lowest risk!)

    Naive-green would pick 11:00 (pred 150).
    Carbonova with lambda=1.0 and margin=0.05 will pick 12:00 (risk 190 < 210, improvement = 9.5% >= 5%).
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 150.0, 180.0],
        uncertainties=[10.0, 100.0, 10.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-carb",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=10.0,
    )

    # 1. Naive green picks 11:00
    config_naive = SchedulerConfig(policy=PolicyType.NAIVE_GREEN)
    res_naive = run_naive_green_policy([job], grid, config_naive)
    assert res_naive.decisions[0].scheduled_start == base_time + timedelta(hours=1)

    # 2. Carbonova picks 12:00
    config_carb = SchedulerConfig(
        policy=PolicyType.CARBONOVA,
        risk_lambda=1.0,
        min_improvement_margin=0.05,
        margin_unit=MarginUnit.RELATIVE_PERCENTAGE,
    )
    res_carb = run_carbonova_policy([job], grid, config_carb)
    d_carb = res_carb.decisions[0]
    assert d_carb.scheduled_start == base_time + timedelta(hours=2)
    assert d_carb.risk_score == 190.0
    assert d_carb.improvement_pct == pytest.approx((210 - 190) / 210 * 100.0, 0.01)


def test_carbonova_min_improvement_margin_threshold(base_time):
    """
    Earliest 10:00: pred 200, unc 0 -> risk 200
    Candidate 11:00: pred 194, unc 0 -> risk 194
    Improvement: (200 - 194) / 200 = 3.0%.
    With min_improvement_margin = 0.05 (5%), improvement is insufficient.
    Should schedule at earliest (10:00).
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 194.0],
        uncertainties=[0.0, 0.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-margin",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
        deferrable=True,
    )
    config = SchedulerConfig(
        policy=PolicyType.CARBONOVA,
        risk_lambda=0.5,
        min_improvement_margin=0.05,
    )
    res = run_carbonova_policy([job], grid, config)
    d = res.decisions[0]
    # Insufficient improvement -> earliest slot
    assert d.scheduled_start == base_time
    assert "below 5.0% margin" in d.reason


def test_carbonova_absolute_score_margin_and_boundary(base_time):
    """
    Tests MarginUnit.ABSOLUTE_SCORE with exact boundary conditions.
    Earliest 10:00: risk = 200.0 gCO2eq/kWh.
    Candidate 11:00: risk = 185.0 gCO2eq/kWh.
    Reduction = 15.0 gCO2eq/kWh.

    Case A: Margin = 15.0 gCO2eq/kWh (exact boundary).
    15.0 >= 15.0 -> meets margin! Delays to 11:00.

    Case B: Margin = 15.01 gCO2eq/kWh (just above reduction).
    15.0 < 15.01 -> below margin! Executes at 10:00.
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 185.0],
        uncertainties=[0.0, 0.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-abs-margin",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
        deferrable=True,
    )

    # Case A: Exactly on margin (15.0 gCO2eq/kWh)
    cfg_exact = SchedulerConfig(
        policy=PolicyType.CARBONOVA,
        min_improvement_margin=15.0,
        margin_unit=MarginUnit.ABSOLUTE_SCORE,
    )
    res_exact = run_carbonova_policy([job], grid, cfg_exact)
    assert res_exact.decisions[0].scheduled_start == base_time + timedelta(hours=1)
    assert res_exact.decisions[0].improvement_score == 15.0
    assert "meets 15.00 gCO2eq/kWh margin" in res_exact.decisions[0].reason

    # Case B: Just below margin (15.01 gCO2eq/kWh)
    cfg_above = SchedulerConfig(
        policy=PolicyType.CARBONOVA,
        min_improvement_margin=15.01,
        margin_unit=MarginUnit.ABSOLUTE_SCORE,
    )
    res_above = run_carbonova_policy([job], grid, cfg_above)
    assert res_above.decisions[0].scheduled_start == base_time
    assert "below 15.01 gCO2eq/kWh margin" in res_above.decisions[0].reason


def test_carbonova_zero_lambda(base_time):
    """
    When risk_lambda == 0.0, risk_score equals predicted_carbon_intensity.
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 100.0],
        uncertainties=[100.0, 100.0],  # High uncertainty ignored when lambda=0
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-zero-lambda",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
    )
    cfg = SchedulerConfig(
        policy=PolicyType.CARBONOVA,
        risk_lambda=0.0,
        min_improvement_margin=0.05,
    )
    res = run_carbonova_policy([job], grid, cfg)
    d = res.decisions[0]
    assert d.risk_score == 100.0
    assert d.scheduled_start == base_time + timedelta(hours=1)


def test_carbonova_non_deferrable_executes_immediately(base_time):
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[300.0, 100.0],
        uncertainties=[5.0, 5.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-non-def",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
        deferrable=False,  # Non-deferrable!
    )
    config = SchedulerConfig(policy=PolicyType.CARBONOVA, min_improvement_margin=0.05)
    res = run_carbonova_policy([job], grid, config)
    d = res.decisions[0]
    assert d.scheduled_start == base_time
    assert "Non-deferrable" in d.reason


def test_non_integer_duration_actual_finish(base_time):
    """
    Job duration = 45 minutes on a 60-minute grid.
    Start at 10:00 -> actual finish must be 10:45 (not 11:00).
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 100.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-45min",
        arrival_time=base_time,
        deadline=base_time + timedelta(minutes=50),  # Deadline is 10:50!
        duration_minutes=45,
        energy_kwh=3.0,
    )
    config = SchedulerConfig(policy=PolicyType.FIFO)
    res = run_fifo_policy([job], grid, config)
    d = res.decisions[0]
    assert d.feasibility_status == FeasibilityStatus.SCHEDULED
    assert d.scheduled_start == base_time
    # Finish is exactly 10:45
    assert d.scheduled_finish == base_time + timedelta(minutes=45)
    assert d.scheduled_finish <= job.deadline


def test_flat_carbon_all_policies_select_earliest(base_time):
    """
    When carbon is flat (equal across all slots), all policies select earliest slot.
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[150.0, 150.0, 150.0],
        uncertainties=[10.0, 10.0, 10.0],
        realized_values=[150.0, 150.0, 150.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-flat",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    r_fifo = run_fifo_policy([job], grid, SchedulerConfig(policy=PolicyType.FIFO))
    r_naive = run_naive_green_policy([job], grid, SchedulerConfig(policy=PolicyType.NAIVE_GREEN))
    r_carb = run_carbonova_policy([job], grid, SchedulerConfig(policy=PolicyType.CARBONOVA))
    r_oracle = run_oracle_policy([job], grid, SchedulerConfig(policy=PolicyType.ORACLE))

    assert r_fifo.decisions[0].scheduled_start == base_time
    assert r_naive.decisions[0].scheduled_start == base_time
    assert r_carb.decisions[0].scheduled_start == base_time
    assert r_oracle.decisions[0].scheduled_start == base_time


def test_oracle_policy(base_time):
    # Forecast predicted: 10:00 = 200, 11:00 = 100
    # Realized actual: 10:00 = 120, 11:00 = 250 (forecast backfired!)
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 100.0],
        realized_values=[120.0, 250.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-oracle",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
    )
    config = SchedulerConfig(policy=PolicyType.ORACLE)
    res = run_oracle_policy([job], grid, config)
    d = res.decisions[0]
    # Oracle knows realized: 10:00 is 120 vs 11:00 is 250, so oracle schedules at 10:00!
    assert d.scheduled_start == base_time


def test_capacity_contention_and_infeasible_jobs(base_time):
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[100.0, 100.0, 100.0],
        time_step_minutes=60,
    )
    # Cluster capacity is 2.0
    config = SchedulerConfig(cluster=ClusterConfig(total_capacity=2.0))

    # Job 1 takes all 2.0 units from 10:00 to 12:00 (2 hours)
    j1 = Job(
        job_id="j1",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=120,
        energy_kwh=20.0,
        resource_requirement=2.0,
    )
    # Job 2 also wants 2.0 units from 10:00 to 12:00 -> no capacity left!
    j2 = Job(
        job_id="j2",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
        resource_requirement=2.0,
    )
    # Job 3 is initially infeasible (duration 4 hours with 2 hour window)
    j3 = Job(
        job_id="j3",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=240,
        energy_kwh=10.0,
        resource_requirement=1.0,
    )

    res = run_fifo_policy([j1, j2, j3], grid, config)
    decisions = {d.job_id: d for d in res.decisions}

    assert decisions["j1"].feasibility_status == FeasibilityStatus.SCHEDULED
    assert decisions["j2"].feasibility_status == FeasibilityStatus.CAPACITY_INFEASIBLE
    assert decisions["j3"].feasibility_status == FeasibilityStatus.INITIALLY_INFEASIBLE
