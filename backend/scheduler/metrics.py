"""
Reusable Metric Calculation Functions for Carbonova Evaluation.

Provides rigorous, test-verified metric calculations for Member 3's evaluation runner:
- Total realized emissions
- Emissions reduction against named baselines
- Deadline success among feasible jobs
- Waiting-time summary statistics
- Backfire rate (handling zero delayed jobs as N/A)
- Predicted vs realized savings
- Oracle gap
- Forecast interval coverage

Methodology note:
Emissions are calculated as Job.energy_kwh * average_carbon_intensity.
Per-job counterfactual emissions evaluate each job at its earliest feasible start time.
"""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from backend.carbon.interface import CarbonGrid
from backend.scheduler.models import DecisionRecord, FeasibilityStatus, Job, PolicyScheduleResult
from backend.scheduler.time_grid import calculate_required_slots


COUNTERFACTUAL_DISCLOSURE = (
    "Per-job counterfactual emissions evaluate each job independently at its earliest feasible slot "
    "and do not represent a globally concurrent schedule under system-wide resource contention."
)


def calculate_job_emissions(
    job: Job,
    start_time: datetime,
    carbon_grid: CarbonGrid,
    use_realized: bool = True,
) -> float:
    """
    Computes total gCO2eq emissions for a job executing from start_time:
      Emissions (gCO2) = job.energy_kwh * avg_intensity (gCO2/kWh)
    """
    req_slots = calculate_required_slots(job.duration_minutes, carbon_grid.time_step_minutes)
    points = carbon_grid.get_interval_points(start_time, req_slots)
    if not points or len(points) != req_slots:
        raise ValueError(f"Incomplete grid for job {job.job_id} at {start_time}")

    if use_realized:
        realized_vals = [p.realized_carbon_intensity for p in points]
        if any(v is None for v in realized_vals):
            raise ValueError(f"Realized carbon intensity missing for job {job.job_id} at {start_time}")
        avg_ci = sum(v for v in realized_vals if v is not None) / req_slots
    else:
        avg_ci = sum(p.predicted_carbon_intensity for p in points) / req_slots

    return round(job.energy_kwh * avg_ci, 4)


