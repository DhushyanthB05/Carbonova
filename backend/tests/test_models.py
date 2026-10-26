"""
Unit tests for Job schemas, validation, and serialization.
"""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from backend.scheduler.models import (
    ClusterConfig,
    DecisionRecord,
    FeasibilityStatus,
    Job,
    JobOrdering,
    PolicyScheduleResult,
    PolicyType,
    ScheduleBatchRequest,
    SchedulerConfig,
)


def test_job_valid_creation():
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    job = Job(
        job_id="job-1",
        arrival_time=now,
        deadline=now + timedelta(hours=4),
        duration_minutes=60,
        energy_kwh=10.5,
        priority=2,
        deferrable=True,
        resource_requirement=2.0,
    )
    assert job.job_id == "job-1"
    assert job.arrival_time == now
    assert job.duration_timedelta == timedelta(minutes=60)
    assert job.is_initially_feasible(cluster_capacity=4.0) is True


def test_job_invalid_timestamps():
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    # Deadline before or equal arrival
    with pytest.raises(ValidationError):
        Job(
            job_id="job-bad-time",
            arrival_time=now,
            deadline=now,  # equal
            duration_minutes=30,
            energy_kwh=5.0,
        )

    with pytest.raises(ValidationError):
        Job(
            job_id="job-bad-time-2",
            arrival_time=now,
            deadline=now - timedelta(hours=1),
            duration_minutes=30,
            energy_kwh=5.0,
        )


def test_job_invalid_duration_and_energy():
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        Job(
            job_id="job-zero-duration",
            arrival_time=now,
            deadline=now + timedelta(hours=2),
            duration_minutes=0,  # <= 0
            energy_kwh=5.0,
        )

    with pytest.raises(ValidationError):
        Job(
            job_id="job-negative-energy",
            arrival_time=now,
            deadline=now + timedelta(hours=2),
            duration_minutes=60,
            energy_kwh=-1.0,  # <= 0
        )

    with pytest.raises(ValidationError):
        Job(
            job_id="job-negative-resource",
            arrival_time=now,
            deadline=now + timedelta(hours=2),
            duration_minutes=60,
            energy_kwh=5.0,
            resource_requirement=0.0,  # <= 0
        )


def test_job_initially_infeasible_checks():
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    # Duration exceeds window
    job1 = Job(
        job_id="job-too-long",
        arrival_time=now,
        deadline=now + timedelta(minutes=30),
        duration_minutes=60,  # 60 > 30 min window
        energy_kwh=5.0,
    )
    assert job1.is_initially_feasible(cluster_capacity=4.0) is False

    # Resource requirement exceeds cluster capacity
    job2 = Job(
        job_id="job-too-heavy",
        arrival_time=now,
        deadline=now + timedelta(hours=5),
        duration_minutes=60,
        energy_kwh=5.0,
        resource_requirement=8.0,
    )
    assert job2.is_initially_feasible(cluster_capacity=4.0) is False


def test_schedule_batch_request_duplicate_ids():
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    j1 = Job(
        job_id="dup-1",
        arrival_time=now,
        deadline=now + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    j2 = Job(
        job_id="dup-1",  # duplicate ID
        arrival_time=now,
        deadline=now + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    with pytest.raises(ValidationError) as exc:
        ScheduleBatchRequest(jobs=[j1, j2])
    assert "Duplicate job IDs" in str(exc.value)
