"""
Unit tests for reusable evaluation metrics, counterfactuals, backfire rates,
and baseline/oracle comparisons.
"""

from datetime import datetime, timedelta, timezone
import pytest

from backend.carbon.synthetic import create_mock_carbon_grid
from backend.scheduler.metrics import (
    calculate_job_emissions,
    compute_forecast_interval_coverage,
    compute_schedule_metrics,
)
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
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


def test_hand_calculated_emissions(base_time):
    # Slot 10:00 = 100 gCO2/kWh, Slot 11:00 = 200 gCO2/kWh
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[100.0, 200.0],
        realized_values=[100.0, 200.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j1",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=2.5,  # 2.5 kWh
    )
    # At 10:00: 2.5 kWh * 100 gCO2/kWh = 250 gCO2
    em_10 = calculate_job_emissions(job, base_time, grid, use_realized=True)
    assert em_10 == 250.0

    # At 11:00: 2.5 kWh * 200 gCO2/kWh = 500 gCO2
    em_11 = calculate_job_emissions(job, base_time + timedelta(hours=1), grid, use_realized=True)
    assert em_11 == 500.0


def test_backfire_rate_none_when_no_delayed_jobs(base_time):
    # Under FIFO, all jobs run at earliest feasible slot -> 0 delayed jobs
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 100.0],
        realized_values=[200.0, 100.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j1",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    config = SchedulerConfig(policy=PolicyType.FIFO)
    result = run_fifo_policy([job], grid, config)
    metrics = compute_schedule_metrics([job], result, grid)

    assert metrics["delayed_jobs_count"] == 0
    assert metrics["backfire_rate_pct"] is None
    assert "N/A" in metrics["backfire_rate_display"]


def test_backfire_detection(base_time):
    """
    Job delayed to 11:00 because forecast predicted 11:00 would be 50 vs 10:00 at 200.
    In reality, 11:00 realized was 300, while 10:00 was 200!
    The delay caused a backfire (emissions increased from 200*5=1000 to 300*5=1500).
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 50.0],
        uncertainties=[5.0, 5.0],
        realized_values=[200.0, 300.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-backfire",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    config = SchedulerConfig(policy=PolicyType.NAIVE_GREEN)
    result = run_naive_green_policy([job], grid, config)
    metrics = compute_schedule_metrics([job], result, grid)

    assert metrics["delayed_jobs_count"] == 1
    assert metrics["backfire_jobs_count"] == 1
    assert metrics["backfire_rate_pct"] == 100.0
    assert metrics["total_realized_emissions_gco2"] == 1500.0
    assert metrics["counterfactual_earliest_emissions_gco2"] == 1000.0


def test_baseline_and_oracle_gap_metrics(base_time):
    # 10:00 = 200 gCO2, 11:00 = 100 gCO2
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 100.0],
        realized_values=[200.0, 100.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-comp",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
    )
    # FIFO: runs at 10:00 -> 10 * 200 = 2000 gCO2
    fifo_res = run_fifo_policy([job], grid, SchedulerConfig(policy=PolicyType.FIFO))
    # Naive-Green: runs at 11:00 -> 10 * 100 = 1000 gCO2
    naive_res = run_naive_green_policy([job], grid, SchedulerConfig(policy=PolicyType.NAIVE_GREEN))
    # Oracle: runs at 11:00 -> 1000 gCO2
    oracle_res = run_oracle_policy([job], grid, SchedulerConfig(policy=PolicyType.ORACLE))

    metrics = compute_schedule_metrics(
        jobs=[job],
        schedule_result=naive_res,
        carbon_grid=grid,
        baseline_result=fifo_res,
        oracle_result=oracle_res,
    )

    # Reduction vs FIFO baseline
    assert metrics["baseline_comparison"]["baseline_emissions_gco2"] == 2000.0
    assert metrics["baseline_comparison"]["emissions_reduction_gco2"] == 1000.0
    assert metrics["baseline_comparison"]["emissions_reduction_pct"] == 50.0

    # Oracle gap: Naive vs Oracle (both 1000 gCO2 -> 0 gap)
    assert metrics["oracle_comparison"]["oracle_emissions_gco2"] == 1000.0
    assert metrics["oracle_comparison"]["oracle_gap_gco2"] == 0.0
    assert metrics["oracle_comparison"]["oracle_gap_pct"] == 0.0


def test_forecast_interval_coverage(base_time):
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[100.0, 100.0, 100.0, 100.0],
        uncertainties=[10.0, 10.0, 10.0, 10.0],  # CI: [100 - 19.6, 100 + 19.6] -> [80.4, 119.6]
        realized_values=[95.0, 105.0, 115.0, 150.0],  # 3 inside [80.4, 119.6], 1 outside (150)
        time_step_minutes=60,
    )
    cov = compute_forecast_interval_coverage(grid)
    assert cov["status"] == "EVALUATED"
    assert cov["evaluable_points"] == 4
    assert cov["in_bounds_points"] == 3
    assert cov["coverage_pct"] == 75.0


def test_empty_jobs_metrics_no_division_by_zero(base_time):
    """
    When 0 jobs are passed to compute_schedule_metrics, no division by zero occurs
    and deadline_success_rate_pct is None ('N/A').
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[100.0, 100.0],
        time_step_minutes=60,
    )
    empty_result = run_fifo_policy([], grid, SchedulerConfig(policy=PolicyType.FIFO))
    metrics = compute_schedule_metrics([], empty_result, grid)

    assert metrics["total_jobs_submitted"] == 0
    assert metrics["initially_feasible_jobs"] == 0
    assert metrics["deadline_success_rate_pct"] is None
    assert "N/A" in metrics["deadline_success_display"]
    assert metrics["backfire_rate_pct"] is None
    assert metrics["waiting_time_minutes"]["mean"] is None


def test_zero_baseline_emissions_safe_division(base_time):
    """
    When baseline emissions are 0.0, reduction percentage returns 0.0 without division by zero.
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[0.0, 0.0],
        realized_values=[0.0, 0.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="j-zero-em",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    fifo_res = run_fifo_policy([job], grid, SchedulerConfig(policy=PolicyType.FIFO))
    carb_res = run_carbonova_policy([job], grid, SchedulerConfig(policy=PolicyType.CARBONOVA))

    metrics = compute_schedule_metrics(
        jobs=[job],
        schedule_result=carb_res,
        carbon_grid=grid,
        baseline_result=fifo_res,
    )
    assert metrics["baseline_comparison"]["baseline_emissions_gco2"] == 0.0
    assert metrics["baseline_comparison"]["emissions_reduction_pct"] == 0.0
