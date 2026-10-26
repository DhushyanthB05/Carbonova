"""
Unit tests for Job model validation.
Section 13.1 of Master Specification.
"""

from datetime import datetime, timedelta
import pytest
from pydantic import ValidationError
from backend.scheduler.models import Job


def test_valid_job_creation():
    now = datetime(2026, 10, 25, 10, 0, 0)
    job = Job(
        job_id="job-001",
        job_type="training",
        arrival_time=now,
        deadline=now + timedelta(hours=6),
        duration_minutes=120,
        energy_kwh=3.5,
        priority=1,
        deferrable=True,
        resource_requirement=1,
    )
    assert job.job_id == "job-001"
    assert job.duration_minutes == 120
    assert job.energy_kwh == 3.5


def test_reject_deadline_before_or_equal_arrival():
    now = datetime(2026, 10, 25, 10, 0, 0)
    # Deadline before arrival
    with pytest.raises(ValidationError):
        Job(
            job_id="job-bad-deadline",
            arrival_time=now,
            deadline=now - timedelta(hours=1),
            duration_minutes=60,
            energy_kwh=1.0,
        )

    # Deadline equal to arrival
    with pytest.raises(ValidationError):
        Job(
            job_id="job-equal-deadline",
            arrival_time=now,
            deadline=now,
            duration_minutes=60,
            energy_kwh=1.0,
        )


def test_duration_exceeding_window_is_initially_infeasible():
    now = datetime(2026, 10, 25, 10, 0, 0)
    # Available window is 60 minutes, but duration is 120 minutes
    job = Job(
        job_id="job-too-long",
        arrival_time=now,
        deadline=now + timedelta(minutes=60),
        duration_minutes=120,
        energy_kwh=1.0,
    )
    # In Member 2's authoritative design, the model instantiates cleanly but is marked infeasible
    assert not job.is_initially_feasible(cluster_capacity=4.0)


def test_reject_non_positive_duration_or_energy():
    now = datetime(2026, 10, 25, 10, 0, 0)
    # Duration <= 0
    with pytest.raises(ValidationError):
        Job(
            job_id="job-zero-duration",
            arrival_time=now,
            deadline=now + timedelta(hours=2),
            duration_minutes=0,
            energy_kwh=1.0,
        )

    # Energy <= 0
    with pytest.raises(ValidationError):
        Job(
            job_id="job-zero-energy",
            arrival_time=now,
            deadline=now + timedelta(hours=2),
            duration_minutes=60,
            energy_kwh=0.0,
        )
