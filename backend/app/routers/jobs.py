"""
Workload Jobs Submission Router.
"""

from typing import Any, Dict, List, Union
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.storage import store
from backend.scheduler.models import Job

router = APIRouter(prefix="/api", tags=["Jobs"])


class JobSubmissionResponse(BaseModel):
    message: str
    total_stored_jobs: int
    submitted_jobs: List[Job]
    initial_feasibility: Dict[str, bool]


@router.post("/jobs", response_model=JobSubmissionResponse)
def submit_jobs(
    jobs_input: Union[Job, List[Job]],
    cluster_capacity: float = Query(4.0, gt=0.0, description="Cluster capacity for initial feasibility check"),
):
    """
    Submits workload jobs to the backend session repository with validation.
    """
    job_list = [jobs_input] if isinstance(jobs_input, Job) else jobs_input

    # Check for duplicate job IDs within the submission
    seen = set()
    duplicates = set()
    for j in job_list:
        if j.job_id in seen:
            duplicates.add(j.job_id)
        seen.add(j.job_id)
    if duplicates:
        raise HTTPException(
            status_code=422,
            detail=f"Duplicate job IDs found in submission: {sorted(list(duplicates))}",
        )

    # Initial feasibility assessment
    feasibility_map = {
        j.job_id: j.is_initially_feasible(cluster_capacity)
        for j in job_list
    }

    # Store jobs
    updated_jobs = store.add_jobs(job_list)

    return JobSubmissionResponse(
        message=f"Successfully submitted and stored {len(job_list)} job(s).",
        total_stored_jobs=len(updated_jobs),
        submitted_jobs=job_list,
        initial_feasibility=feasibility_map,
    )


@router.get("/jobs", response_model=List[Job])
def list_jobs():
    """
    Lists all currently stored jobs in the backend session.
    """
    return store.get_all_jobs()


@router.delete("/jobs")
def clear_jobs():
    """
    Clears all stored jobs in the backend session.
    """
    store.clear_jobs()
    return {"message": "All session jobs cleared."}
