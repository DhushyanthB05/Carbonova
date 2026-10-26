"""
Unit tests for scheduling feasibility and resource constraints.
Section 13.1 of Master Specification.
Delegates to Member 2's authoritative SchedulingEngine via EvaluationRunner.
"""

from datetime import datetime, timedelta, timezone
from backend.scheduler.models import Job
from backend.evaluation.runner import EvaluationRunner


def test_no_job_scheduled_before_arrival_or_after_deadline():
    start = datetime(2026, 10, 25, 8, 0, 0, tzinfo=timezone.utc)
    time_grid = [start + timedelta(hours=i) for i in range(24)]
    carbon_map = {t: 300.0 for t in time_grid}

    job1 = Job(
        job_id="j1",
        arrival_time=start + timedelta(hours=2),
        deadline=start + timedelta(hours=8),
        duration_minutes=120,
        energy_kwh=2.0,
        deferrable=True,
    )
    job2 = Job(
        job_id="j2",
        arrival_time=start + timedelta(hours=5),
        deadline=start + timedelta(hours=10),
        duration_minutes=60,
        energy_kwh=1.0,
        deferrable=True,
    )

    runner = EvaluationRunner(
        time_grid=time_grid,
        forecast_carbon_map=carbon_map,
        uncertainty_map={t: 10.0 for t in time_grid},
        max_capacity=2,
    )
    report = runner.run_all_policies(jobs=[job1, job2], risk_lambda=1.0)
    sched = report.detailed_schedules["carbonova"]

    for sj in sched.scheduled_jobs:
        job = job1 if sj.job_id == "j1" else job2
        assert sj.scheduled_start >= job.arrival_time
        assert sj.scheduled_finish <= job.deadline


def test_resource_capacity_never_exceeded():
    start = datetime(2026, 10, 25, 8, 0, 0, tzinfo=timezone.utc)
    time_grid = [start + timedelta(hours=i) for i in range(12)]
    carbon_map = {t: 200.0 for t in time_grid}

    # 3 jobs competing for capacity = 1 at the exact same arrival window
    jobs = [
        Job(
            job_id=f"j-{i}",
            arrival_time=start,
            deadline=start + timedelta(hours=6),
            duration_minutes=60,
            energy_kwh=1.0,
            resource_requirement=1,
            deferrable=True,
        )
        for i in range(3)
    ]

    runner = EvaluationRunner(
        time_grid=time_grid,
        forecast_carbon_map=carbon_map,
        max_capacity=1,
    )
    report = runner.run_all_policies(jobs=jobs, risk_lambda=1.0)
    sched = report.detailed_schedules["fifo"]

    assert len(sched.scheduled_jobs) == 3

    # All 3 must have distinct non-overlapping start times because capacity is 1
    starts = [sj.scheduled_start for sj in sched.scheduled_jobs]
    assert len(set(starts)) == 3


def test_non_deferrable_job_earliest_feasible():
    start = datetime(2026, 10, 25, 8, 0, 0, tzinfo=timezone.utc)
    time_grid = [start + timedelta(hours=i) for i in range(12)]
    # Hour 5 is much cleaner, but job is non-deferrable
    forecast_map = {t: 500.0 for t in time_grid}
    forecast_map[start + timedelta(hours=5)] = 100.0

    urgent_job = Job(
        job_id="urgent-01",
        arrival_time=start,
        deadline=start + timedelta(hours=8),
        duration_minutes=60,
        energy_kwh=2.0,
        deferrable=False,
    )

    runner = EvaluationRunner(
        time_grid=time_grid,
        forecast_carbon_map=forecast_map,
        uncertainty_map={t: 5.0 for t in time_grid},
        max_capacity=1,
    )
    report = runner.run_all_policies(jobs=[urgent_job], risk_lambda=1.0)
    sched = report.detailed_schedules["carbonova"]

    assert len(sched.scheduled_jobs) == 1
    # Must be scheduled at start (earliest feasible), not hour 5
    assert sched.scheduled_jobs[0].scheduled_start == start
