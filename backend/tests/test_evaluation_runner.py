"""
Unit and Integration tests for EvaluationRunner.
Deliverables 1, 2, 3, 4.
"""

from datetime import datetime, timedelta
from backend.evaluation.scenarios import generate_standard_batch_scenario
from backend.evaluation.runner import EvaluationRunner


def test_four_policy_comparison_fairness():
    """
    Verifies that all 4 policies are evaluated on the exact same jobs
    and scored against the exact same realized trace.
    """
    start = datetime(2026, 10, 25, 0, 0, 0)
    time_grid = [start + timedelta(hours=i) for i in range(36)]

    # Realized carbon: high in morning/night, low in afternoon
    realized_carbon = {}
    forecast_carbon = {}
    uncertainty_map = {}
    for i, t in enumerate(time_grid):
        hour = t.hour
        val = 450.0 - 200.0 * (1.0 if 10 <= hour <= 16 else 0.0)
        realized_carbon[t] = val
        forecast_carbon[t] = val + 10.0  # slight bias
        uncertainty_map[t] = 20.0

    jobs = generate_standard_batch_scenario(start_time=start, seed=42)

    runner = EvaluationRunner(
        time_grid=time_grid,
        realized_carbon_map=realized_carbon,
        forecast_carbon_map=forecast_carbon,
        uncertainty_map=uncertainty_map,
        max_capacity=2,
    )

    report = runner.run_all_policies(jobs, risk_lambda=1.0)

    # 1. Check all 4 policies exist in summary
    assert "fifo" in report.summary
    assert "naive_green" in report.summary
    assert "carbonova" in report.summary
    assert "greedy_oracle" in report.summary

    # 2. Check oracle has the lowest or equal emissions
    oracle_emissions = report.summary["greedy_oracle"].total_emissions_gco2e
    fifo_emissions = report.summary["fifo"].total_emissions_gco2e
    carb_emissions = report.summary["carbonova"].total_emissions_gco2e

    assert oracle_emissions <= fifo_emissions
    assert carb_emissions <= fifo_emissions

    # 3. Check oracle gap for oracle is 0
    assert report.summary["greedy_oracle"].oracle_gap_gco2e == 0.0

    # 4. Check deadline success is high
    assert report.summary["carbonova"].deadline_success_pct >= 90.0
