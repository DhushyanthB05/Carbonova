"""
Scheduling Engine Core.

The primary entry point for scheduling execution, policy comparison, and Member 3's evaluation runner.
Coordinates job ordering, policy execution, metric computation, and explainability.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend.carbon.interface import CarbonGrid
from backend.scheduler.metrics import compute_schedule_metrics
from backend.scheduler.models import (
    ClusterConfig,
    Job,
    JobOrdering,
    MarginUnit,
    MultiPolicyScheduleResponse,
    PolicyScheduleResult,
    PolicyType,
    SchedulerConfig,
)
from backend.scheduler.ordering import sort_jobs
from backend.scheduler.policies import (
    run_carbonova_policy,
    run_fifo_policy,
    run_naive_green_policy,
    run_oracle_policy,
)


class SchedulingEngine:
    """
    High-level engine that executes policies and compiles comparative metrics.
    Designed for direct integration by Member 3 (Evaluation Runner) and FastAPI routers.
    """

    @staticmethod
    def run_policy(
        jobs: Sequence[Job],
        carbon_grid: CarbonGrid,
        config: Optional[SchedulerConfig] = None,
    ) -> PolicyScheduleResult:
        """
        Executes a single requested policy on a batch of jobs.
        """
        cfg = config or SchedulerConfig()
        ordered_jobs = sort_jobs(jobs, ordering=cfg.job_ordering)

        if cfg.policy == PolicyType.FIFO:
            result = run_fifo_policy(ordered_jobs, carbon_grid, cfg)
        elif cfg.policy == PolicyType.NAIVE_GREEN:
            result = run_naive_green_policy(ordered_jobs, carbon_grid, cfg)
        elif cfg.policy == PolicyType.CARBONOVA:
            result = run_carbonova_policy(ordered_jobs, carbon_grid, cfg)
        elif cfg.policy == PolicyType.ORACLE:
            result = run_oracle_policy(ordered_jobs, carbon_grid, cfg)
        else:
            raise ValueError(f"Unknown policy: {cfg.policy}")

        # Attach single-policy metrics
        result.metrics = compute_schedule_metrics(jobs, result, carbon_grid)
        return result

    @classmethod
    def run_all_policies(
        cls,
        jobs: Sequence[Job],
        carbon_grid: CarbonGrid,
        config: Optional[SchedulerConfig] = None,
    ) -> MultiPolicyScheduleResponse:
        """
        Executes all four policies (FIFO, Naive-Green, Carbonova, Oracle) on the exact same
        job batch, calculates cross-policy comparative metrics (FIFO baseline, Oracle gap),
        and returns a unified MultiPolicyScheduleResponse.
        """
        base_cfg = config or SchedulerConfig()

        # 1. Run FIFO (Baseline)
        fifo_cfg = base_cfg.model_copy(update={"policy": PolicyType.FIFO})
        fifo_res = cls.run_policy(jobs, carbon_grid, fifo_cfg)

        # 2. Run Naive-Green
        naive_cfg = base_cfg.model_copy(update={"policy": PolicyType.NAIVE_GREEN})
        naive_res = cls.run_policy(jobs, carbon_grid, naive_cfg)

        # 3. Run Carbonova
        carb_cfg = base_cfg.model_copy(update={"policy": PolicyType.CARBONOVA})
        carb_res = cls.run_policy(jobs, carbon_grid, carb_cfg)

        # 4. Check if Oracle can run (requires realized carbon data)
        oracle_res: Optional[PolicyScheduleResult] = None
        has_realized = any(p.realized_carbon_intensity is not None for p in carbon_grid.points)
        if has_realized:
            oracle_cfg = base_cfg.model_copy(update={"policy": PolicyType.ORACLE})
            oracle_res = cls.run_policy(jobs, carbon_grid, oracle_cfg)

        # Re-compute metrics with baseline and oracle linkages
        results: Dict[str, PolicyScheduleResult] = {}
        for p_res in [fifo_res, naive_res, carb_res, oracle_res]:
            if p_res is None:
                continue
            p_res.metrics = compute_schedule_metrics(
                jobs=jobs,
                schedule_result=p_res,
                carbon_grid=carbon_grid,
                baseline_result=fifo_res,
                oracle_result=oracle_res,
            )
            results[p_res.policy.value] = p_res

        # Comparative summary across policies
        summary: Dict[str, Any] = {
            "ordering_evaluated": base_cfg.job_ordering.value,
            "total_jobs": len(jobs),
            "realized_emissions_gco2": {
                k: v.metrics.get("total_realized_emissions_gco2")
                for k, v in results.items()
            },
            "emissions_reduction_vs_fifo_pct": {
                k: v.metrics.get("baseline_comparison", {}).get("emissions_reduction_pct")
                for k, v in results.items() if k != "fifo"
            },
            "oracle_gap_pct": {
                k: v.metrics.get("oracle_comparison", {}).get("oracle_gap_pct")
                for k, v in results.items() if k != "oracle"
            },
            "backfire_rate_display": {
                k: v.metrics.get("backfire_rate_display")
                for k, v in results.items()
            },
            "deadline_success_rate_pct": {
                k: v.metrics.get("deadline_success_rate_pct")
                for k, v in results.items()
            },
        }

        return MultiPolicyScheduleResponse(
            time_step_minutes=base_cfg.cluster.time_step_minutes,
            cluster_capacity=base_cfg.cluster.total_capacity,
            results=results,
            comparative_summary=summary,
        )

    @classmethod
    def compare_orderings(
        cls,
        jobs: Sequence[Job],
        carbon_grid: CarbonGrid,
        policy: PolicyType = PolicyType.CARBONOVA,
        risk_lambda: float = 0.5,
        min_improvement_margin: float = 0.05,
        margin_unit: MarginUnit = MarginUnit.RELATIVE_PERCENTAGE,
        cluster_config: Optional[ClusterConfig] = None,
    ) -> Dict[str, Any]:
        """
        Direct helper for Member 3's sensitivity analysis:
        Compares Earliest-Arrival-First (EAF) vs Least-Deadline-Slack-First (LDSF)
        for a given policy under identical resource and carbon conditions.
        """
        cluster = cluster_config or ClusterConfig()
        
        cfg_eaf = SchedulerConfig(
            policy=policy,
            job_ordering=JobOrdering.EARLIEST_ARRIVAL_FIRST,
            risk_lambda=risk_lambda,
            min_improvement_margin=min_improvement_margin,
            margin_unit=margin_unit,
            cluster=cluster,
        )
        res_eaf = cls.run_policy(jobs, carbon_grid, cfg_eaf)

        cfg_ldsf = SchedulerConfig(
            policy=policy,
            job_ordering=JobOrdering.LEAST_DEADLINE_SLACK_FIRST,
            risk_lambda=risk_lambda,
            min_improvement_margin=min_improvement_margin,
            margin_unit=margin_unit,
            cluster=cluster,
        )
        res_ldsf = cls.run_policy(jobs, carbon_grid, cfg_ldsf)

        return {
            "policy": policy.value,
            "earliest_arrival_first": {
                "metrics": res_eaf.metrics,
                "decisions": [d.model_dump() for d in res_eaf.decisions],
            },
            "least_deadline_slack_first": {
                "metrics": res_ldsf.metrics,
                "decisions": [d.model_dump() for d in res_ldsf.decisions],
            },
        }
