"""
Cluster Resource Capacity Tracker.

Enforces resource limits over half-open time intervals [start, finish)
on a discrete time grid. Ensures that the sum of concurrent job resource demands
does not exceed cluster capacity at any discrete time step.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple


class CapacityTracker:
    """
    Tracks resource allocations (e.g. GPUs, CPU units) per discrete time slot.
    """

    def __init__(self, total_capacity: float, time_step_minutes: int = 60) -> None:
        if total_capacity <= 0:
            raise ValueError(f"total_capacity must be positive, got {total_capacity}")
        if time_step_minutes <= 0:
            raise ValueError(f"time_step_minutes must be positive, got {time_step_minutes}")

        self.total_capacity = float(total_capacity)
        self.time_step_minutes = time_step_minutes
        self._step = timedelta(minutes=time_step_minutes)
        # Mapping: slot_timestamp -> used_capacity
        self._usage: Dict[datetime, float] = {}
        # Mapping: slot_timestamp -> list of (job_id, allocated_amount)
        self._allocations: Dict[datetime, List[Tuple[str, float]]] = {}

    def get_used_capacity(self, slot: datetime) -> float:
        slot_utc = slot if slot.tzinfo else slot.replace(tzinfo=timezone.utc)
        return self._usage.get(slot_utc, 0.0)

    def get_available_capacity(self, slot: datetime) -> float:
        return max(0.0, self.total_capacity - self.get_used_capacity(slot))

    def can_accommodate(
        self,
        start_time: datetime,
        duration_slots: int,
        resource_req: float,
    ) -> bool:
        """
        Verifies whether sufficient capacity is available for all `duration_slots`
        starting from `start_time`.
        """
        if resource_req <= 0:
            return True
        if resource_req > self.total_capacity:
            return False

        slot = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        for _ in range(duration_slots):
            current_used = self._usage.get(slot, 0.0)
            # Floating point tolerance check
            if (current_used + resource_req) > (self.total_capacity + 1e-9):
                return False
            slot += self._step
        return True

    def reserve(
        self,
        job_id: str,
        start_time: datetime,
        duration_slots: int,
        resource_req: float,
    ) -> None:
        """
        Reserves capacity for a job across all specified slots.
        Raises ValueError if capacity is exceeded.
        """
        if not self.can_accommodate(start_time, duration_slots, resource_req):
            raise ValueError(
                f"Cannot reserve {resource_req} units for job {job_id} starting at "
                f"{start_time.isoformat()} for {duration_slots} slots: exceeds total capacity {self.total_capacity}."
            )

        slot = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        for _ in range(duration_slots):
            self._usage[slot] = round(self._usage.get(slot, 0.0) + resource_req, 6)
            if slot not in self._allocations:
                self._allocations[slot] = []
            self._allocations[slot].append((job_id, resource_req))
            slot += self._step

    def copy(self) -> CapacityTracker:
        """
        Creates a deep copy of the tracker state.
        """
        new_tracker = CapacityTracker(
            total_capacity=self.total_capacity,
            time_step_minutes=self.time_step_minutes,
        )
        new_tracker._usage = dict(self._usage)
        new_tracker._allocations = {k: list(v) for k, v in self._allocations.items()}
        return new_tracker
