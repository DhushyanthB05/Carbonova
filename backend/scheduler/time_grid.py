"""
Time Grid and Slot Geometry Utilities.

Enforces half-open execution intervals [start, finish), discrete time-step alignment,
and candidate feasible-slot generation according to carbon grid resolution.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from backend.carbon.interface import CarbonGrid
from backend.scheduler.models import Job


def align_to_next_slot(dt: datetime, time_step_minutes: int) -> datetime:
    """
    Rounds a datetime up (ceil) to the nearest discrete slot boundary.
    If already exactly on a boundary, returns the datetime unchanged.
    Ensures UTC timezone.
    """
    dt_utc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    step_seconds = time_step_minutes * 60
    epoch_seconds = int(dt_utc.timestamp())
    remainder = epoch_seconds % step_seconds
    if remainder == 0:
        return dt_utc
    aligned_seconds = epoch_seconds + (step_seconds - remainder)
    return datetime.fromtimestamp(aligned_seconds, tz=timezone.utc)


def align_to_prev_slot(dt: datetime, time_step_minutes: int) -> datetime:
    """
    Rounds a datetime down (floor) to the nearest discrete slot boundary.
    Ensures UTC timezone.
    """
    dt_utc = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    step_seconds = time_step_minutes * 60
    epoch_seconds = int(dt_utc.timestamp())
    remainder = epoch_seconds % step_seconds
    aligned_seconds = epoch_seconds - remainder
    return datetime.fromtimestamp(aligned_seconds, tz=timezone.utc)


def calculate_required_slots(duration_minutes: int, time_step_minutes: int) -> int:
    """
    Computes the number of discrete time slots required to complete a duration.
    Rounds up to ensure full execution capacity is reserved.
    """
    if duration_minutes <= 0:
        raise ValueError(f"duration_minutes must be > 0, got {duration_minutes}")
    return math.ceil(duration_minutes / time_step_minutes)


def get_candidate_start_slots(
    job: Job,
    carbon_grid: CarbonGrid,
    time_step_minutes: int = 60,
) -> List[datetime]:
    """
    Generates all candidate start slot timestamps for a job that satisfy:
    1. start_slot >= arrival_time (on the grid's discrete slot boundaries)
    2. start_slot + job.duration_timedelta <= deadline (job completes before or at deadline)
    3. All required execution capacity slots exist contiguously in the carbon grid.

    Returns an ordered list of valid start datetimes.
    """
    required_slots = calculate_required_slots(job.duration_minutes, time_step_minutes)
    candidates: List[datetime] = []

    for p in carbon_grid.points:
        slot = p.timestamp
        # Slot cannot start before job has arrived
        if slot < job.arrival_time:
            continue
        # Job must finish on or before its deadline
        if (slot + job.duration_timedelta) > job.deadline:
            continue
        # Verify all contiguous slots required for execution capacity are present in grid
        slots = carbon_grid.get_interval_points(slot, required_slots)
        if len(slots) == required_slots:
            candidates.append(slot)

    return candidates
