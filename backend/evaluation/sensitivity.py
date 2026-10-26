"""
Sensitivity Analysis Experiments.
Owned by Member 3 (Sairam) — Evaluation, Metrics & Testing.
Deliverables 3 & 5.
Section 9.1 & 9.2 of Master Specification:
- Variable vs Flat Carbon Trace (Sanity check)
- Forecast Uncertainty Penalty (Lambda) Sweep
- Forecast Noise / Backfire Escalation Experiment
- Resource Capacity and Deadline Tightness Sweeps
"""

import random
from datetime import datetime
from typing import Any
from backend.scheduler.models import Job
from backend.evaluation.runner import EvaluationRunner, EvaluationReport


def run_lambda_sweep(
    jobs: list[Job],
    time_grid: list[datetime],
    realized_carbon: dict[datetime, float],
    forecast_carbon: dict[datetime, float],
    uncertainty_map: dict[datetime, float],
    lambdas: list[float] = [0.0, 0.2, 0.5, 0.8, 1.0, 1.5, 2.0, 2.5],
    max_capacity: int = 1,
) -> list[dict[str, Any]]:
    """
    Sweeps risk_lambda across a range of values.
    Shows the tradeoff between aggressive shifting (lower lambda)
    and uncertainty conservatism (higher lambda).
    """
    runner = EvaluationRunner(
        time_grid=time_grid,
        realized_carbon_map=realized_carbon,
        forecast_carbon_map=forecast_carbon,
        uncertainty_map=uncertainty_map,
        max_capacity=max_capacity,
    )

    results = []
    for lmb in lambdas:
        report = runner.run_all_policies(jobs, risk_lambda=lmb, evaluation_id=f"sweep-lambda-{lmb}")
        carb_summary = report.summary["carbonova"]
        results.append(
            {
                "lambda": lmb,
                "total_emissions_gco2e": carb_summary.total_emissions_gco2e,
                "emissions_reduction_vs_fifo_pct": carb_summary.emissions_reduction_vs_fifo_pct,
                "backfire_rate_pct": carb_summary.backfire_rate_pct,
                "mean_waiting_minutes": carb_summary.waiting_time_mean_minutes,
                "deadline_success_pct": carb_summary.deadline_success_pct,
                "oracle_gap_gco2e": carb_summary.oracle_gap_gco2e,
            }
        )
    return results


def run_flat_carbon_sanity_check(
    jobs: list[Job],
    time_grid: list[datetime],
    flat_intensity: float = 400.0,
    max_capacity: int = 1,
) -> EvaluationReport:
    """
    Sanity check per Section 9.2:
    When carbon intensity is constant across all time steps,
    savings from time-shifting must be essentially zero (~0 gCO2e, ~0%).
    The system MUST NOT manufacture fake savings.
    """
    flat_trace = {t: flat_intensity for t in time_grid}
    zero_uncertainty = {t: 0.0 for t in time_grid}

    runner = EvaluationRunner(
        time_grid=time_grid,
        realized_carbon_map=flat_trace,
        forecast_carbon_map=flat_trace,
        uncertainty_map=zero_uncertainty,
        max_capacity=max_capacity,
        trace_provenance={"source_type": "synthetic_flat", "intensity": flat_intensity},
    )

    return runner.run_all_policies(jobs, risk_lambda=1.0, evaluation_id="sanity-flat-carbon")


def run_forecast_noise_experiment(
    jobs: list[Job],
    time_grid: list[datetime],
    true_realized_carbon: dict[datetime, float],
    noise_stds: list[float] = [0.0, 25.0, 50.0, 75.0, 100.0],
    seed: int = 42,
    max_capacity: int = 1,
) -> list[dict[str, Any]]:
    """
    Evaluates backfire escalation under increasing forecast noise.
    Demonstrates that Naive-Green suffers severe backfire when forecasts are inaccurate,
    while Carbonova's uncertainty-penalty mitigates backfire.
    """
    rng = random.Random(seed)
    results = []
    total_slots = max(len(time_grid) - 1, 1)

    for noise_std in noise_stds:
        # Generate noisy forecast with horizon-growing uncertainty
        noisy_forecast = {}
        estimated_uncertainty = {}
        for i, t in enumerate(time_grid):
            true_val = true_realized_carbon[t]
            # Uncertainty scales with baseline and lead-time horizon
            lead_factor = 1.0 + (i / total_slots)
            slot_unc = round(max(5.0, noise_std * lead_factor), 2)
            err = rng.gauss(0.0, slot_unc) if noise_std > 0 else 0.0
            noisy_val = max(20.0, true_val + err)
            noisy_forecast[t] = round(noisy_val, 2)
            estimated_uncertainty[t] = slot_unc

        runner = EvaluationRunner(
            time_grid=time_grid,
            realized_carbon_map=true_realized_carbon,
            forecast_carbon_map=noisy_forecast,
            uncertainty_map=estimated_uncertainty,
            max_capacity=max_capacity,
        )

        report = runner.run_all_policies(
            jobs, risk_lambda=1.5, evaluation_id=f"noise-std-{noise_std}"
        )
        naive = report.summary["naive_green"]
        carb = report.summary["carbonova"]

        results.append(
            {
                "noise_std": noise_std,
                "naive_green": {
                    "total_emissions": naive.total_emissions_gco2e,
                    "backfire_rate_pct": naive.backfire_rate_pct,
                    "realized_savings": naive.realized_savings_gco2e,
                },
                "carbonova": {
                    "total_emissions": carb.total_emissions_gco2e,
                    "backfire_rate_pct": carb.backfire_rate_pct,
                    "realized_savings": carb.realized_savings_gco2e,
                },
            }
        )

    return results
