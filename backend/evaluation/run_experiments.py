"""
Reproducible Benchmark and Experiment Runner.
Owned by Member 3 (Sairam).
Runs all 4 policies on reproducible scenarios and exports saved artifacts to data/

Supports:
1. Legacy / Synthetic Demo Mode (default, for backwards compatibility with demo trace)
2. Real NESO Trace Mode (--use-real-trace, evaluates authoritative 2024 NESO trace on saved 2024 scenarios)
   Outputs to data/results/2024_neso_reporting_v2/ with workload throughput and complete reproducibility metadata.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repo root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.carbon.neso_provider import NESORealTraceCarbonDataProvider
from backend.evaluation.scenarios import (
    DEFAULT_EVALUATION_START,
    generate_standard_batch_scenario,
    generate_resource_contention_scenario,
    generate_tight_deadline_scenario,
    generate_urgent_only_scenario,
    load_jobs_from_json,
    save_jobs_to_json,
)
from backend.evaluation.runner import EvaluationRunner
from backend.evaluation.sensitivity import (
    run_lambda_sweep,
    run_flat_carbon_sanity_check,
    run_forecast_noise_experiment,
)
from backend.evaluation.storage import (
    save_evaluation_report,
    export_dashboard_payload,
)
from backend.evaluation.backtest import RollingBacktestRunner


def load_csv_trace(filepath: str | Path) -> Tuple[Dict[datetime, float], Dict[str, str]]:
    """Loads a carbon trace CSV file."""
    trace_map: Dict[datetime, float] = {}
    provenance: Dict[str, str] = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00")).replace(tzinfo=None)
            val = float(row["carbon_intensity_gco2_per_kwh"])
            trace_map[ts] = val
            if not provenance:
                provenance = {
                    "source_type": row.get("source_type", "synthetic"),
                    "region": row.get("region", "DEMO"),
                    "unit": "gCO2e/kWh",
                }
    return trace_map, provenance


def run_synthetic_demo(
    csv_path: Path = Path("data/carbon_trace.csv"),
    scenarios_dir: Path = Path("data/scenarios"),
    results_dir: Path = Path("data/results"),
) -> None:
    """
    Executes the legacy synthetic evaluation workflow.
    Preserved for backwards compatibility with earlier demonstration artifacts.
    """
    print("=" * 70)
    print("CARBONOVA — SYNTHETIC DEMO EXPERIMENT RUNNER")
    print("Member 3: Sairam")
    print("=" * 70)

    # 1. Load Trace
    realized_trace, provenance = load_csv_trace(csv_path)
    time_grid = sorted(realized_trace.keys())
    start_time = time_grid[0]

    # Forecast with realistic error & uncertainty modeling
    forecast_trace: Dict[datetime, float] = {}
    uncertainty_map: Dict[datetime, float] = {}
    total_slots = max(len(time_grid) - 1, 1)
    for i, t in enumerate(time_grid):
        val = realized_trace[t]
        lead_ratio = i / total_slots
        hour = t.hour
        is_transition = 1.0 if (6 <= hour <= 9 or 17 <= hour <= 20) else 0.0
        unc = 12.0 + (28.0 * lead_ratio) + (10.0 * is_transition)
        uncertainty_map[t] = round(unc, 2)
        forecast_trace[t] = round(val * (1.02 + 0.04 * lead_ratio), 2)

    # 2. Generate and Save Standard Benchmark Scenarios
    print("\n[1/4] Generating reproducible workload scenarios...")
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    std_jobs = generate_standard_batch_scenario(start_time, seed=42)
    save_jobs_to_json(std_jobs, scenarios_dir / "standard_batch_24h.json")

    contention_jobs = generate_resource_contention_scenario(start_time, seed=42)
    save_jobs_to_json(contention_jobs, scenarios_dir / "resource_contention_18h.json")

    tight_jobs = generate_tight_deadline_scenario(start_time, seed=42)
    save_jobs_to_json(tight_jobs, scenarios_dir / "tight_deadlines_24h.json")

    urgent_jobs = generate_urgent_only_scenario(start_time, seed=42)
    save_jobs_to_json(urgent_jobs, scenarios_dir / "urgent_only_24h.json")

    print(f"  -> Saved 4 scenarios to {scenarios_dir}")

    # 3. Run 4-Policy Evaluation on Standard Benchmark
    print("\n[2/4] Executing 4-policy comparison on Standard Batch Scenario...")
    runner = EvaluationRunner(
        time_grid=time_grid,
        realized_carbon_map=realized_trace,
        forecast_carbon_map=forecast_trace,
        uncertainty_map=uncertainty_map,
        max_capacity=2,
        trace_provenance=provenance,
    )

    report = runner.run_all_policies(std_jobs, risk_lambda=1.0, evaluation_id="standard_batch_comparison")

    results_dir.mkdir(parents=True, exist_ok=True)
    report_file = save_evaluation_report(report, results_dir)
    print(f"  -> Saved comparison report to {report_file}")

    dashboard_payload = export_dashboard_payload(report, policy_name="carbonova")
    with open(results_dir / "dashboard_carbonova_payload.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_payload, f, indent=2)
    print(f"  -> Saved frontend dashboard payload to {results_dir / 'dashboard_carbonova_payload.json'}")

    # Print summary table
    print("\n" + "-" * 75)
    print(f"{'Policy':<16} | {'Emissions':<12} | {'Reduction%':<12} | {'Backfire%':<10} | {'Wait (m)':<8} | {'Oracle Gap'}")
    print("-" * 75)
    for p_name in ["fifo", "naive_green", "carbonova", "greedy_oracle"]:
        s = report.summary[p_name]
        red_str = f"{s.emissions_reduction_vs_fifo_pct:.1f}%" if s.emissions_reduction_vs_fifo_pct is not None else "Baseline"
        bf_str = f"{s.backfire_rate_pct:.1f}%" if s.backfire_rate_pct is not None else "N/A"
        print(
            f"{s.policy:<16} | {s.total_emissions_gco2e:>8.1f} g | {red_str:>12} | {bf_str:>10} | {s.waiting_time_mean_minutes:>8.1f} | {s.oracle_gap_gco2e:>8.1f} g"
        )
    print("-" * 75)

    # 4. Sensitivity Experiments
    print("\n[3/4] Running Lambda Uncertainty Penalty Sweep...")
    lambda_results = run_lambda_sweep(
        jobs=std_jobs,
        time_grid=time_grid,
        realized_carbon=realized_trace,
        forecast_carbon=forecast_trace,
        uncertainty_map=uncertainty_map,
        max_capacity=2,
    )
    with open(results_dir / "lambda_sensitivity.json", "w", encoding="utf-8") as f:
        json.dump(lambda_results, f, indent=2)
    print(f"  -> Saved lambda sweep to {results_dir / 'lambda_sensitivity.json'}")

    print("\n[4/5] Running Forecast Noise / Backfire Escalation Experiment...")
    noise_results = run_forecast_noise_experiment(
        jobs=std_jobs,
        time_grid=time_grid,
        true_realized_carbon=realized_trace,
        seed=42,
        max_capacity=2,
    )
    with open(results_dir / "forecast_noise_sensitivity.json", "w", encoding="utf-8") as f:
        json.dump(noise_results, f, indent=2)
    print(f"  -> Saved noise experiment to {results_dir / 'forecast_noise_sensitivity.json'}")

    print("\n[5/5] Running Rolling Backtest across multi-window horizons...")
    backtester = RollingBacktestRunner(
        full_time_grid=time_grid,
        realized_carbon_map=realized_trace,
        forecast_carbon_map=forecast_trace,
        uncertainty_map=uncertainty_map,
        window_hours=24,
        step_hours=6,
        jobs_per_window=15,
        max_capacity=2,
    )
    backtest_report = backtester.run(base_seed=100)
    with open(results_dir / "rolling_backtest_report.json", "w", encoding="utf-8") as f:
        json.dump(backtest_report.model_dump(mode="json"), f, indent=2)
    print(f"  -> Saved rolling backtest report ({backtest_report.window_count} windows) to {results_dir / 'rolling_backtest_report.json'}")

    print("\n[SUCCESS] Synthetic demo evaluation completed.")


def run_real_trace_evaluation(
    scenarios_dir: Path = Path("data/scenarios"),
    results_dir: Path = Path("data/results/2024_neso_reporting_v2"),
    start_time: datetime = DEFAULT_EVALUATION_START,
    horizon_hours: int = 36,
    max_capacity: float = 2.0,
    risk_lambda: float = 1.0,
) -> Dict[str, Any]:
    """
    Executes the authoritative evaluation workflow on the real Great Britain NESO 2024 trace.
    Loads the pre-generated 2024 scenario JSON files without overwriting or regenerating them.
    Saves all artifacts into results_dir (defaulting to data/results/2024_neso_reporting_v2/)
    with comprehensive workload completion reporting and reproducibility metadata.
    """
    print("=" * 80)
    print("CARBONOVA — REAL NESO 2024 TRACE EVALUATION RUNNER (REPORTING V2)")
    print("Member 3: Sairam")
    print("=" * 80)

    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Instantiate real NESO provider and build CarbonGrid
    print(f"\n[1/5] Initializing NESO provider for window [{start_time.isoformat()} + {horizon_hours}h]...")
    provider = NESORealTraceCarbonDataProvider(uncertainty_mode="diurnal")
    end_time = start_time + timedelta(hours=horizon_hours)

    grid = provider.get_carbon_grid(start_time, end_time, time_step_minutes=60)
    provenance = {
        "source_type": "NESO_Great_Britain_Carbon_Intensity",
        "region": "GB",
        "unit": "gCO2/kWh",
        "uncertainty_mode": provider.uncertainty_mode,
        "window_start": start_time.isoformat(),
        "window_end": end_time.isoformat(),
        "time_step_minutes": 60,
    }
    print(f"  -> Loaded {len(grid.points)} hourly forecast points from {provider.trace_path.name}")

    # 2. Load the four pre-generated 2024 scenarios
    print("\n[2/5] Loading saved 2024 scenarios from disk (zero re-generation)...")
    scenario_files = [
        ("standard_batch_comparison", scenarios_dir / "standard_batch_24h_2024.json"),
        ("resource_contention_comparison", scenarios_dir / "resource_contention_18h_2024.json"),
        ("tight_deadlines_comparison", scenarios_dir / "tight_deadlines_24h_2024.json"),
        ("urgent_only_comparison", scenarios_dir / "urgent_only_24h_2024.json"),
    ]

    runner = EvaluationRunner(
        carbon_grid=grid,
        max_capacity=max_capacity,
        trace_provenance=provenance,
    )

    reports: Dict[str, Any] = {}
    for eval_id, sc_path in scenario_files:
        if not sc_path.exists():
            raise FileNotFoundError(f"Required 2024 scenario file not found: {sc_path}")
        jobs = load_jobs_from_json(sc_path)

        # Validate bounds
        for j in jobs:
            if j.arrival_time < start_time or j.deadline > end_time:
                raise ValueError(
                    f"Job {j.job_id} in {sc_path.name} out of bounds: "
                    f"arrival={j.arrival_time.isoformat()}, deadline={j.deadline.isoformat()}, "
                    f"grid=[{start_time.isoformat()}, {end_time.isoformat()}]"
                )

        rep = runner.run_all_policies(jobs, risk_lambda=risk_lambda, evaluation_id=eval_id)
        save_evaluation_report(rep, output_dir=results_dir)
        reports[eval_id] = rep
        print(f"  -> Evaluated {sc_path.name} ({len(jobs)} jobs) -> saved {eval_id}.json")

    # Export dashboard payload for standard batch
    std_rep = reports["standard_batch_comparison"]
    payload = export_dashboard_payload(std_rep, policy_name="carbonova")
    with open(results_dir / "dashboard_carbonova_payload.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"  -> Saved dashboard payload to {results_dir / 'dashboard_carbonova_payload.json'}")

    # Print comprehensive summary table with workload completion & throughput metrics
    print("\n" + "=" * 98)
    print(f"STANDARD BATCH 2024 (REAL NESO) — 4-POLICY BENCHMARK REPORT (V2)")
    print("=" * 98)
    print(f"{'Policy':<14} | {'Done/Total':<10} | {'Done%':<7} | {'Emissions':<12} | {'Em/kWh':<10} | {'Reduction%':<11} | {'Backfire%':<10} | {'Wait (m)':<8} | {'Oracle Gap'}")
    print("-" * 98)
    for p_name in ["fifo", "naive_green", "carbonova", "greedy_oracle"]:
        s = std_rep.summary[p_name]
        done_str = f"{s.scheduled_count}/{s.submitted_count}"
        done_pct_str = f"{s.completion_rate_pct:.1f}%" if s.completion_rate_pct is not None else "N/A"
        em_kwh_str = f"{s.emissions_per_completed_kwh:.2f} g" if s.emissions_per_completed_kwh is not None else "N/A"
        red_str = f"{s.emissions_reduction_vs_fifo_pct:.1f}%" if s.emissions_reduction_vs_fifo_pct is not None else "Baseline"
        bf_str = f"{s.backfire_rate_pct:.1f}%" if s.backfire_rate_pct is not None else "N/A"
        print(
            f"{s.policy:<14} | {done_str:>10} | {done_pct_str:>7} | {s.total_emissions_gco2e:>10.1f} g | {em_kwh_str:>10} | {red_str:>11} | {bf_str:>10} | {s.waiting_time_mean_minutes:>8.1f} | {s.oracle_gap_gco2e:>8.1f} g"
        )
    print("=" * 98)

    # 3. Sensitivity Experiments on Real Trace
    print("\n[3/5] Running Lambda Uncertainty Penalty Sweep on real NESO trace...")
    std_jobs = load_jobs_from_json(scenarios_dir / "standard_batch_24h_2024.json")
    time_grid = [p.timestamp for p in grid.points]
    realized_trace = {p.timestamp: p.realized_carbon_intensity for p in grid.points}
    forecast_trace = {p.timestamp: p.predicted_carbon_intensity for p in grid.points}
    uncertainty_map = {p.timestamp: p.slot_specific_uncertainty for p in grid.points}

    lambda_results = run_lambda_sweep(
        jobs=std_jobs,
        time_grid=time_grid,
        realized_carbon=realized_trace,
        forecast_carbon=forecast_trace,
        uncertainty_map=uncertainty_map,
        max_capacity=int(max_capacity),
    )
    with open(results_dir / "lambda_sensitivity.json", "w", encoding="utf-8") as f:
        json.dump(lambda_results, f, indent=2)
    print(f"  -> Saved lambda sweep to {results_dir / 'lambda_sensitivity.json'}")

    print("\n[4/5] Running Forecast Noise / Backfire Escalation Experiment on real NESO trace...")
    noise_results = run_forecast_noise_experiment(
        jobs=std_jobs,
        time_grid=time_grid,
        true_realized_carbon=realized_trace,
        seed=42,
        max_capacity=int(max_capacity),
    )
    with open(results_dir / "forecast_noise_sensitivity.json", "w", encoding="utf-8") as f:
        json.dump(noise_results, f, indent=2)
    print(f"  -> Saved noise experiment to {results_dir / 'forecast_noise_sensitivity.json'}")

    # 4. Multi-Day Rolling Backtest on Real 2024 Trace
    print("\n[5/5] Running Rolling Backtest across 7-day real NESO window (June 1 - June 8, 2024)...")
    backtest_days = 7
    backtest_end = start_time + timedelta(days=backtest_days)
    bt_grid = provider.get_carbon_grid(start_time, backtest_end, time_step_minutes=60)
    bt_time_grid = [p.timestamp for p in bt_grid.points]
    bt_realized = {p.timestamp: p.realized_carbon_intensity for p in bt_grid.points}
    bt_forecast = {p.timestamp: p.predicted_carbon_intensity for p in bt_grid.points}
    bt_uncertainty = {p.timestamp: p.slot_specific_uncertainty for p in bt_grid.points}

    backtester = RollingBacktestRunner(
        full_time_grid=bt_time_grid,
        realized_carbon_map=bt_realized,
        forecast_carbon_map=bt_forecast,
        uncertainty_map=bt_uncertainty,
        window_hours=24,
        step_hours=6,
        jobs_per_window=15,
        max_capacity=int(max_capacity),
    )
    backtest_report = backtester.run(base_seed=100, backtest_id="rolling-backtest-7d-june2024")
    with open(results_dir / "rolling_backtest_report.json", "w", encoding="utf-8") as f:
        json.dump(backtest_report.model_dump(mode="json"), f, indent=2)
    print(f"  -> Saved rolling backtest report ({backtest_report.window_count} windows) to {results_dir / 'rolling_backtest_report.json'}")

    # 5. Master Reproducibility & Provenance Summary (V2 Schema)
    summary_data = {
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "real_neso_2024",
        "provenance": {
            "provider_class": "NESORealTraceCarbonDataProvider",
            "source_trace_csv": str(provider.trace_path.name),
            "provenance_source": "NESO_Great_Britain_Carbon_Intensity",
            "region": "GB",
            "unit": "gCO2/kWh",
            "uncertainty_mode": provider.uncertainty_mode,
            "diurnal_quantiles_gco2_per_kwh": getattr(provider, "diurnal_quantiles", {}),
            "global_quantile_gco2_per_kwh": getattr(provider, "global_quantile", None),
        },
        "time_window": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "step_minutes": 60,
        },
        "scheduler_configuration": {
            "cluster_total_capacity": max_capacity,
            "time_step_minutes": 60,
            "job_ordering": "earliest_arrival_first",
            "risk_lambda": risk_lambda,
            "min_improvement_margin": 0.0,
            "margin_unit": "relative_percentage",
        },
        "random_seeds": {
            "scenario_generation_seed": 42,
            "forecast_noise_experiment_seed": 42,
            "rolling_backtest_base_seed": 100,
        },
        "output_artifact_paths": [
            "standard_batch_comparison.json",
            "resource_contention_comparison.json",
            "tight_deadlines_comparison.json",
            "urgent_only_comparison.json",
            "dashboard_carbonova_payload.json",
            "lambda_sensitivity.json",
            "forecast_noise_sensitivity.json",
            "rolling_backtest_report.json",
            "experiment_summary.json",
        ],
        "methodology_and_reproducibility": {
            "metrics_implementation": "backend.scheduler.metrics.compute_schedule_metrics",
            "scheduling_engine_reference": "backend.scheduler.engine.SchedulingEngine",
            "oracle_specification": "Online sequential greedy oracle with perfect ground-truth lookahead under identical job arrival ordering (not offline global MIP/ILP)",
            "unexecuted_job_accounting": "Unscheduled jobs emit 0 gCO2e; throughput must be evaluated alongside raw emissions via completion_rate_pct and emissions_per_completed_kwh",
            "specification_reference": "Carbonova Master Specification Section 9.1, 11.2, & 13.1",
        },
        "scenarios": {
            name: {
                "file": sc_path.name,
                "job_count": len(reports[name].detailed_schedules["fifo"].scheduled_jobs) + len(reports[name].detailed_schedules["fifo"].unscheduled_jobs),
                "summary": {
                    pol: s.model_dump(mode="json")
                    for pol, s in reports[name].summary.items()
                },
            }
            for name, sc_path in scenario_files
        },
        "backtest_summary": {
            "window_count": backtest_report.window_count,
            "policy_aggregates": {
                pol: agg.model_dump(mode="json")
                for pol, agg in backtest_report.policy_aggregates.items()
            },
        },
    }
    with open(results_dir / "experiment_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"  -> Saved aggregate experiment summary (v2) to {results_dir / 'experiment_summary.json'}")

    print("\n[SUCCESS] Real NESO 2024 trace evaluation benchmark completed successfully.")
    return summary_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Carbonova — Evaluation, Metrics & Reproducibility Benchmark Runner")
    parser.add_argument(
        "--use-real-trace",
        action="store_true",
        help="Use real Great Britain NESO 2024 carbon trace and load saved 2024 scenarios",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Custom output results directory (defaults to data/results/2024_neso_reporting_v2 for real trace)",
    )
    args = parser.parse_args()

    if args.use_real_trace:
        target_dir = Path(args.results_dir) if args.results_dir else Path("data/results/2024_neso_reporting_v2")
        run_real_trace_evaluation(results_dir=target_dir)
    else:
        target_dir = Path(args.results_dir) if args.results_dir else Path("data/results")
        run_synthetic_demo(results_dir=target_dir)


if __name__ == "__main__":
    main()