def compute_schedule_metrics(
    jobs: Sequence[Job],
    schedule_result: PolicyScheduleResult,
    carbon_grid: CarbonGrid,
    baseline_result: Optional[PolicyScheduleResult] = None,
    oracle_result: Optional[PolicyScheduleResult] = None,
) -> Dict[str, Any]:
    """
    Computes all standard Carbonova evaluation metrics for a policy run.
    """
    jobs_by_id = {j.job_id: j for j in jobs}
    decisions_by_id = {d.job_id: d for d in schedule_result.decisions}

    initially_infeasible_ids: List[str] = []
    capacity_infeasible_ids: List[str] = []
    scheduled_ids: List[str] = []

    for d in schedule_result.decisions:
        if d.feasibility_status == FeasibilityStatus.INITIALLY_INFEASIBLE:
            initially_infeasible_ids.append(d.job_id)
        elif d.feasibility_status == FeasibilityStatus.CAPACITY_INFEASIBLE:
            capacity_infeasible_ids.append(d.job_id)
        elif d.feasibility_status == FeasibilityStatus.SCHEDULED:
            scheduled_ids.append(d.job_id)

    total_submitted = len(jobs)
    initially_feasible_count = total_submitted - len(initially_infeasible_ids)

    # Deadline success: scheduled jobs that finish before deadline
    deadline_success_count = 0
    for jid in scheduled_ids:
        job = jobs_by_id[jid]
        decision = decisions_by_id[jid]
        if decision.scheduled_finish and decision.scheduled_finish <= job.deadline:
            deadline_success_count += 1

    # Undefined ratio guard: if initially_feasible_count == 0, return None ("N/A")
    if initially_feasible_count > 0:
        deadline_success_rate: Optional[float] = round(deadline_success_count / initially_feasible_count * 100.0, 2)
        deadline_success_display = f"{deadline_success_rate}%"
    else:
        deadline_success_rate = None
        deadline_success_display = "N/A (No feasible jobs submitted)"

    # Realized emissions and counterfactuals
    total_realized_emissions = 0.0
    total_predicted_emissions = 0.0
    counterfactual_earliest_emissions = 0.0
    counterfactual_predicted_earliest = 0.0

    waiting_times: List[float] = []
    delayed_jobs_count = 0
    backfire_jobs_count = 0

    has_realized_data = True

    for jid in scheduled_ids:
        job = jobs_by_id[jid]
        decision = decisions_by_id[jid]
        if decision.waiting_time_minutes is not None:
            waiting_times.append(decision.waiting_time_minutes)

        try:
            # Scheduled emissions
            job_real_em = calculate_job_emissions(job, decision.scheduled_start, carbon_grid, use_realized=True)
            job_pred_em = calculate_job_emissions(job, decision.scheduled_start, carbon_grid, use_realized=False)
            total_realized_emissions += job_real_em
            total_predicted_emissions += job_pred_em

            # Earliest counterfactual emissions
            if decision.earliest_feasible_start:
                cf_real = calculate_job_emissions(job, decision.earliest_feasible_start, carbon_grid, use_realized=True)
                cf_pred = calculate_job_emissions(job, decision.earliest_feasible_start, carbon_grid, use_realized=False)
                counterfactual_earliest_emissions += cf_real
                counterfactual_predicted_earliest += cf_pred

                # Backfire check: delayed job with realized emissions higher than earliest run
                if decision.scheduled_start > decision.earliest_feasible_start:
                    delayed_jobs_count += 1
                    if job_real_em > cf_real:
                        backfire_jobs_count += 1
        except ValueError:
            has_realized_data = False

    # Backfire rate rule: When no jobs are delayed, backfire rate must be None ("N/A"), NOT 0.0%
    if delayed_jobs_count == 0:
        backfire_rate: Optional[float] = None
        backfire_rate_display = "N/A (No delayed jobs)"
    else:
        backfire_rate = round(backfire_jobs_count / delayed_jobs_count * 100.0, 2)
        backfire_rate_display = f"{backfire_rate}%"

    # Waiting time statistics
    if waiting_times:
        waiting_mean = round(statistics.mean(waiting_times), 2)
        waiting_median = round(statistics.median(waiting_times), 2)
        waiting_min = round(min(waiting_times), 2)
        waiting_max = round(max(waiting_times), 2)
    else:
        waiting_mean = waiting_median = waiting_min = waiting_max = None

    # Savings vs earliest counterfactual
    realized_savings_gco2 = round(counterfactual_earliest_emissions - total_realized_emissions, 2) if has_realized_data else None
    if has_realized_data and counterfactual_earliest_emissions > 0:
        realized_savings_pct: Optional[float] = round(realized_savings_gco2 / counterfactual_earliest_emissions * 100.0, 2)
    elif has_realized_data and counterfactual_earliest_emissions == 0:
        realized_savings_pct = 0.0
    else:
        realized_savings_pct = None

    predicted_savings_gco2 = round(counterfactual_predicted_earliest - total_predicted_emissions, 2)
    if counterfactual_predicted_earliest > 0:
        predicted_savings_pct: Optional[float] = round(predicted_savings_gco2 / counterfactual_predicted_earliest * 100.0, 2)
    else:
        predicted_savings_pct = 0.0

    metrics: Dict[str, Any] = {
        "total_jobs_submitted": total_submitted,
        "initially_feasible_jobs": initially_feasible_count,
        "initially_infeasible_jobs": len(initially_infeasible_ids),
        "initially_infeasible_job_ids": initially_infeasible_ids,
        "capacity_infeasible_jobs": len(capacity_infeasible_ids),
        "capacity_infeasible_job_ids": capacity_infeasible_ids,
        "scheduled_jobs_count": len(scheduled_ids),
        "deadline_success_count": deadline_success_count,
        "deadline_success_rate_pct": deadline_success_rate,
        "deadline_success_display": deadline_success_display,
        "total_realized_emissions_gco2": round(total_realized_emissions, 2) if has_realized_data else None,
        "total_predicted_emissions_gco2": round(total_predicted_emissions, 2),
        "counterfactual_earliest_emissions_gco2": round(counterfactual_earliest_emissions, 2) if has_realized_data else None,
        "realized_savings_vs_earliest_gco2": realized_savings_gco2,
        "realized_savings_vs_earliest_pct": realized_savings_pct,
        "predicted_savings_vs_earliest_gco2": predicted_savings_gco2,
        "predicted_savings_vs_earliest_pct": predicted_savings_pct,
        "delayed_jobs_count": delayed_jobs_count,
        "backfire_jobs_count": backfire_jobs_count,
        "backfire_rate_pct": backfire_rate,
        "backfire_rate_display": backfire_rate_display,
        "waiting_time_minutes": {
            "mean": waiting_mean,
            "median": waiting_median,
            "min": waiting_min,
            "max": waiting_max,
        },
        "notes": COUNTERFACTUAL_DISCLOSURE,
    }

    # Baseline comparison (e.g. vs FIFO)
    if baseline_result is not None:
        base_metrics = compute_schedule_metrics(jobs, baseline_result, carbon_grid)
        base_emissions = base_metrics.get("total_realized_emissions_gco2")
        if base_emissions is not None and has_realized_data and base_emissions > 0:
            reduction_gco2 = round(base_emissions - total_realized_emissions, 2)
            reduction_pct = round(reduction_gco2 / base_emissions * 100.0, 2)
            metrics["baseline_comparison"] = {
                "baseline_policy": baseline_result.policy.value,
                "baseline_emissions_gco2": base_emissions,
                "emissions_reduction_gco2": reduction_gco2,
                "emissions_reduction_pct": reduction_pct,
            }
        elif base_emissions == 0:
            metrics["baseline_comparison"] = {
                "baseline_policy": baseline_result.policy.value,
                "baseline_emissions_gco2": 0.0,
                "emissions_reduction_gco2": 0.0,
                "emissions_reduction_pct": 0.0,
            }

    # Oracle gap comparison
    if oracle_result is not None:
        oracle_metrics = compute_schedule_metrics(jobs, oracle_result, carbon_grid)
        oracle_emissions = oracle_metrics.get("total_realized_emissions_gco2")
        if oracle_emissions is not None and has_realized_data and oracle_emissions > 0:
            gap_gco2 = round(total_realized_emissions - oracle_emissions, 2)
            gap_pct = round(gap_gco2 / oracle_emissions * 100.0, 2)
            metrics["oracle_comparison"] = {
                "oracle_emissions_gco2": oracle_emissions,
                "oracle_gap_gco2": gap_gco2,
                "oracle_gap_pct": gap_pct,
            }
        elif oracle_emissions == 0:
            metrics["oracle_comparison"] = {
                "oracle_emissions_gco2": 0.0,
                "oracle_gap_gco2": 0.0,
                "oracle_gap_pct": 0.0,
            }

    return metrics


def compute_forecast_interval_coverage(carbon_grid: CarbonGrid) -> Dict[str, Any]:
    """
    Evaluates empirical coverage of forecast confidence intervals:
      coverage = (count of realized values within [lower_bound_ci, upper_bound_ci]) / total_points
    """
    points = carbon_grid.points
    evaluable = [
        p for p in points
        if p.realized_carbon_intensity is not None
        and p.lower_bound_ci is not None
        and p.upper_bound_ci is not None
    ]

    if not evaluable:
        return {
            "evaluable_points": 0,
            "coverage_pct": None,
            "status": "UNAVAILABLE",
            "reason": "Forecast intervals (lower_bound_ci, upper_bound_ci) or realized values not available.",
        }

    in_bounds = sum(
        1 for p in evaluable
        if p.lower_bound_ci <= p.realized_carbon_intensity <= p.upper_bound_ci
    )
    coverage_pct = round(in_bounds / len(evaluable) * 100.0, 2)

    return {
        "evaluable_points": len(evaluable),
        "in_bounds_points": in_bounds,
        "coverage_pct": coverage_pct,
        "status": "EVALUATED",
    }
