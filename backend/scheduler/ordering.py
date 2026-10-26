"""
Workload Job Ordering Strategies.

Provides deterministic, reproducible sorting of submitted jobs:
1. Earliest-Arrival-First (EAF)
2. Least-Deadline-Slack-First (LDSF)

Includes stable secondary and tertiary tie-breakers using job IDs.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence

from backend.scheduler.models import Job, JobOrdering


def compute_job_slack_seconds(job: Job, reference_time: Optional[datetime] = None) -> float:
    """
    Computes deadline slack in seconds:
      slack = (deadline - decision_time) - duration
    If reference_time is None or earlier than arrival_time, uses arrival_time.
    """
    decision_time = job.arrival_time
    if reference_time is not None and reference_time > job.arrival_time:
        decision_time = reference_time

    window_seconds = (job.deadline - decision_time).total_seconds()
    duration_seconds = job.duration_minutes * 60.0
    return window_seconds - duration_seconds


def sort_jobs(
    jobs: Sequence[Job],
    ordering: JobOrdering = JobOrdering.EARLIEST_ARRIVAL_FIRST,
    reference_time: Optional[datetime] = None,
) -> List[Job]:
    """
    Sorts a sequence of jobs deterministically according to the selected strategy.

    Tie-breakers:
      - EAF: arrival_time ASC, deadline ASC, priority DESC, job_id ASC
      - LDSF: slack ASC, arrival_time ASC, priority DESC, job_id ASC
    """
    if ordering == JobOrdering.EARLIEST_ARRIVAL_FIRST:
        return sorted(
            jobs,
            key=lambda j: (
                j.arrival_time,
                j.deadline,
                -j.priority,
                j.job_id,
            ),
        )
    elif ordering == JobOrdering.LEAST_DEADLINE_SLACK_FIRST:
        return sorted(
            jobs,
            key=lambda j: (
                compute_job_slack_seconds(j, reference_time),
                j.arrival_time,
                -j.priority,
                j.job_id,
            ),
        )
    else:
        raise ValueError(f"Unsupported JobOrdering: {ordering}")
