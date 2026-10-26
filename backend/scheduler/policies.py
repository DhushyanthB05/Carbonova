"""
Scheduling Policy Implementations.

Implements all four core scheduling policies under a unified feasibility and capacity framework:
1. FIFO / Earliest-Feasible
2. Naive-Green (Forecast-greedy without uncertainty)
3. Carbonova Uncertainty-Aware (Risk score with configurable minimum-improvement margin)
4. Perfect-Forecast Greedy Oracle (Using realized carbon observations)

Forecast Isolation Guarantee:
FIFO, Naive-Green, and Carbonova policies strictly call `compute_forecast_interval_stats`
and NEVER access realized_carbon_intensity.
Only the Oracle policy accesses `compute_realized_interval_stats`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Tuple

from backend.carbon.interface import CarbonGrid
from backend.scheduler.capacity import CapacityTracker
from backend.scheduler.models import (
    ClusterConfig,
    DecisionRecord,
    FeasibilityStatus,
    Job,
    MarginUnit,
    PolicyScheduleResult,
    PolicyType,
    SchedulerConfig,
)
from backend.scheduler.time_grid import align_to_next_slot, calculate_required_slots, get_candidate_start_slots


def compute_forecast_interval_stats(
    carbon_grid: CarbonGrid,
    start_time: datetime,
    duration_slots: int,
) -> Tuple[float, float]:
    """
    Computes (avg_predicted, avg_uncertainty) over [start_time, start_time + duration_slots).
    STRICT FORECAST ISOLATION: Never accesses realized_carbon_intensity.
    """
    points = carbon_grid.get_interval_points(start_time, duration_slots)
    if not points or len(points) != duration_slots:
        raise ValueError(f"Incomplete carbon grid for interval starting at {start_time.isoformat()}")

    avg_pred = sum(p.predicted_carbon_intensity for p in points) / duration_slots
    avg_unc = sum(p.slot_specific_uncertainty for p in points) / duration_slots
    return avg_pred, avg_unc


def compute_realized_interval_stats(
    carbon_grid: CarbonGrid,
    start_time: datetime,
    duration_slots: int,
) -> float:
    """
    Computes avg_realized over [start_time, start_time + duration_slots).
    STRICTLY RESTRICTED TO ORACLE AND POST-HOC EVALUATION.
    """
    points = carbon_grid.get_interval_points(start_time, duration_slots)
    if not points or len(points) != duration_slots:
        raise ValueError(f"Incomplete carbon grid for interval starting at {start_time.isoformat()}")

    realized_vals = [p.realized_carbon_intensity for p in points]
    if any(v is None for v in realized_vals):
        raise ValueError(f"Realized carbon intensity missing in carbon grid starting at {start_time.isoformat()}")

    return sum(v for v in realized_vals if v is not None) / duration_slots


def evaluate_job_feasibility(
    job: Job,
    carbon_grid: CarbonGrid,
    capacity_tracker: CapacityTracker,
    time_step_minutes: int,
) -> Tuple[FeasibilityStatus, List[datetime], Optional[str]]:
    """
    Evaluates whether a job is initially feasible and returns all currently capacity-feasible slots.
    """
    if not job.is_initially_feasible(capacity_tracker.total_capacity, time_step_minutes):
        window_minutes = (job.deadline - job.arrival_time).total_seconds() / 60.0
        if job.duration_minutes > window_minutes:
            reason = f"Job duration ({job.duration_minutes}m) exceeds submission-to-deadline window ({window_minutes:.0f}m)."
        elif job.resource_requirement > capacity_tracker.total_capacity:
            reason = f"Job resource requirement ({job.resource_requirement}) exceeds cluster capacity ({capacity_tracker.total_capacity})."
        else:
            earliest = align_to_next_slot(job.arrival_time, time_step_minutes)
            reason = (
                f"Job aligned to grid slot ({earliest.strftime('%H:%M')}) cannot complete duration "
                f"({job.duration_minutes}m) before deadline ({job.deadline.strftime('%H:%M')})."
            )
        return FeasibilityStatus.INITIALLY_INFEASIBLE, [], reason

    candidates = get_candidate_start_slots(job, carbon_grid, time_step_minutes)
    if not candidates:
        return FeasibilityStatus.INITIALLY_INFEASIBLE, [], "Insufficient carbon forecast coverage within job deadline window."

    required_slots = calculate_required_slots(job.duration_minutes, time_step_minutes)
    feasible_slots = [
        slot for slot in candidates
        if capacity_tracker.can_accommodate(slot, required_slots, job.resource_requirement)
    ]

    if not feasible_slots:
        return FeasibilityStatus.CAPACITY_INFEASIBLE, [], "All time slots within deadline window lack sufficient cluster capacity."

    return FeasibilityStatus.SCHEDULED, feasible_slots, None


def run_fifo_policy(
    ordered_jobs: Sequence[Job],
    carbon_grid: CarbonGrid,
    scheduler_config: SchedulerConfig,
) -> PolicyScheduleResult:
    """
    FIFO / Earliest-Feasible Policy:
    Schedules each job at its earliest feasible slot respecting capacity.
    """
    tracker = CapacityTracker(
        total_capacity=scheduler_config.cluster.total_capacity,
        time_step_minutes=scheduler_config.cluster.time_step_minutes,
    )
    time_step = scheduler_config.cluster.time_step_minutes
    decisions: List[DecisionRecord] = []

    for idx, job in enumerate(ordered_jobs):
        status, feasible_slots, unscheduled_reason = evaluate_job_feasibility(
            job, carbon_grid, tracker, time_step
        )
        slack_min = job.calculate_deadline_slack_minutes()

        if status != FeasibilityStatus.SCHEDULED or not feasible_slots:
            decisions.append(
                DecisionRecord(
                    job_id=job.job_id,
                    policy=PolicyType.FIFO,
                    feasibility_status=status,
                    ordering_index=idx,
                    deadline_slack_minutes=slack_min,
                    reason=f"Unscheduled: {unscheduled_reason}",
                    unscheduled_reason=unscheduled_reason,
                )
            )
            continue

        chosen_start = feasible_slots[0]
        req_slots = calculate_required_slots(job.duration_minutes, time_step)
        chosen_finish = chosen_start + job.duration_timedelta
        tracker.reserve(job.job_id, chosen_start, req_slots, job.resource_requirement)

        pred_ci, unc = compute_forecast_interval_stats(carbon_grid, chosen_start, req_slots)
        waiting_min = (chosen_start - job.arrival_time).total_seconds() / 60.0

        decisions.append(
            DecisionRecord(
                job_id=job.job_id,
                policy=PolicyType.FIFO,
                feasibility_status=FeasibilityStatus.SCHEDULED,
                scheduled_start=chosen_start,
                scheduled_finish=chosen_finish,
                earliest_feasible_start=chosen_start,
                predicted_carbon_intensity=round(pred_ci, 2),
                slot_uncertainty=round(unc, 2),
                risk_score=round(pred_ci, 2),
                earliest_risk_score=round(pred_ci, 2),
                improvement_pct=0.0,
                improvement_score=0.0,
                waiting_time_minutes=round(waiting_min, 1),
                deadline_slack_minutes=round(slack_min, 1),
                ordering_index=idx,
                reason="Scheduled at earliest feasible slot under FIFO policy.",
            )
        )

    return PolicyScheduleResult(
        policy=PolicyType.FIFO,
        job_ordering=scheduler_config.job_ordering,
        decisions=decisions,
    )


def run_naive_green_policy(
    ordered_jobs: Sequence[Job],
    carbon_grid: CarbonGrid,
    scheduler_config: SchedulerConfig,
) -> PolicyScheduleResult:
    """
    Naive-Green Policy:
    Forecast-greedy policy choosing slot with lowest predicted carbon intensity.
    Ignores uncertainty and does not apply a minimum improvement margin.
    """
    tracker = CapacityTracker(
        total_capacity=scheduler_config.cluster.total_capacity,
        time_step_minutes=scheduler_config.cluster.time_step_minutes,
    )
    time_step = scheduler_config.cluster.time_step_minutes
    decisions: List[DecisionRecord] = []

    for idx, job in enumerate(ordered_jobs):
        status, feasible_slots, unscheduled_reason = evaluate_job_feasibility(
            job, carbon_grid, tracker, time_step
        )
        slack_min = job.calculate_deadline_slack_minutes()

        if status != FeasibilityStatus.SCHEDULED or not feasible_slots:
            decisions.append(
                DecisionRecord(
                    job_id=job.job_id,
                    policy=PolicyType.NAIVE_GREEN,
                    feasibility_status=status,
                    ordering_index=idx,
                    deadline_slack_minutes=slack_min,
                    reason=f"Unscheduled: {unscheduled_reason}",
                    unscheduled_reason=unscheduled_reason,
                )
            )
            continue

        req_slots = calculate_required_slots(job.duration_minutes, time_step)
        earliest_start = feasible_slots[0]
        earliest_pred, earliest_unc = compute_forecast_interval_stats(carbon_grid, earliest_start, req_slots)

        best_slot = earliest_start
        best_pred = earliest_pred
        best_unc = earliest_unc

        for slot in feasible_slots:
            pred_ci, unc = compute_forecast_interval_stats(carbon_grid, slot, req_slots)
            if pred_ci < best_pred:
                best_pred = pred_ci
                best_slot = slot
                best_unc = unc

        chosen_finish = best_slot + job.duration_timedelta
        tracker.reserve(job.job_id, best_slot, req_slots, job.resource_requirement)

        waiting_min = (best_slot - job.arrival_time).total_seconds() / 60.0
        score_diff = max(0.0, earliest_pred - best_pred)
        improvement_pct = ((score_diff / earliest_pred) * 100.0) if earliest_pred > 0 else 0.0

        if best_slot == earliest_start:
            reason = "Selected earliest feasible slot (predicted carbon intensity is optimal or tied)."
        else:
            reason = (
                f"Delayed by {waiting_min:.0f}m to slot {best_slot.strftime('%H:%M')} for lower predicted "
                f"carbon intensity ({best_pred:.1f} vs {earliest_pred:.1f} gCO2eq/kWh, reduction: {improvement_pct:.1f}%)."
            )

        decisions.append(
            DecisionRecord(
                job_id=job.job_id,
                policy=PolicyType.NAIVE_GREEN,
                feasibility_status=FeasibilityStatus.SCHEDULED,
                scheduled_start=best_slot,
                scheduled_finish=chosen_finish,
                earliest_feasible_start=earliest_start,
                predicted_carbon_intensity=round(best_pred, 2),
                slot_uncertainty=round(best_unc, 2),
                risk_score=round(best_pred, 2),
                earliest_risk_score=round(earliest_pred, 2),
                improvement_pct=round(improvement_pct, 2),
                improvement_score=round(score_diff, 2),
                waiting_time_minutes=round(waiting_min, 1),
                deadline_slack_minutes=round(slack_min, 1),
                ordering_index=idx,
                reason=reason,
            )
        )

    return PolicyScheduleResult(
        policy=PolicyType.NAIVE_GREEN,
        job_ordering=scheduler_config.job_ordering,
        decisions=decisions,
    )


def run_carbonova_policy(
    ordered_jobs: Sequence[Job],
    carbon_grid: CarbonGrid,
    scheduler_config: SchedulerConfig,
) -> PolicyScheduleResult:
    """
    Carbonova Uncertainty-Aware Policy:
    Calculates risk_score = predicted_carbon + lambda_risk * slot_specific_uncertainty.
    Delays flexible jobs ONLY if risk reduction satisfies configurable min_improvement_margin.
    Supports both RELATIVE_PERCENTAGE and ABSOLUTE_SCORE margin units.
    Non-deferrable or urgent jobs execute at earliest feasible slot.
    """
    tracker = CapacityTracker(
        total_capacity=scheduler_config.cluster.total_capacity,
        time_step_minutes=scheduler_config.cluster.time_step_minutes,
    )
    time_step = scheduler_config.cluster.time_step_minutes
    risk_lambda = scheduler_config.risk_lambda
    min_margin = scheduler_config.min_improvement_margin
    margin_unit = scheduler_config.margin_unit
    decisions: List[DecisionRecord] = []

    for idx, job in enumerate(ordered_jobs):
        status, feasible_slots, unscheduled_reason = evaluate_job_feasibility(
            job, carbon_grid, tracker, time_step
        )
        slack_min = job.calculate_deadline_slack_minutes()

        if status != FeasibilityStatus.SCHEDULED or not feasible_slots:
            decisions.append(
                DecisionRecord(
                    job_id=job.job_id,
                    policy=PolicyType.CARBONOVA,
                    feasibility_status=status,
                    ordering_index=idx,
                    deadline_slack_minutes=slack_min,
                    reason=f"Unscheduled: {unscheduled_reason}",
                    unscheduled_reason=unscheduled_reason,
                )
            )
            continue

        req_slots = calculate_required_slots(job.duration_minutes, time_step)
        earliest_start = feasible_slots[0]
        e_pred, e_unc = compute_forecast_interval_stats(carbon_grid, earliest_start, req_slots)
        earliest_risk = e_pred + risk_lambda * e_unc

        # Evaluate risk score across all feasible candidate slots
        best_slot = earliest_start
        best_risk = earliest_risk
        best_pred = e_pred
        best_unc = e_unc

        for slot in feasible_slots:
            pred, unc = compute_forecast_interval_stats(carbon_grid, slot, req_slots)
            risk = pred + risk_lambda * unc
            # Strict inequality to favor earlier slots on ties
            if risk < best_risk:
                best_risk = risk
                best_slot = slot
                best_pred = pred
                best_unc = unc

        score_diff = max(0.0, earliest_risk - best_risk)
        improvement_score = round(score_diff, 4)
        improvement_fraction = (score_diff / earliest_risk) if earliest_risk > 0 else 0.0
        improvement_pct = round(improvement_fraction * 100.0, 2)

        # Margin unit evaluation
        if margin_unit == MarginUnit.ABSOLUTE_SCORE:
            meets_margin = improvement_score >= min_margin
            threshold_label = f"{min_margin:.2f} gCO2eq/kWh"
            actual_label = f"{improvement_score:.2f} gCO2eq/kWh"
        else:  # RELATIVE_PERCENTAGE
            meets_margin = improvement_fraction >= min_margin
            threshold_label = f"{min_margin * 100.0:.1f}%"
            actual_label = f"{improvement_pct:.1f}%"

        # Decision rule logic
        if not job.deferrable:
            chosen_start = earliest_start
            chosen_pred = e_pred
            chosen_unc = e_unc
            chosen_risk = earliest_risk
            decision_reason = "Non-deferrable job executed immediately at earliest feasible slot."
        elif best_slot == earliest_start:
            chosen_start = earliest_start
            chosen_pred = e_pred
            chosen_unc = e_unc
            chosen_risk = earliest_risk
            decision_reason = f"Earliest feasible slot offers lowest uncertainty-penalized risk score ({earliest_risk:.1f} gCO2eq/kWh)."
        elif meets_margin:
            chosen_start = best_slot
            chosen_pred = best_pred
            chosen_unc = best_unc
            chosen_risk = best_risk
            waiting_min = (best_slot - job.arrival_time).total_seconds() / 60.0
            decision_reason = (
                f"Delayed by {waiting_min:.0f}m to slot {best_slot.strftime('%H:%M')} for {actual_label} "
                f"risk reduction (meets {threshold_label} margin, risk {best_risk:.1f} vs {earliest_risk:.1f} gCO2eq/kWh)."
            )
        else:
            chosen_start = earliest_start
            chosen_pred = e_pred
            chosen_unc = e_unc
            chosen_risk = earliest_risk
            decision_reason = (
                f"Potential risk reduction ({actual_label}) below {threshold_label} margin; "
                f"scheduled at earliest slot to avoid uncertain delay."
            )

        chosen_finish = chosen_start + job.duration_timedelta
        tracker.reserve(job.job_id, chosen_start, req_slots, job.resource_requirement)
        waiting_min = (chosen_start - job.arrival_time).total_seconds() / 60.0

        decisions.append(
            DecisionRecord(
                job_id=job.job_id,
                policy=PolicyType.CARBONOVA,
                feasibility_status=FeasibilityStatus.SCHEDULED,
                scheduled_start=chosen_start,
                scheduled_finish=chosen_finish,
                earliest_feasible_start=earliest_start,
                predicted_carbon_intensity=round(chosen_pred, 2),
                slot_uncertainty=round(chosen_unc, 2),
                risk_score=round(chosen_risk, 2),
                earliest_risk_score=round(earliest_risk, 2),
                improvement_pct=round(improvement_pct, 2),
                improvement_score=round(improvement_score, 2),
                waiting_time_minutes=round(waiting_min, 1),
                deadline_slack_minutes=round(slack_min, 1),
                ordering_index=idx,
                reason=decision_reason,
            )
        )

    return PolicyScheduleResult(
        policy=PolicyType.CARBONOVA,
        job_ordering=scheduler_config.job_ordering,
        decisions=decisions,
    )


def run_oracle_policy(
    ordered_jobs: Sequence[Job],
    carbon_grid: CarbonGrid,
    scheduler_config: SchedulerConfig,
) -> PolicyScheduleResult:
    """
    Perfect-Forecast Greedy Oracle:
    Selects slot with minimum REALIZED carbon intensity.
    Strictly isolated for post-hoc benchmark comparison.
    Greedy heuristic under common capacity and ordering constraints (not global MIP).
    """
    tracker = CapacityTracker(
        total_capacity=scheduler_config.cluster.total_capacity,
        time_step_minutes=scheduler_config.cluster.time_step_minutes,
    )
    time_step = scheduler_config.cluster.time_step_minutes
    decisions: List[DecisionRecord] = []

    for idx, job in enumerate(ordered_jobs):
        status, feasible_slots, unscheduled_reason = evaluate_job_feasibility(
            job, carbon_grid, tracker, time_step
        )
        slack_min = job.calculate_deadline_slack_minutes()

        if status != FeasibilityStatus.SCHEDULED or not feasible_slots:
            decisions.append(
                DecisionRecord(
                    job_id=job.job_id,
                    policy=PolicyType.ORACLE,
                    feasibility_status=status,
                    ordering_index=idx,
                    deadline_slack_minutes=slack_min,
                    reason=f"Unscheduled: {unscheduled_reason}",
                    unscheduled_reason=unscheduled_reason,
                )
            )
            continue

        req_slots = calculate_required_slots(job.duration_minutes, time_step)
        earliest_start = feasible_slots[0]
        e_real = compute_realized_interval_stats(carbon_grid, earliest_start, req_slots)
        e_pred, e_unc = compute_forecast_interval_stats(carbon_grid, earliest_start, req_slots)

        best_slot = earliest_start
        best_real = e_real
        best_pred = e_pred
        best_unc = e_unc

        for slot in feasible_slots:
            real = compute_realized_interval_stats(carbon_grid, slot, req_slots)
            pred, unc = compute_forecast_interval_stats(carbon_grid, slot, req_slots)
            if real < best_real:
                best_real = real
                best_slot = slot
                best_pred = pred
                best_unc = unc

        chosen_finish = best_slot + job.duration_timedelta
        tracker.reserve(job.job_id, best_slot, req_slots, job.resource_requirement)

        waiting_min = (best_slot - job.arrival_time).total_seconds() / 60.0
        score_diff = max(0.0, e_real - best_real)
        improvement = ((score_diff / e_real) * 100.0) if e_real > 0 else 0.0

        if best_slot == earliest_start:
            reason = "Oracle selected earliest slot: lowest realized carbon intensity."
        else:
            reason = (
                f"Oracle selected slot {best_slot.strftime('%H:%M')} with realized carbon intensity "
                f"{best_real:.1f} gCO2eq/kWh (saved {improvement:.1f}% vs earliest slot realized {e_real:.1f} gCO2eq/kWh)."
            )

        decisions.append(
            DecisionRecord(
                job_id=job.job_id,
                policy=PolicyType.ORACLE,
                feasibility_status=FeasibilityStatus.SCHEDULED,
                scheduled_start=best_slot,
                scheduled_finish=chosen_finish,
                earliest_feasible_start=earliest_start,
                predicted_carbon_intensity=round(best_pred, 2),
                slot_uncertainty=round(best_unc, 2),
                risk_score=round(best_real, 2),
                earliest_risk_score=round(e_real, 2),
                improvement_pct=round(improvement, 2),
                improvement_score=round(score_diff, 2),
                waiting_time_minutes=round(waiting_min, 1),
                deadline_slack_minutes=round(slack_min, 1),
                ordering_index=idx,
                reason=reason,
            )
        )

    return PolicyScheduleResult(
        policy=PolicyType.ORACLE,
        job_ordering=scheduler_config.job_ordering,
        decisions=decisions,
    )
