"""
Pydantic Data Schemas for Carbonova Workload Scheduling.

Defines data contracts for:
  - WorkloadJob: AI compute workload specification including arrival, duration, deadline, and flexibility.
  - DecisionType: Enumeration of scheduling decisions (SCHEDULED, REJECTED_INFEASIBLE, DEFERRED).
  - SchedulingDecision: Formal scheduling decision record with timestamps, carbon forecasts, and rationales.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class DecisionType(str, Enum):
    """Enumeration of discrete scheduler decisions."""
    SCHEDULED = "SCHEDULED"
    REJECTED_INFEASIBLE = "REJECTED_INFEASIBLE"
    DEFERRED = "DEFERRED"


class WorkloadJob(BaseModel):
    """
    Representation of an AI workload job submitted to the Carbonova scheduler.
    """
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the workload job."
    )
    arrival_time_utc: datetime = Field(
        ...,
        description="Timestamp when the job arrives in the queue (in UTC)."
    )
    duration_half_hours: int = Field(
        ...,
        gt=0,
        description="Job execution duration in half-hour intervals (must be positive integer)."
    )
    deadline_time_utc: datetime = Field(
        ...,
        description="Strict completion deadline for the job (in UTC)."
    )
    resource_demand: float = Field(
        ...,
        gt=0.0,
        description="Compute or GPU resource demand (must be positive)."
    )
    is_flexible: bool = Field(
        default=True,
        description="Whether the workload can be delayed or green-shifted within its deadline window."
    )

    @field_validator("arrival_time_utc", "deadline_time_utc")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_job_feasibility_window(self) -> "WorkloadJob":
        if self.arrival_time_utc > self.deadline_time_utc:
            raise ValueError(
                f"Invalid job {self.job_id}: arrival_time_utc ({self.arrival_time_utc.isoformat()}) "
                f"is after deadline_time_utc ({self.deadline_time_utc.isoformat()})."
            )

        min_execution_time = timedelta(minutes=30 * self.duration_half_hours)
        earliest_possible_completion = self.arrival_time_utc + min_execution_time
        if earliest_possible_completion > self.deadline_time_utc:
            raise ValueError(
                f"Infeasible job {self.job_id}: duration of {self.duration_half_hours} intervals "
                f"({min_execution_time}) requires completion at {earliest_possible_completion.isoformat()}, "
                f"which exceeds deadline {self.deadline_time_utc.isoformat()}."
            )

        return self


class SchedulingDecision(BaseModel):
    """
    Formal scheduling decision produced by a scheduler policy for a specific workload job.
    """
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(
        ...,
        description="Identifier of the job being scheduled."
    )
    policy_name: str = Field(
        ...,
        description="Name of the scheduling policy that made this decision (e.g. 'FIFO', 'Carbonova_Conservative')."
    )
    decision: DecisionType = Field(
        ...,
        description="Action decision: SCHEDULED, REJECTED_INFEASIBLE, or DEFERRED."
    )
    scheduled_start_utc: Optional[datetime] = Field(
        default=None,
        description="Scheduled execution start time in UTC (None if rejected)."
    )
    scheduled_completion_utc: Optional[datetime] = Field(
        default=None,
        description="Scheduled completion time in UTC (None if rejected)."
    )
    predicted_carbon_intensity_gco2_per_kwh: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Predicted grid carbon intensity at scheduled start time (when forecast available)."
    )
    lower_90_gco2_per_kwh: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Lower bound of nominal 90% prediction interval in gCO2/kWh."
    )
    upper_90_gco2_per_kwh: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Upper bound of nominal 90% prediction interval in gCO2/kWh."
    )
    uncertainty_width_gco2_per_kwh: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Full width of nominal 90% prediction interval in gCO2/kWh."
    )
    reason: str = Field(
        ...,
        description="Detailed explanation of the scheduling decision."
    )
    data_status: str = Field(
        default="not_applicable",
        description="Status of carbon forecast data ('live', 'fallback_no_forecast', 'degraded', 'not_applicable')."
    )

    @field_validator("scheduled_start_utc", "scheduled_completion_utc")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_scheduled_timing(self) -> "SchedulingDecision":
        if self.decision == DecisionType.SCHEDULED:
            if self.scheduled_start_utc is None or self.scheduled_completion_utc is None:
                raise ValueError(
                    f"Scheduled decision for job {self.job_id} must specify scheduled_start_utc "
                    "and scheduled_completion_utc."
                )
            if self.scheduled_start_utc > self.scheduled_completion_utc:
                raise ValueError(
                    f"Scheduled start ({self.scheduled_start_utc.isoformat()}) cannot be after "
                    f"scheduled completion ({self.scheduled_completion_utc.isoformat()})."
                )
        return self
