"""
In-Memory Storage Store for Jobs and Scheduling History.

Provides clean, lightweight in-memory storage for submitted jobs,
active carbon grids, and run results without heavy external database dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from backend.carbon.interface import CarbonGrid
from backend.carbon.synthetic import SyntheticCarbonDataProvider
from backend.scheduler.models import Job, MultiPolicyScheduleResponse


class InMemoryStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._runs: List[Dict] = []
        self._carbon_provider = SyntheticCarbonDataProvider()

    def add_jobs(self, jobs: List[Job]) -> List[Job]:
        for j in jobs:
            self._jobs[j.job_id] = j
        return list(self._jobs.values())

    def get_all_jobs(self) -> List[Job]:
        return list(self._jobs.values())

    def clear_jobs(self) -> None:
        self._jobs.clear()

    def record_run(
        self,
        response: MultiPolicyScheduleResponse,
        job_count: int,
    ) -> Dict:
        run_record = {
            "run_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "job_count": job_count,
            "response": response.model_dump(),
        }
        self._runs.append(run_record)
        return run_record

    def get_runs(self, limit: int = 10) -> List[Dict]:
        return list(reversed(self._runs[-limit:]))

    def get_default_carbon_grid(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        time_step_minutes: int = 60,
    ) -> CarbonGrid:
        from datetime import timedelta
        start = start_time or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        end = end_time or (start + timedelta(hours=48))
        return self._carbon_provider.get_carbon_grid(start, end, time_step_minutes)


# Global singleton instance
store = InMemoryStore()
