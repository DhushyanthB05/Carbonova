"""
Scheduling Execution and Results Router.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.storage import store
from backend.carbon.interface import CarbonGrid
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.models import (
    Job,
    MultiPolicyScheduleResponse,
    PolicyScheduleResult,
    SchedulerConfig,
)

router = APIRouter(prefix="/api/schedule", tags=["Schedule"])


class ScheduleRunRequest(BaseModel):
    jobs: Optional[List[Job]] = Field(
        default=None,
        description="Optional list of jobs. If omitted, currently stored session jobs are scheduled."
    )
    config: SchedulerConfig = Field(
        default_factory=SchedulerConfig,
        description="Scheduling configuration (policy, ordering, risk lambda, margin, cluster)."
    )
    run_all_policies: bool = Field(
        default=True,
        description="Whether to run all policies (FIFO, Naive, Carbonova, Oracle) for full comparative evaluation."
    )


@router.post("/run", response_model=MultiPolicyScheduleResponse)
def run_schedule(request: ScheduleRunRequest):
    """
    Executes scheduling for the specified jobs and returns detailed decisions,
    per-policy schedules, counterfactuals, and comparative metrics.
    """
    jobs_to_schedule = request.jobs or store.get_all_jobs()
    if not jobs_to_schedule:
        raise HTTPException(
            status_code=400,
            detail="No jobs provided in request and no jobs currently stored in session. Submit jobs first.",
        )

    # Determine required time window from jobs
    earliest_arrival = min(j.arrival_time for j in jobs_to_schedule)
    latest_deadline = max(j.deadline for j in jobs_to_schedule)

    carbon_grid = store.get_default_carbon_grid(
        start_time=earliest_arrival,
        end_time=latest_deadline,
        time_step_minutes=request.config.cluster.time_step_minutes,
    )

    if request.run_all_policies:
        response = SchedulingEngine.run_all_policies(
            jobs=jobs_to_schedule,
            carbon_grid=carbon_grid,
            config=request.config,
        )
    else:
        single_result = SchedulingEngine.run_policy(
            jobs=jobs_to_schedule,
            carbon_grid=carbon_grid,
            config=request.config,
        )
        response = MultiPolicyScheduleResponse(
            time_step_minutes=request.config.cluster.time_step_minutes,
            cluster_capacity=request.config.cluster.total_capacity,
            results={single_result.policy.value: single_result},
            comparative_summary={"single_policy_run": single_result.policy.value},
        )

    # Persist in run history
    store.record_run(response, len(jobs_to_schedule))
    return response


@router.get("/results", response_model=List[Dict[str, Any]])
def get_schedule_results(limit: int = Query(10, ge=1, le=100)):
    """
    Retrieves recent scheduling execution history.
    """
    return store.get_runs(limit=limit)
