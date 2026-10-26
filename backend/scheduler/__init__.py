"""
Carbonova Core Scheduling Engine.

Exports data models, policies, ordering strategies, time grid math,
capacity tracking, reusable evaluation metrics, and the main SchedulingEngine.
"""

from backend.scheduler.capacity import CapacityTracker
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.metrics import (
    calculate_job_emissions,
    compute_forecast_interval_coverage,
    compute_schedule_metrics,
)
from backend.scheduler.models import (
    ClusterConfig,
    DecisionRecord,
    FeasibilityStatus,
    Job,
    JobOrdering,
    MarginUnit,
    MultiPolicyScheduleResponse,
    PolicyScheduleResult,
    PolicyType,
    ScheduleBatchRequest,
    SchedulerConfig,
)
from backend.scheduler.ordering import compute_job_slack_seconds, sort_jobs
from backend.scheduler.policies import (
    compute_forecast_interval_stats,
    compute_realized_interval_stats,
    run_carbonova_policy,
    run_fifo_policy,
    run_naive_green_policy,
    run_oracle_policy,
)
from backend.scheduler.time_grid import (
    align_to_next_slot,
    align_to_prev_slot,
    calculate_required_slots,
    get_candidate_start_slots,
)

__all__ = [
    "CapacityTracker",
    "SchedulingEngine",
    "calculate_job_emissions",
    "compute_forecast_interval_coverage",
    "compute_schedule_metrics",
    "ClusterConfig",
    "DecisionRecord",
    "FeasibilityStatus",
    "Job",
    "JobOrdering",
    "MarginUnit",
    "MultiPolicyScheduleResponse",
    "PolicyScheduleResult",
    "PolicyType",
    "ScheduleBatchRequest",
    "SchedulerConfig",
    "compute_job_slack_seconds",
    "sort_jobs",
    "compute_forecast_interval_stats",
    "compute_realized_interval_stats",
    "run_carbonova_policy",
    "run_fifo_policy",
    "run_naive_green_policy",
    "run_oracle_policy",
    "align_to_next_slot",
    "align_to_prev_slot",
    "calculate_required_slots",
    "get_candidate_start_slots",
]
