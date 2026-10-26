"""
Rolling Backtesting and Multi-Window Evaluation Harness.
Owned by Member 3 (Sairam) — Evaluation, Metrics & Testing.
Section 9.1 & 14 of Master Specification:
"Repeat across multiple trace windows/days and multiple random job traces.
Report mean and spread (standard deviation / range), not only the best run."
"""

import math
from datetime import datetime, timedelta
from typing import Any
from pydantic import BaseModel, Field

from backend.scheduler.models import Job
from backend.evaluation.scenarios import generate_jobs
from backend.evaluation.runner import EvaluationRunner, PolicyEvaluationSummary


class AggregateMetricStats(BaseModel):
    """Mean and spread across multiple backtest windows."""
    mean: float
    std: float
    min: float
    max: float


class PolicyBacktestAggregate(BaseModel):
    """Aggregate statistics for a policy across all evaluated windows."""
    policy: str
    total_emissions_gco2e: AggregateMetricStats
    emissions_reduction_pct: AggregateMetricStats
    backfire_rate_pct: AggregateMetricStats
    mean_waiting_minutes: AggregateMetricStats
    realized_savings_gco2e: AggregateMetricStats
    oracle_gap_gco2e: AggregateMetricStats


class RollingBacktestReport(BaseModel):
    """Full multi-window backtest report."""
    backtest_id: str
    window_count: int
    window_hours: int
    step_hours: int
    policy_aggregates: dict[str, PolicyBacktestAggregate]
    window_summaries: list[dict[str, PolicyEvaluationSummary]]


def _calc_stats(values: list[float]) -> AggregateMetricStats:
    """Computes mean, standard deviation, min, and max."""
    if not values:
        return AggregateMetricStats(mean=0.0, std=0.0, min=0.0, max=0.0)
    n = len(values)
    mean_val = sum(values) / n
    variance = sum((x - mean_val) ** 2 for x in values) / n if n > 1 else 0.0
    std_val = math.sqrt(variance)
    return AggregateMetricStats(
        mean=round(mean_val, 2),
        std=round(std_val, 2),
        min=round(min(values), 2),
        max=round(max(values), 2),
    )


class RollingBacktestRunner:
    """
    Slides an evaluation window across a multi-day carbon trace,
    evaluating all 4 policies on independent workloads in each window.
    """

    def __init__(
        self,
        full_time_grid: list[datetime],
        realized_carbon_map: dict[datetime, float],
        forecast_carbon_map: dict[datetime, float],
        uncertainty_map: dict[datetime, float],
        window_hours: int = 24,
        step_hours: int = 6,
        jobs_per_window: int = 15,
        max_capacity: int = 2,
    ):
        self.full_time_grid = sorted(full_time_grid)
        self.realized_carbon_map = realized_carbon_map
        self.forecast_carbon_map = forecast_carbon_map
        self.uncertainty_map = uncertainty_map
        self.window_hours = window_hours
        self.step_hours = step_hours
        self.jobs_per_window = jobs_per_window
        self.max_capacity = max_capacity

    def run(self, base_seed: int = 100, backtest_id: str = "rolling-backtest-48h") -> RollingBacktestReport:
        """Executes rolling backtesting across all available windows."""
        earliest_t = self.full_time_grid[0]
        latest_t = self.full_time_grid[-1]
        window_duration = timedelta(hours=self.window_hours)
        step_delta = timedelta(hours=self.step_hours)

        current_window_start = earliest_t
        window_summaries: list[dict[str, PolicyEvaluationSummary]] = []
        window_idx = 0

        while current_window_start + window_duration <= latest_t:
            window_end = current_window_start + window_duration
            window_grid = [t for t in self.full_time_grid if current_window_start <= t <= window_end]

            # Generate distinct deterministic jobs for this window
            window_seed = base_seed + (window_idx * 7)
            jobs = generate_jobs(
                start_time=current_window_start,
                horizon_hours=self.window_hours,
                n_jobs=self.jobs_per_window,
                seed=window_seed,
            )

            runner = EvaluationRunner(
                time_grid=window_grid,
                realized_carbon_map=self.realized_carbon_map,
                forecast_carbon_map=self.forecast_carbon_map,
                uncertainty_map=self.uncertainty_map,
                max_capacity=self.max_capacity,
            )

            report = runner.run_all_policies(jobs, risk_lambda=1.0, evaluation_id=f"win-{window_idx}")
            window_summaries.append(report.summary)

            window_idx += 1
            current_window_start += step_delta

        # Aggregate across windows by policy
        policies = ["fifo", "naive_green", "carbonova", "greedy_oracle"]
        aggregates: dict[str, PolicyBacktestAggregate] = {}

        for pol in policies:
            emissions_list = []
            reduction_list = []
            backfire_list = []
            waiting_list = []
            savings_list = []
            oracle_gap_list = []

            for w_summary in window_summaries:
                s = w_summary[pol]
                emissions_list.append(s.total_emissions_gco2e)
                if s.emissions_reduction_vs_fifo_pct is not None:
                    reduction_list.append(s.emissions_reduction_vs_fifo_pct)
                if s.backfire_rate_pct is not None:
                    backfire_list.append(s.backfire_rate_pct)
                waiting_list.append(s.waiting_time_mean_minutes)
                savings_list.append(s.realized_savings_gco2e)
                oracle_gap_list.append(s.oracle_gap_gco2e)

            aggregates[pol] = PolicyBacktestAggregate(
                policy=pol,
                total_emissions_gco2e=_calc_stats(emissions_list),
                emissions_reduction_pct=_calc_stats(reduction_list),
                backfire_rate_pct=_calc_stats(backfire_list),
                mean_waiting_minutes=_calc_stats(waiting_list),
                realized_savings_gco2e=_calc_stats(savings_list),
                oracle_gap_gco2e=_calc_stats(oracle_gap_list),
            )

        return RollingBacktestReport(
            backtest_id=backtest_id,
            window_count=len(window_summaries),
            window_hours=self.window_hours,
            step_hours=self.step_hours,
            policy_aggregates=aggregates,
            window_summaries=window_summaries,
        )
