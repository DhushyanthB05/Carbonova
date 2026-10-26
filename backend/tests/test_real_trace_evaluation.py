"""
Unit tests for the Real NESO 2024 Evaluation Mode.
Verifies Task 6B Step 7 & Step 10 requirements:
- Loading of saved 2024 scenarios (without regeneration)
- Use of NESORealTraceCarbonDataProvider
- Preservation of original scenarios and demo results
- Output directed to versioned directories (data/results/2024_neso_reporting_v2/)
- Error handling on invalid or out-of-range dates
- Intact synthetic demo mode interface and contracts
- Workload completion reporting and emissions-per-completed-kWh metrics
- Reproducibility metadata and schema backward compatibility
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.carbon.neso_provider import NESORealTraceCarbonDataProvider
from backend.carbon.interface import CarbonGrid
from backend.evaluation.scenarios import (
    DEFAULT_EVALUATION_START,
    load_jobs_from_json,
)
from backend.evaluation.runner import EvaluationRunner, PolicyEvaluationSummary
from backend.evaluation.run_experiments import (
    run_real_trace_evaluation,
    run_synthetic_demo,
)


def test_saved_2024_scenarios_exist_and_loadable():
    """Confirms all four saved 2024 scenarios exist and contain expected job counts."""
    scenarios = {
        "standard_batch_24h_2024.json": 20,
        "resource_contention_18h_2024.json": 35,
        "tight_deadlines_24h_2024.json": 20,
        "urgent_only_24h_2024.json": 15,
    }
    sc_dir = Path("data/scenarios")
    for filename, expected_count in scenarios.items():
        path = sc_dir / filename
        assert path.exists(), f"Missing scenario file: {path}"
        jobs = load_jobs_from_json(path)
        assert len(jobs) == expected_count
        # Verify UTC timezone awareness
        for j in jobs:
            assert j.arrival_time.tzinfo == timezone.utc
            assert j.deadline.tzinfo == timezone.utc


def test_real_provider_produces_valid_2024_grid():
    """Verifies that NESO provider supplies a 2024 grid with conformal uncertainties."""
    provider = NESORealTraceCarbonDataProvider()
    start = DEFAULT_EVALUATION_START
    end = start + timedelta(hours=24)
    grid = provider.get_carbon_grid(start, end, time_step_minutes=60)

    assert isinstance(grid, CarbonGrid)
    assert len(grid.points) == 24  # 24 hourly slots for half-open interval [start, end)
    for p in grid.points:
        assert p.timestamp.year == 2024
        assert p.timestamp.month == 6
        assert p.predicted_carbon_intensity > 0.0
        assert p.realized_carbon_intensity is not None
        assert p.realized_carbon_intensity > 0.0
        assert p.slot_specific_uncertainty > 0.0


def test_real_provider_rejects_out_of_range_dates():
    """Verifies that dates outside 2024 raise a ValueError."""
    provider = NESORealTraceCarbonDataProvider()
    start_2026 = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    end_2026 = start_2026 + timedelta(hours=24)

    with pytest.raises(ValueError, match="out of range"):
        provider.get_carbon_grid(start_2026, end_2026, time_step_minutes=60)


def test_scenario_jobs_within_grid_bounds():
    """Verifies that all jobs in 2024 scenarios fit within the standard 36h evaluation window."""
    provider = NESORealTraceCarbonDataProvider()
    start = DEFAULT_EVALUATION_START
    end = start + timedelta(hours=36)
    grid = provider.get_carbon_grid(start, end, time_step_minutes=60)
    grid_start = grid.points[0].timestamp
    grid_end = grid.points[-1].timestamp

    sc_dir = Path("data/scenarios")
    for filename in [
        "standard_batch_24h_2024.json",
        "resource_contention_18h_2024.json",
        "tight_deadlines_24h_2024.json",
        "urgent_only_24h_2024.json",
    ]:
        jobs = load_jobs_from_json(sc_dir / filename)
        for j in jobs:
            assert j.arrival_time >= grid_start
            assert j.deadline <= grid_end


def test_evaluation_runner_scores_four_policies_on_real_grid():
    """Verifies EvaluationRunner computes metrics across FIFO, Naive-Green, Carbonova, and Oracle on real NESO grid."""
    provider = NESORealTraceCarbonDataProvider()
    start = DEFAULT_EVALUATION_START
    end = start + timedelta(hours=36)
    grid = provider.get_carbon_grid(start, end, time_step_minutes=60)

    jobs = load_jobs_from_json("data/scenarios/standard_batch_24h_2024.json")
    runner = EvaluationRunner(
        carbon_grid=grid,
        max_capacity=2.0,
        trace_provenance={"source_type": "NESO_GB", "region": "GB"},
    )
    report = runner.run_all_policies(jobs, risk_lambda=1.0, evaluation_id="test-real-run")

    for pol in ["fifo", "naive_green", "carbonova", "greedy_oracle"]:
        assert pol in report.summary
        s = report.summary[pol]
        assert s.total_emissions_gco2e > 0.0
        assert s.deadline_success_pct >= 0.0
        assert s.waiting_time_mean_minutes >= 0.0


def test_workload_completion_and_emissions_per_kwh_reporting():
    """Verifies workload completion metrics and emissions per completed kWh reporting."""
    provider = NESORealTraceCarbonDataProvider()
    start = DEFAULT_EVALUATION_START
    end = start + timedelta(hours=36)
    grid = provider.get_carbon_grid(start, end, time_step_minutes=60)

    jobs = load_jobs_from_json("data/scenarios/standard_batch_24h_2024.json")
    runner = EvaluationRunner(
        carbon_grid=grid,
        max_capacity=2.0,
        trace_provenance={"source_type": "NESO_GB", "region": "GB"},
    )
    report = runner.run_all_policies(jobs, risk_lambda=1.0, evaluation_id="test-completion-run")

    # In standard batch:
    # Carbonova and FIFO schedule all 20 jobs
    carb = report.summary["carbonova"]
    fifo = report.summary["fifo"]
    naive = report.summary["naive_green"]
    oracle = report.summary["greedy_oracle"]

    assert carb.submitted_count == 20
    assert carb.scheduled_count == 20
    assert carb.unscheduled_count == 0
    assert carb.completion_rate_pct == 100.0
    assert carb.total_energy_executed_kwh > 0.0
    assert carb.emissions_per_completed_kwh is not None
    assert carb.emissions_per_completed_kwh > 0.0

    assert fifo.submitted_count == 20
    assert fifo.scheduled_count == 20
    assert fifo.completion_rate_pct == 100.0

    # Naive-Green dropped 2 jobs due to queue contention
    assert naive.submitted_count == 20
    assert naive.scheduled_count == 18
    assert naive.unscheduled_count == 2
    assert naive.completion_rate_pct == 90.0

    # Oracle dropped 1 job
    assert oracle.submitted_count == 20
    assert oracle.scheduled_count == 19
    assert oracle.unscheduled_count == 1
    assert oracle.completion_rate_pct == 95.0


def test_zero_executed_energy_safe_division():
    """Verifies that PolicyEvaluationSummary handles zero executed energy safely without division by zero."""
    summary = PolicyEvaluationSummary(
        policy="test_empty",
        total_emissions_gco2e=0.0,
        deadline_success_pct=0.0,
        waiting_time_mean_minutes=0.0,
        waiting_time_median_minutes=0.0,
        waiting_time_max_minutes=0.0,
        predicted_savings_gco2e=0.0,
        realized_savings_gco2e=0.0,
        oracle_gap_gco2e=0.0,
        scheduled_count=0,
        unscheduled_count=5,
        submitted_count=5,
        completion_rate_pct=0.0,
        total_energy_executed_kwh=0.0,
        emissions_per_completed_kwh=None,
    )
    assert summary.emissions_per_completed_kwh is None
    assert summary.completion_rate_pct == 0.0


def test_backward_compatibility_of_summary_schema():
    """Confirms that deserializing older JSON payloads without the new fields succeeds with defaults."""
    legacy_payload = {
        "policy": "legacy_fifo",
        "total_emissions_gco2e": 1500.0,
        "deadline_success_pct": 100.0,
        "waiting_time_mean_minutes": 10.0,
        "waiting_time_median_minutes": 5.0,
        "waiting_time_max_minutes": 30.0,
        "predicted_savings_gco2e": 0.0,
        "realized_savings_gco2e": 0.0,
        "oracle_gap_gco2e": 50.0,
        "scheduled_count": 10,
        "unscheduled_count": 0,
    }
    model = PolicyEvaluationSummary.model_validate(legacy_payload)
    assert model.submitted_count == 0
    assert model.completion_rate_pct is None
    assert model.total_energy_executed_kwh == 0.0
    assert model.emissions_per_completed_kwh is None


def test_real_trace_mode_output_isolation(tmp_path):
    """
    Verifies that run_real_trace_evaluation writes results to the specified results directory
    and does NOT modify or write files into scenarios directory.
    """
    custom_results_dir = tmp_path / "custom_results"

    # Capture scenario directory mtimes before run
    sc_dir = Path("data/scenarios")
    mtimes_before = {p: p.stat().st_mtime for p in sc_dir.glob("*.json")}

    # Run real trace evaluation targeting temporary results directory
    summary = run_real_trace_evaluation(
        scenarios_dir=sc_dir,
        results_dir=custom_results_dir,
        start_time=DEFAULT_EVALUATION_START,
        horizon_hours=36,
        max_capacity=2.0,
    )

    # Verify results written to custom_results_dir
    assert (custom_results_dir / "standard_batch_comparison.json").exists()
    assert (custom_results_dir / "resource_contention_comparison.json").exists()
    assert (custom_results_dir / "tight_deadlines_comparison.json").exists()
    assert (custom_results_dir / "urgent_only_comparison.json").exists()
    assert (custom_results_dir / "dashboard_carbonova_payload.json").exists()
    assert (custom_results_dir / "lambda_sensitivity.json").exists()
    assert (custom_results_dir / "forecast_noise_sensitivity.json").exists()
    assert (custom_results_dir / "rolling_backtest_report.json").exists()
    assert (custom_results_dir / "experiment_summary.json").exists()

    # Verify no scenario files were touched or rewritten
    for p, old_mtime in mtimes_before.items():
        assert p.stat().st_mtime == old_mtime, f"Scenario file was modified: {p}"

    assert summary["mode"] == "real_neso_2024"
    assert summary["provenance"]["provider_class"] == "NESORealTraceCarbonDataProvider"
    assert "scheduler_configuration" in summary
    assert "random_seeds" in summary
    assert "methodology_and_reproducibility" in summary


def test_synthetic_demo_mode_interface_intact():
    """Confirms run_synthetic_demo is callable and preserves its interface signature."""
    import inspect
    sig = inspect.signature(run_synthetic_demo)
    assert "csv_path" in sig.parameters
    assert "scenarios_dir" in sig.parameters
    assert "results_dir" in sig.parameters
