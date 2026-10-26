"""
Data models and schemas for the Carbonova Scheduling Engine.

Defines Pydantic models for jobs, scheduling options, feasibility statuses,
decision records, and policy specifications.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class PolicyType(str, Enum):
    FIFO = "fifo"
    NAIVE_GREEN = "naive_green"
    CARBONOVA = "carbonova"
    ORACLE = "oracle"


class JobOrdering(str, Enum):
    EARLIEST_ARRIVAL_FIRST = "earliest_arrival_first"
    LEAST_DEADLINE_SLACK_FIRST = "least_deadline_slack_first"


class FeasibilityStatus(str, Enum):
    SCHEDULED = "scheduled"
    INITIALLY_INFEASIBLE = "initially_infeasible"
    CAPACITY_INFEASIBLE = "capacity_infeasible"


class MarginUnit(str, Enum):
    """
    Defines the unit semantics for Carbonova's min_improvement_margin:
      - RELATIVE_PERCENTAGE: dimensionless fraction [0.0, 1.0], e.g. 0.05 = 5% relative reduction.
      - ABSOLUTE_SCORE: risk score reduction in gCO2eq/kWh, e.g. 15.0 gCO2eq/kWh.
    """
    RELATIVE_PERCENTAGE = "relative_percentage"
    ABSOLUTE_SCORE = "absolute_score"


class Job(BaseModel):
    """
    Workload job specification for scheduling.
    """
    job_id: str = Field(..., min_length=1, description="Unique job identifier.")
    job_type: str = Field(default="training", description="Type of workload (e.g. training, batch_inference).")
    arrival_time: datetime = Field(..., description="Job arrival/submission time in UTC.")
    deadline: datetime = Field(..., description="Hard deadline for completion in UTC.")
    duration_minutes: int = Field(..., gt=0, description="Execution duration in minutes (must be > 0).")
    energy_kwh: float = Field(..., gt=0.0, description="Estimated total energy consumption in kWh.")
    priority: int = Field(default=1, ge=1, description="Priority level (1=normal, higher=more urgent).")
    deferrable: bool = Field(default=True, description="Whether the job can be delayed for carbon optimization.")
    resource_requirement: float = Field(default=1.0, gt=0.0, description="Resource units required (e.g., GPUs).")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata.")

    @field_validator("arrival_time", "deadline")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_times(self) -> Job:
        if self.deadline <= self.arrival_time:
            raise ValueError(
                f"Job deadline ({self.deadline.isoformat()}) must be strictly later "
                f"than arrival_time ({self.arrival_time.isoformat()})."
            )
        return self

    @property
    def duration_timedelta(self) -> timedelta:
        return timedelta(minutes=self.duration_minutes)

    def is_initially_feasible(
        self,
        cluster_capacity: float,
        time_step_minutes: Optional[int] = None,
    ) -> bool:
        """
        A job is initially infeasible if:
        1. Its duration is strictly longer than the continuous interval between arrival and deadline.
        2. Its resource requirement exceeds the total cluster capacity.
        3. If time_step_minutes is given: when snapped to discrete slot grid, its finish time exceeds deadline.
        """
        available_window = (self.deadline - self.arrival_time).total_seconds() / 60.0
        if self.duration_minutes > available_window:
            return False
        if self.resource_requirement > cluster_capacity:
            return False
        if time_step_minutes is not None:
            from backend.scheduler.time_grid import align_to_next_slot
            earliest_slot = align_to_next_slot(self.arrival_time, time_step_minutes)
            if (earliest_slot + self.duration_timedelta) > self.deadline:
                return False
        return True

    def calculate_deadline_slack_minutes(self, reference_time: Optional[datetime] = None) -> float:
        """
        Calculates slack relative to reference_time (or arrival_time if None):
        slack = (deadline - reference_time) - duration_minutes
        """
        ref = reference_time or self.arrival_time
        window_minutes = (self.deadline - ref).total_seconds() / 60.0
        return window_minutes - self.duration_minutes


class DecisionRecord(BaseModel):
    """
    Explainable audit record for every scheduling decision made for a job.
    """
    job_id: str
    policy: PolicyType
    feasibility_status: FeasibilityStatus
    scheduled_start: Optional[datetime] = None
    scheduled_finish: Optional[datetime] = None
    earliest_feasible_start: Optional[datetime] = None
    predicted_carbon_intensity: Optional[float] = None
    slot_uncertainty: Optional[float] = None
    risk_score: Optional[float] = None
    earliest_risk_score: Optional[float] = None
    improvement_pct: Optional[float] = None
    improvement_score: Optional[float] = Field(
        default=None,
        description="Absolute risk score reduction in gCO2eq/kWh vs earliest slot."
    )
    waiting_time_minutes: Optional[float] = None
    deadline_slack_minutes: Optional[float] = None
    ordering_index: int = 0
    reason: str = ""
    unscheduled_reason: Optional[str] = None

    @field_validator("scheduled_start", "scheduled_finish", "earliest_feasible_start")
    @classmethod
    def ensure_utc_optional(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class ClusterConfig(BaseModel):
    """
    Cluster environment configuration for resource capacity and time discretization.
    """
    total_capacity: float = Field(default=4.0, gt=0.0, description="Total cluster resource capacity (e.g., 4 GPUs).")
    time_step_minutes: int = Field(default=60, gt=0, description="Discrete time grid resolution in minutes.")


class SchedulerConfig(BaseModel):
    """
    Configurable parameters for scheduling policies.
    """
    policy: PolicyType = Field(default=PolicyType.CARBONOVA, description="Target policy to evaluate.")
    job_ordering: JobOrdering = Field(
        default=JobOrdering.EARLIEST_ARRIVAL_FIRST,
        description="Job sorting strategy (EAF or LDSF)."
    )
    risk_lambda: float = Field(
        default=0.5,
        ge=0.0,
        description="Non-negative uncertainty penalty multiplier (lambda) for Carbonova risk score."
    )
    min_improvement_margin: float = Field(
        default=0.05,
        ge=0.0,
        description="Minimum improvement required to justify delaying a job. In relative_percentage mode, "
                    "0.05 represents a 5% reduction. In absolute_score mode, this is in gCO2eq/kWh."
    )
    margin_unit: MarginUnit = Field(
        default=MarginUnit.RELATIVE_PERCENTAGE,
        description="Units for min_improvement_margin: 'relative_percentage' or 'absolute_score'."
    )
    cluster: ClusterConfig = Field(default_factory=ClusterConfig)


class ScheduleBatchRequest(BaseModel):
    """
    Request payload for scheduling a batch of jobs.
    """
    jobs: List[Job] = Field(..., min_length=1, description="List of jobs to schedule.")
    config: SchedulerConfig = Field(default_factory=SchedulerConfig)

    @model_validator(mode="after")
    def validate_unique_job_ids(self) -> ScheduleBatchRequest:
        seen = set()
        duplicates = set()
        for j in self.jobs:
            if j.job_id in seen:
                duplicates.add(j.job_id)
            seen.add(j.job_id)
        if duplicates:
            raise ValueError(f"Duplicate job IDs found in batch: {sorted(list(duplicates))}")
        return self


class PolicyScheduleResult(BaseModel):
    """
    The full schedule and metric outcome for a single policy.
    """
    policy: PolicyType
    job_ordering: JobOrdering
    decisions: List[DecisionRecord]
    metrics: Dict[str, Any] = Field(default_factory=dict)


class MultiPolicyScheduleResponse(BaseModel):
    """
    Response model containing results across all executed policies and comparative baselines.
    """
    time_step_minutes: int
    cluster_capacity: float
    results: Dict[str, PolicyScheduleResult]
    comparative_summary: Dict[str, Any] = Field(default_factory=dict)
