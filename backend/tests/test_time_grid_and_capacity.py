"""
Unit tests for time grid alignment, interval geometry, and capacity tracker.
"""

from datetime import datetime, timedelta, timezone
import pytest

from backend.carbon.synthetic import create_mock_carbon_grid
from backend.scheduler.capacity import CapacityTracker
from backend.scheduler.models import Job
from backend.scheduler.time_grid import (
    align_to_next_slot,
    align_to_prev_slot,
    calculate_required_slots,
    get_candidate_start_slots,
)


def test_slot_alignment():
    # Exactly on hour
    t0 = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    assert align_to_next_slot(t0, 60) == t0
    assert align_to_prev_slot(t0, 60) == t0

    # 10:15 with 60 min step -> next is 11:00, prev is 10:00
    t1 = datetime(2026, 10, 26, 10, 15, 0, tzinfo=timezone.utc)
    assert align_to_next_slot(t1, 60) == datetime(2026, 10, 26, 11, 0, 0, tzinfo=timezone.utc)
    assert align_to_prev_slot(t1, 60) == datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)

    # 10:15 with 15 min step -> exact match
    assert align_to_next_slot(t1, 15) == t1


def test_calculate_required_slots():
    assert calculate_required_slots(60, 60) == 1
    assert calculate_required_slots(61, 60) == 2
    assert calculate_required_slots(30, 60) == 1
    assert calculate_required_slots(120, 60) == 2
    with pytest.raises(ValueError):
        calculate_required_slots(0, 60)


def test_get_candidate_start_slots():
    t0 = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    grid = create_mock_carbon_grid(
        start_time=t0,
        values=[200.0, 180.0, 150.0, 210.0, 250.0],
        time_step_minutes=60,
    )
    # Job arriving at 10:00, deadline at 13:00, duration 60 mins -> slots 10:00, 11:00, 12:00
    job = Job(
        job_id="j1",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    candidates = get_candidate_start_slots(job, grid, time_step_minutes=60)
    assert len(candidates) == 3
    assert candidates[0] == t0
    assert candidates[1] == t0 + timedelta(hours=1)
    assert candidates[2] == t0 + timedelta(hours=2)


def test_capacity_tracker_half_open_intervals():
    t0 = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    tracker = CapacityTracker(total_capacity=4.0, time_step_minutes=60)

    # Schedule Job A: 10:00 to 12:00 (2 slots), uses 3.0 units
    assert tracker.can_accommodate(t0, duration_slots=2, resource_req=3.0) is True
    tracker.reserve("job-A", t0, duration_slots=2, resource_req=3.0)

    # Check capacity at 10:00 and 11:00 (used = 3.0, available = 1.0)
    assert tracker.get_used_capacity(t0) == 3.0
    assert tracker.get_used_capacity(t0 + timedelta(hours=1)) == 3.0

    # Job B at 10:00 requires 2.0 units -> cannot accommodate (3+2 = 5 > 4)
    assert tracker.can_accommodate(t0, duration_slots=1, resource_req=2.0) is False

    # Job C at 10:00 requires 1.0 unit -> fits exactly
    assert tracker.can_accommodate(t0, duration_slots=1, resource_req=1.0) is True

    # At 12:00 Job A has finished (half-open [10:00, 12:00)) -> available = 4.0
    t2 = t0 + timedelta(hours=2)
    assert tracker.get_used_capacity(t2) == 0.0
    assert tracker.can_accommodate(t2, duration_slots=1, resource_req=4.0) is True
