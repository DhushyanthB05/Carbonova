"""
In-Memory Storage Store for Jobs and Scheduling History.

Provides clean, lightweight in-memory storage for submitted jobs,
active carbon grids, and run results without heavy external database dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from backend.carbon.interface import CarbonDataProvider, CarbonGrid
from backend.carbon.synthetic import SyntheticCarbonDataProvider
from backend.scheduler.models import Job, MultiPolicyScheduleResponse


class InMemoryStore:
    def __init__(self, carbon_provider: Optional[CarbonDataProvider] = None) -> None:
        self._jobs: Dict[str, Job] = {}
        self._runs: List[Dict] = []
        if carbon_provider is not None:
            self.set_carbon_provider(carbon_provider)
        else:
            self._carbon_provider: CarbonDataProvider = SyntheticCarbonDataProvider()

    def set_carbon_provider(self, provider: CarbonDataProvider) -> None:
        """
        Registers a custom CarbonDataProvider (e.g. Member 1's real grid data provider).
        Raises TypeError if provider does not implement the CarbonDataProvider interface.
        """
        if not isinstance(provider, CarbonDataProvider):
            raise TypeError(
                f"provider must be an instance of CarbonDataProvider, got {type(provider).__name__}"
            )
        self._carbon_provider = provider

    def get_carbon_provider(self) -> CarbonDataProvider:
        """
        Returns the currently active CarbonDataProvider instance.
        """
        return self._carbon_provider

    def reset_carbon_provider(self) -> None:
        """
        Resets the active provider to the default SyntheticCarbonDataProvider.
        """
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


def set_carbon_provider(provider: CarbonDataProvider) -> None:
    """Convenience wrapper to register a custom CarbonDataProvider on the global store."""
    store.set_carbon_provider(provider)


def get_carbon_provider() -> CarbonDataProvider:
    """Convenience wrapper to retrieve the active CarbonDataProvider from the global store."""
    return store.get_carbon_provider()


def reset_carbon_provider() -> None:
    """Convenience wrapper to reset the global store's provider to default SyntheticCarbonDataProvider."""
    store.reset_carbon_provider()
