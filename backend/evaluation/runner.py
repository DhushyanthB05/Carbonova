"""
Evaluation and Comparison Runner.
Owned by Member 3 (Sairam) — Evaluation, Metrics & Testing.
Deliverables 1, 2, 3.

Delegates scheduling execution and official metrics directly to Member 2's
authoritative SchedulingEngine (backend.scheduler.engine) and CarbonGrid.
Scoring is performed against the SAME realized carbon trace across all 4 policies:
1. FIFO / Earliest Feasible
2. Naive-Green
3. Carbonova (Uncertainty-Aware)
4. Perfect-Forecast Greedy Oracle
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from pydantic import BaseModel, Field

from backend.carbon.interface import CarbonForecastPoint, CarbonGrid
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.metrics import calculate_job_emissions
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
    MultiPolicyScheduleResponse,
    PolicyScheduleResult,
    PolicyType,
    SchedulerConfig,
)


class ScheduledJob(BaseModel):
    """Assignment details for a scheduled job (evaluation representation)."""
    job_id: str
    scheduled_start: datetime
    scheduled_finish: datetime
    predicted_intensity: float
    uncertainty: float = 0.0
    risk_score: float = 0.0
    explanation: str = ""
    is_delayed: bool = False
    realized_emissions_gco2e: Optional[float] = None
    immediate_emissions_gco2e: Optional[float] = None
    backfired: Optional[bool] = None


class ScheduleResult(BaseModel):
    """Schedule result model for evaluation reporting and dashboard exports."""
    policy: str
    risk_lambda: float = 0.0
    scheduled_jobs: List[ScheduledJob] = Field(default_factory=list)
    unscheduled_jobs: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    raw_result: Optional[PolicyScheduleResult] = None


class PolicyEvaluationSummary(BaseModel):
    """Evaluation summary metrics for a single scheduling policy."""
    policy: str
    total_emissions_gco2e: float
    emissions_reduction_vs_fifo_pct: Optional[float] = None
    deadline_success_pct: float
    waiting_time_mean_minutes: float
    waiting_time_median_minutes: float
    waiting_time_max_minutes: float
    backfire_rate_pct: Optional[float] = None
    predicted_savings_gco2e: float
    realized_savings_gco2e: float
    oracle_gap_gco2e: float
    oracle_gap_pct: Optional[float] = None
    scheduled_count: int
    unscheduled_count: int
    submitted_count: int = 0
    completion_rate_pct: Optional[float] = None
    total_energy_executed_kwh: float = 0.0
    emissions_per_completed_kwh: Optional[float] = None


class EvaluationReport(BaseModel):
    """Comprehensive comparison report across all policies."""
    evaluation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parameters: Dict[str, Any] = Field(default_factory=dict)
    trace_provenance: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, PolicyEvaluationSummary]
    detailed_schedules: Dict[str, ScheduleResult]
    multi_policy_response: Optional[MultiPolicyScheduleResponse] = None


class EvaluationRunner:
    """
    Evaluation Runner orchestrating the 4-policy benchmark.
    Directly delegates scheduling dispatch and metrics computation to Member 2's SchedulingEngine.
    """

    def __init__(
        self,
        time_grid: Optional[Sequence[datetime]] = None,
        realized_carbon_map: Optional[Dict[datetime, float]] = None,
        forecast_carbon_map: Optional[Dict[datetime, float]] = None,
        uncertainty_map: Optional[Dict[datetime, float]] = None,
        max_capacity: float = 1.0,
        time_step_minutes: int = 60,
        trace_provenance: Optional[Dict[str, Any]] = None,
        carbon_grid: Optional[CarbonGrid] = None,
    ):
        self.time_step_minutes = time_step_minutes
        self.max_capacity = max_capacity
        self.trace_provenance = trace_provenance or {
            "source_type": "synthetic",
            "region": "DEMO-GRID",
            "unit": "gCO2e/kWh",
        }

        if carbon_grid is not None:
            self.carbon_grid = carbon_grid
            self.time_grid = [p.timestamp for p in carbon_grid.points]
            self.realized_carbon_map = {
                p.timestamp: p.realized_carbon_intensity
                for p in carbon_grid.points
                if p.realized_carbon_intensity is not None
            }
            self.forecast_carbon_map = {
                p.timestamp: p.predicted_carbon_intensity
                for p in carbon_grid.points
            }
            self.uncertainty_map = {
                p.timestamp: p.slot_specific_uncertainty
                for p in carbon_grid.points
            }
        else:
            if not time_grid:
                raise ValueError("Either carbon_grid or time_grid must be provided to EvaluationRunner.")
            self.time_grid = sorted(time_grid)
            self.realized_carbon_map = realized_carbon_map or {}
            self.forecast_carbon_map = forecast_carbon_map or {}
            self.uncertainty_map = uncertainty_map or {t: 0.0 for t in self.time_grid}

            # Construct verified Member 2 CarbonGrid from discrete inputs
            points: List[CarbonForecastPoint] = []
            for t in self.time_grid:
                ts = t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc)
                pred_ci = float(self.forecast_carbon_map.get(t, 0.0))
                unc = float(self.uncertainty_map.get(t, 0.0))
                real_ci = (
                    float(self.realized_carbon_map[t])
                    if (t in self.realized_carbon_map and self.realized_carbon_map[t] is not None)
                    else None
                )
                points.append(
                    CarbonForecastPoint(
                        timestamp=ts,
                        predicted_carbon_intensity=pred_ci,
                        slot_specific_uncertainty=unc,
                        realized_carbon_intensity=real_ci,
                        provenance=str(self.trace_provenance.get("source_type", "SYNTHETIC")),
                    )
                )
            self.carbon_grid = CarbonGrid(points, time_step_minutes=self.time_step_minutes)

    def run_all_policies(
        self,
        jobs: Sequence[Job],
        risk_lambda: float = 1.0,
        evaluation_id: str = "eval-run-001",
    ) -> EvaluationReport:
        """
        Executes FIFO, Naive-Green, Carbonova, and Perfect-Forecast Greedy Oracle
        via Member 2's authoritative SchedulingEngine, reusing official metric calculations.
        """
        job_dict = {j.job_id: j for j in jobs}

        # Configure cluster and risk parameters
        config = SchedulerConfig(
            risk_lambda=risk_lambda,
            cluster=ClusterConfig(
                total_capacity=float(self.max_capacity),
                time_step_minutes=self.time_step_minutes,
            ),
        )

        # Execute all policies via authoritative engine
        response: MultiPolicyScheduleResponse = SchedulingEngine.run_all_policies(
            jobs=jobs,
            carbon_grid=self.carbon_grid,
            config=config,
        )

        summaries: Dict[str, PolicyEvaluationSummary] = {}
        detailed_schedules: Dict[str, ScheduleResult] = {}

        for p_name, p_res in response.results.items():
            metrics = p_res.metrics
            tot_emissions = float(metrics.get("total_realized_emissions_gco2") or 0.0)
            baseline_comp = metrics.get("baseline_comparison", {})
            reduction_vs_fifo = baseline_comp.get("emissions_reduction_pct")
            oracle_comp = metrics.get("oracle_comparison", {})
            oracle_gap_gco2 = float(oracle_comp.get("oracle_gap_gco2") or 0.0)
            oracle_gap_pct = oracle_comp.get("oracle_gap_pct")
            
            # Deadline success: Member 2 returns None if no feasible jobs submitted
            raw_deadline_rate = metrics.get("deadline_success_rate_pct")
            deadline_success_val = float(raw_deadline_rate) if raw_deadline_rate is not None else 0.0
            
            waiting_info = metrics.get("waiting_time_minutes", {})
            backfire_pct = metrics.get("backfire_rate_pct")
            pred_savings = float(metrics.get("predicted_savings_vs_earliest_gco2") or 0.0)
            real_savings = float(metrics.get("realized_savings_vs_earliest_gco2") or 0.0)
            scheduled_count = int(metrics.get("scheduled_jobs_count", 0))
            unscheduled_count = int(metrics.get("initially_infeasible_jobs", 0)) + int(metrics.get("capacity_infeasible_jobs", 0))
            submitted_count = len(jobs)
            completion_rate = round(scheduled_count / submitted_count * 100.0, 2) if submitted_count > 0 else 0.0

            # Total energy of successfully scheduled jobs (kWh)
            executed_energy = sum(
                job_dict[d.job_id].energy_kwh
                for d in p_res.decisions
                if d.feasibility_status == FeasibilityStatus.SCHEDULED and d.job_id in job_dict
            )
            executed_energy = round(float(executed_energy), 4)
            emissions_per_kwh = round(tot_emissions / executed_energy, 2) if executed_energy > 0.0 else None

            summary = PolicyEvaluationSummary(
                policy=p_name,
                total_emissions_gco2e=tot_emissions,
                emissions_reduction_vs_fifo_pct=reduction_vs_fifo,
                deadline_success_pct=deadline_success_val,
                waiting_time_mean_minutes=float(waiting_info.get("mean", 0.0)),
                waiting_time_median_minutes=float(waiting_info.get("median", 0.0)),
                waiting_time_max_minutes=float(waiting_info.get("max", 0.0)),
                backfire_rate_pct=backfire_pct,
                predicted_savings_gco2e=pred_savings,
                realized_savings_gco2e=real_savings,
                oracle_gap_gco2e=oracle_gap_gco2,
                oracle_gap_pct=oracle_gap_pct,
                scheduled_count=scheduled_count,
                unscheduled_count=unscheduled_count,
                submitted_count=submitted_count,
                completion_rate_pct=completion_rate,
                total_energy_executed_kwh=executed_energy,
                emissions_per_completed_kwh=emissions_per_kwh,
            )
            summaries[p_name] = summary

            # Construct backward-compatible ScheduleResult for detailed auditing & dashboard
            scheduled_jobs: List[ScheduledJob] = []
            unscheduled_jobs: List[str] = []

            for d in p_res.decisions:
                if d.feasibility_status == FeasibilityStatus.SCHEDULED and d.scheduled_start and d.scheduled_finish:
                    is_delayed = bool(d.earliest_feasible_start and d.scheduled_start > d.earliest_feasible_start)
                    job = job_dict.get(d.job_id)
                    job_real_em: Optional[float] = None
                    job_imm_em: Optional[float] = None
                    backfired: Optional[bool] = None

                    if job and self.carbon_grid:
                        try:
                            job_real_em = calculate_job_emissions(job, d.scheduled_start, self.carbon_grid, use_realized=True)
                            if d.earliest_feasible_start:
                                job_imm_em = calculate_job_emissions(job, d.earliest_feasible_start, self.carbon_grid, use_realized=True)
                                if is_delayed and job_real_em is not None and job_imm_em is not None:
                                    backfired = job_real_em > job_imm_em
                                else:
                                    backfired = False
                        except Exception:
                            pass

                    scheduled_jobs.append(
                        ScheduledJob(
                            job_id=d.job_id,
                            scheduled_start=d.scheduled_start,
                            scheduled_finish=d.scheduled_finish,
                            predicted_intensity=float(d.predicted_carbon_intensity or 0.0),
                            uncertainty=float(d.slot_uncertainty or 0.0),
                            risk_score=float(d.risk_score or 0.0),
                            explanation=d.reason,
                            is_delayed=is_delayed,
                            realized_emissions_gco2e=job_real_em,
                            immediate_emissions_gco2e=job_imm_em,
                            backfired=backfired,
                        )
                    )
                else:
                    unscheduled_jobs.append(d.job_id)

            sched_result = ScheduleResult(
                policy=p_name,
                risk_lambda=risk_lambda,
                scheduled_jobs=scheduled_jobs,
                unscheduled_jobs=unscheduled_jobs,
                metrics=p_res.metrics,
                raw_result=p_res,
            )
            detailed_schedules[p_name] = sched_result

        # Support both 'oracle' and 'greedy_oracle' naming for backward compatibility
        if "oracle" in summaries:
            summaries["greedy_oracle"] = summaries["oracle"].model_copy(update={"policy": "greedy_oracle"})
            detailed_schedules["greedy_oracle"] = detailed_schedules["oracle"]

        report = EvaluationReport(
            evaluation_id=evaluation_id,
            parameters={
                "risk_lambda": risk_lambda,
                "max_capacity": self.max_capacity,
                "total_jobs": len(jobs),
                "time_step_minutes": self.time_step_minutes,
            },
            trace_provenance=self.trace_provenance,
            summary=summaries,
            detailed_schedules=detailed_schedules,
            multi_policy_response=response,
        )

        return report
