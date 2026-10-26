"""
Tests for Rolling Backtesting and Multi-Window Evaluation.
Section 9.1 & 14 of Master Specification.
"""

from datetime import datetime, timedelta
from backend.evaluation.backtest import RollingBacktestRunner


def test_rolling_backtest_execution():
    start = datetime(2026, 10, 25, 0, 0, 0)
    # 48 hours of time grid
    time_grid = [start + timedelta(hours=i) for i in range(48)]
    realized_carbon = {t: 300.0 + 100.0 * (1 if 8 <= t.hour <= 18 else -1) for t in time_grid}
    forecast_carbon = {t: val + 15.0 for t, val in realized_carbon.items()}
    uncertainty_map = {t: 20.0 for t in time_grid}

    backtester = RollingBacktestRunner(
        full_time_grid=time_grid,
        realized_carbon_map=realized_carbon,
        forecast_carbon_map=forecast_carbon,
        uncertainty_map=uncertainty_map,
        window_hours=24,
        step_hours=12,
        jobs_per_window=10,
        max_capacity=2,
    )

    report = backtester.run(base_seed=42)

    assert report.window_count > 1
    assert "carbonova" in report.policy_aggregates
    assert "fifo" in report.policy_aggregates

    carb_stats = report.policy_aggregates["carbonova"]
    assert carb_stats.total_emissions_gco2e.mean > 0.0
    assert carb_stats.mean_waiting_minutes.mean >= 0.0
