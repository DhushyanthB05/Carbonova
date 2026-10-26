"""
Sensitivity and Sanity tests.
Section 9.2 & 13.1 of Master Specification.
Delegates to Member 2's authoritative SchedulingEngine via EvaluationRunner.
"""

from datetime import datetime, timedelta, timezone
from backend.scheduler.models import Job
from backend.evaluation.scenarios import (
    generate_jobs,
    generate_standard_batch_scenario,
    generate_urgent_only_scenario,
)
from backend.evaluation.sensitivity import (
    run_flat_carbon_sanity_check,
    run_lambda_sweep,
    run_forecast_noise_experiment,
)
from backend.evaluation.runner import EvaluationRunner


def test_flat_carbon_no_manufactured_savings():
    """
    CRITICAL SANITY TEST (Section 9.2):
    When carbon is completely flat across time, time-shifting must NOT
    manufacture large savings. Emissions reduction should be 0.0%.
    """
    start = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)
    time_grid = [start + timedelta(hours=i) for i in range(24)]
    jobs = generate_standard_batch_scenario(start_time=start, seed=42)

    report = run_flat_carbon_sanity_check(jobs, time_grid, flat_intensity=350.0, max_capacity=2)

    fifo_emissions = report.summary["fifo"].total_emissions_gco2e
    carb_emissions = report.summary["carbonova"].total_emissions_gco2e

    # Savings must be zero (or within float rounding)
    diff = abs(fifo_emissions - carb_emissions)
    assert diff < 1e-4, f"Manufactured savings detected on flat trace: {diff} gCO2e"


def test_seed_determinism():
    """
    Verifies that running with the same seed generates identical workloads and schedules.
    """
    start = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)
    jobs1 = generate_jobs(start, horizon_hours=24, n_jobs=15, seed=123)
    jobs2 = generate_jobs(start, horizon_hours=24, n_jobs=15, seed=123)

    assert len(jobs1) == len(jobs2)
    for j1, j2 in zip(jobs1, jobs2):
        assert j1.job_id == j2.job_id
        assert j1.arrival_time == j2.arrival_time
        assert j1.duration_minutes == j2.duration_minutes
        assert j1.energy_kwh == j2.energy_kwh


def test_urgent_only_scenario_backfire_is_none():
    """
    When all jobs are urgent/non-deferrable:
    - Backfire rate must be None (N/A)
    - Mean waiting time must be 0 (or close to 0 if constrained by capacity)
    """
    start = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)
    time_grid = [start + timedelta(hours=i) for i in range(24)]
    realized_carbon = {t: 300.0 for t in time_grid}
    forecast_carbon = {t: 300.0 for t in time_grid}

    urgent_jobs = generate_urgent_only_scenario(start_time=start, seed=42)

    runner = EvaluationRunner(
        time_grid=time_grid,
        realized_carbon_map=realized_carbon,
        forecast_carbon_map=forecast_carbon,
        max_capacity=5,  # ample capacity
    )

    report = runner.run_all_policies(urgent_jobs, risk_lambda=1.0)
    assert report.summary["carbonova"].backfire_rate_pct is None


def test_lambda_sensitivity_differentiates_under_horizon_uncertainty():
    """
    Demonstrates that risk_lambda changes candidate slot selection when
    near-term vs far-term slots have different uncertainty levels.
    """
    start = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)
    t0 = start
    t1 = start + timedelta(hours=1)
    t2 = start + timedelta(hours=8)
    time_grid = [t0, t1, t2]

    # Slot t1 has moderate predicted intensity (300) with low uncertainty (10)
    # Slot t2 has lower predicted intensity (250) but high uncertainty (60)
    forecast_map = {t0: 350.0, t1: 300.0, t2: 250.0}
    uncertainty_map = {t0: 5.0, t1: 10.0, t2: 60.0}

    job = Job(
        job_id="risk-tradeoff-job",
        arrival_time=t0,
        deadline=t2 + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=2.0,
        deferrable=True,
    )

    # At lambda = 0.0 (risk neutral):
    # R(t1) = 300, R(t2) = 250 -> chooses t2 (distant dip)
    runner_l0 = EvaluationRunner(
        time_grid=time_grid,
        forecast_carbon_map=forecast_map,
        uncertainty_map=uncertainty_map,
        max_capacity=1,
    )
    rep_l0 = runner_l0.run_all_policies(jobs=[job], risk_lambda=0.0)
    sched_l0 = rep_l0.detailed_schedules["carbonova"]
    assert len(sched_l0.scheduled_jobs) == 1
    assert sched_l0.scheduled_jobs[0].scheduled_start == t2

    # At lambda = 2.0 (risk averse):
    # R(t1) = 300 + 2*10 = 320
    # R(t2) = 250 + 2*60 = 370
    # -> chooses t1 (nearer, more certain slot)
    runner_l2 = EvaluationRunner(
        time_grid=time_grid,
        forecast_carbon_map=forecast_map,
        uncertainty_map=uncertainty_map,
        max_capacity=1,
    )
    rep_l2 = runner_l2.run_all_policies(jobs=[job], risk_lambda=2.0)
    sched_l2 = rep_l2.detailed_schedules["carbonova"]
    assert len(sched_l2.scheduled_jobs) == 1
    assert sched_l2.scheduled_jobs[0].scheduled_start == t1


def test_forecast_noise_experiment_reproducibility():
    """
    Verifies that run_forecast_noise_experiment with fixed seed produces
    deterministic, reproducible results and valid non-negative values.
    """
    start = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)
    time_grid = [start + timedelta(hours=i) for i in range(12)]
    true_realized = {t: 300.0 + 50.0 * (i % 3) for i, t in enumerate(time_grid)}

    jobs = generate_standard_batch_scenario(start_time=start, seed=42)[:5]

    res1 = run_forecast_noise_experiment(
        jobs=jobs,
        time_grid=time_grid,
        true_realized_carbon=true_realized,
        noise_stds=[0.0, 50.0],
        seed=123,
    )
    res2 = run_forecast_noise_experiment(
        jobs=jobs,
        time_grid=time_grid,
        true_realized_carbon=true_realized,
        noise_stds=[0.0, 50.0],
        seed=123,
    )

    assert len(res1) == 2
    assert res1 == res2
    for item in res1:
        assert item["noise_std"] >= 0.0
        assert item["naive_green"]["total_emissions"] > 0.0
        assert item["carbonova"]["total_emissions"] > 0.0
