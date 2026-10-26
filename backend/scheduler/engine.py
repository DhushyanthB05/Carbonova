"""
Workload Scheduling Engine for Carbonova.

Implements:
  1. FIFOScheduler: Deterministic First-In-First-Out baseline respecting arrival order,
     execution durations, and strict completion deadlines.
  2. CarbonovaScheduler: Conservative carbon-aware immediate-dispatch policy integrating
     with CarbonForecastService to query one-step-ahead forecasts and nominal 90% conformal bounds.
  3. WorkloadScheduler: Unified coordinator providing a direct Python interface for
     both policies.

Capacity Modeling Notice:
  This initial implementation models sequential single-stream queue dispatch. It rigorously
  enforces job arrival sequencing, durations, and deadlines, but does not claim to model
  multi-node GPU cluster topologies, memory bandwidth constraints, or concurrent multi-tenant
  sharing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple, Union

from backend.carbon.schemas import CarbonForecastResponse
from backend.carbon.service import CarbonForecastService
from backend.scheduler.schemas import DecisionType, SchedulingDecision, WorkloadJob


class FIFOScheduler:
    """
    Deterministic FIFO baseline scheduler.
    Processes workloads strictly in order of arrival timestamp.
    """

    POLICY_NAME: str = "FIFO"

    def schedule(
        self,
        jobs: List[WorkloadJob],
        queue_start_time_utc: Optional[datetime] = None,
    ) -> List[SchedulingDecision]:
        """
        Schedule a batch of workloads using the FIFO policy.

        Parameters:
            jobs: List of WorkloadJob instances to schedule.
            queue_start_time_utc: Optional starting availability time of the execution queue.
                                  Defaults to the arrival time of the earliest job.

        Returns:
            List of SchedulingDecision records corresponding to each job.
        """
        if not jobs:
            return []

        # Sort jobs chronologically by arrival time (stable sort preserves submission order)
        sorted_jobs = sorted(jobs, key=lambda j: j.arrival_time_utc)

        decisions: List[SchedulingDecision] = []
        current_available_time: Optional[datetime] = (
            queue_start_time_utc.astimezone(timezone.utc)
            if queue_start_time_utc
            else None
        )

        for job in sorted_jobs:
            # Earliest start is the maximum of job arrival and current queue availability
            if current_available_time is None:
                start_time = job.arrival_time_utc
            else:
                start_time = max(job.arrival_time_utc, current_available_time)

            execution_duration = timedelta(minutes=30 * job.duration_half_hours)
            completion_time = start_time + execution_duration

            # Feasibility check against deadline
            if completion_time > job.deadline_time_utc:
                decisions.append(
                    SchedulingDecision(
                        job_id=job.job_id,
                        policy_name=self.POLICY_NAME,
                        decision=DecisionType.REJECTED_INFEASIBLE,
                        scheduled_start_utc=None,
                        scheduled_completion_utc=None,
                        reason=(
                            f"Infeasible schedule: queue delay pushes completion to "
                            f"{completion_time.isoformat()}, exceeding deadline {job.deadline_time_utc.isoformat()}."
                        ),
                        data_status="not_applicable",
                    )
                )
            else:
                decisions.append(
                    SchedulingDecision(
                        job_id=job.job_id,
                        policy_name=self.POLICY_NAME,
                        decision=DecisionType.SCHEDULED,
                        scheduled_start_utc=start_time,
                        scheduled_completion_utc=completion_time,
                        reason=(
                            f"Scheduled via FIFO at earliest available slot {start_time.isoformat()} "
                            f"(completes at {completion_time.isoformat()})."
                        ),
                        data_status="not_applicable",
                    )
                )
                current_available_time = completion_time

        return decisions


class CarbonovaScheduler:
    """
    Conservative Carbonova carbon-aware dispatch scheduler.

    Consumes CarbonForecastService to query one-step-ahead (next half-hour) forecasts
    and calibrated nominal 90% conformal uncertainty intervals.

    Carbon Savings & Dispatch Rationale:
      - Validated multi-step (24-48h) forecasting is not yet implemented.
      - Therefore, this policy does not compare the current interval with an unverified future
        prediction or claim guaranteed future carbon savings.
      - If data is insufficient to establish that delaying a job would yield verified lower emissions,
        the job is scheduled immediately at the earliest feasible slot to respect deadlines.
      - If carbon forecast data is unavailable, corrupted, or degraded, it falls back gracefully
        to conservative immediate dispatch with explicit status reporting.
    """

    POLICY_NAME: str = "Carbonova_Conservative"

    def __init__(self, carbon_service: Optional[CarbonForecastService] = None) -> None:
        self.carbon_service = carbon_service

    def schedule(
        self,
        jobs: List[WorkloadJob],
        history: Optional[Any] = None,
        queue_start_time_utc: Optional[datetime] = None,
    ) -> List[SchedulingDecision]:
        """
        Schedule a batch of workloads using the Carbonova policy.

        Parameters:
            jobs: List of WorkloadJob instances to schedule.
            history: Optional historical carbon intensity data (at least 336 intervals)
                     for generating next-half-hour predictions.
            queue_start_time_utc: Optional starting availability time of the execution queue.

        Returns:
            List of SchedulingDecision records.
        """
        if not jobs:
            return []

        # Sort jobs chronologically by arrival time
        sorted_jobs = sorted(jobs, key=lambda j: j.arrival_time_utc)

        # Attempt to obtain forecast for immediate slot if service and history are available
        forecast_response: Optional[CarbonForecastResponse] = None
        forecast_error: Optional[str] = None

        if self.carbon_service is not None and history is not None:
            try:
                forecast_response = self.carbon_service.predict_next_half_hour(history)
            except (ValueError, TypeError, FileNotFoundError) as err:
                # Operational data failure or file unavailability: graceful fallback to conservative dispatch
                forecast_error = str(err)
                forecast_response = None

        decisions: List[SchedulingDecision] = []
        current_available_time: Optional[datetime] = (
            queue_start_time_utc.astimezone(timezone.utc)
            if queue_start_time_utc
            else None
        )

        for job in sorted_jobs:
            if current_available_time is None:
                start_time = job.arrival_time_utc
            else:
                start_time = max(job.arrival_time_utc, current_available_time)

            execution_duration = timedelta(minutes=30 * job.duration_half_hours)
            completion_time = start_time + execution_duration

            # Feasibility check against deadline
            if completion_time > job.deadline_time_utc:
                decisions.append(
                    SchedulingDecision(
                        job_id=job.job_id,
                        policy_name=self.POLICY_NAME,
                        decision=DecisionType.REJECTED_INFEASIBLE,
                        scheduled_start_utc=None,
                        scheduled_completion_utc=None,
                        reason=(
                            f"Infeasible schedule: execution from {start_time.isoformat()} to "
                            f"{completion_time.isoformat()} exceeds deadline {job.deadline_time_utc.isoformat()}."
                        ),
                        data_status="not_applicable",
                    )
                )
                continue

            # Dispatch with carbon forecast if available
            if forecast_response is not None and forecast_response.slots:
                slot = forecast_response.slots[0]
                reason_msg = (
                    f"Dispatched immediately at earliest feasible slot {start_time.isoformat()} "
                    f"(completes at {completion_time.isoformat()}). "
                    f"Next-half-hour forecast is {slot.predicted_intensity_gco2_per_kwh:.2f} gCO2/kWh "
                    f"with nominal 90% conformal interval [{slot.lower_90_gco2_per_kwh:.2f}, {slot.upper_90_gco2_per_kwh:.2f}] gCO2/kWh. "
                    f"Job not deferred because verified multi-step trajectory is unavailable to establish future savings."
                )
                decisions.append(
                    SchedulingDecision(
                        job_id=job.job_id,
                        policy_name=self.POLICY_NAME,
                        decision=DecisionType.SCHEDULED,
                        scheduled_start_utc=start_time,
                        scheduled_completion_utc=completion_time,
                        predicted_carbon_intensity_gco2_per_kwh=slot.predicted_intensity_gco2_per_kwh,
                        lower_90_gco2_per_kwh=slot.lower_90_gco2_per_kwh,
                        upper_90_gco2_per_kwh=slot.upper_90_gco2_per_kwh,
                        uncertainty_width_gco2_per_kwh=slot.uncertainty_width_gco2_per_kwh,
                        reason=reason_msg,
                        data_status=forecast_response.data_status,
                    )
                )
            else:
                # Conservative fallback dispatch when forecast is unavailable or degraded
                fallback_reason = (
                    f"Dispatched immediately at earliest feasible slot {start_time.isoformat()} "
                    f"(completes at {completion_time.isoformat()}) under conservative fallback: "
                    f"carbon forecast unavailable or degraded ({forecast_error if forecast_error else 'no input history provided'})."
                )
                decisions.append(
                    SchedulingDecision(
                        job_id=job.job_id,
                        policy_name=self.POLICY_NAME,
                        decision=DecisionType.SCHEDULED,
                        scheduled_start_utc=start_time,
                        scheduled_completion_utc=completion_time,
                        predicted_carbon_intensity_gco2_per_kwh=None,
                        lower_90_gco2_per_kwh=None,
                        upper_90_gco2_per_kwh=None,
                        uncertainty_width_gco2_per_kwh=None,
                        reason=fallback_reason,
                        data_status="fallback_no_forecast",
                    )
                )

            current_available_time = completion_time

        return decisions


class WorkloadScheduler:
    """
    Unified scheduling engine supporting multiple dispatch policies.
    """

    def __init__(self, carbon_service: Optional[CarbonForecastService] = None) -> None:
        self.carbon_service = carbon_service
        self.fifo_policy = FIFOScheduler()
        self.carbonova_policy = CarbonovaScheduler(carbon_service=carbon_service)

    def schedule_fifo(
        self,
        jobs: List[WorkloadJob],
        queue_start_time_utc: Optional[datetime] = None,
    ) -> List[SchedulingDecision]:
        """Schedule workloads via FIFO policy."""
        return self.fifo_policy.schedule(jobs, queue_start_time_utc=queue_start_time_utc)

    def schedule_carbonova(
        self,
        jobs: List[WorkloadJob],
        history: Optional[Any] = None,
        queue_start_time_utc: Optional[datetime] = None,
    ) -> List[SchedulingDecision]:
        """Schedule workloads via conservative Carbonova policy."""
        return self.carbonova_policy.schedule(
            jobs,
            history=history,
            queue_start_time_utc=queue_start_time_utc,
        )
