"""
Forecast Isolation Verification Tests.

Proves that:
1. Online policies (FIFO, Naive-Green, Carbonova) NEVER access realized carbon observations.
2. Online policies operate successfully when realized values are entirely None (online mode).
3. Online policy decisions remain invariant regardless of what realized values are provided.
4. Only the perfect-forecast greedy oracle accesses realized carbon observations.
"""

from datetime import datetime, timedelta, timezone
import pytest

from backend.carbon.interface import CarbonForecastPoint, CarbonGrid
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
    PolicyType,
    SchedulerConfig,
)
from backend.scheduler.policies import (
    run_carbonova_policy,
    run_fifo_policy,
    run_naive_green_policy,
    run_oracle_policy,
)


@pytest.fixture
def base_time():
    return datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)


def test_online_policies_succeed_when_realized_values_are_none(base_time):
    """
    Online operation test: In real-time execution, realized carbon for future slots is None.
    FIFO, Naive-Green, and Carbonova must run flawlessly without errors.
    """
    points = [
        CarbonForecastPoint(
            timestamp=base_time + timedelta(hours=i),
            predicted_carbon_intensity=200.0 - i * 30.0,
            slot_specific_uncertainty=10.0 + i * 5.0,
            realized_carbon_intensity=None,  # FUTURE UNKNOWN
            provenance="LIVE_GRID",
        )
        for i in range(4)
    ]
    grid = CarbonGrid(points, time_step_minutes=60)

    job = Job(
        job_id="online-job",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=5.0,
    )

    # 1. FIFO
    res_fifo = run_fifo_policy([job], grid, SchedulerConfig(policy=PolicyType.FIFO))
    assert res_fifo.decisions[0].feasibility_status == FeasibilityStatus.SCHEDULED

    # 2. Naive-Green
    res_naive = run_naive_green_policy([job], grid, SchedulerConfig(policy=PolicyType.NAIVE_GREEN))
    assert res_naive.decisions[0].feasibility_status == FeasibilityStatus.SCHEDULED

    # 3. Carbonova
    res_carb = run_carbonova_policy([job], grid, SchedulerConfig(policy=PolicyType.CARBONOVA))
    assert res_carb.decisions[0].feasibility_status == FeasibilityStatus.SCHEDULED

    # 4. Oracle MUST fail because it cannot run without realized data
    with pytest.raises(ValueError) as exc:
        run_oracle_policy([job], grid, SchedulerConfig(policy=PolicyType.ORACLE))
    assert "Realized carbon intensity missing" in str(exc.value)


def test_online_policy_decisions_are_invariant_to_future_realized_values(base_time):
    """
    Proves that FIFO, Naive-Green, and Carbonova decisions do not change when future realized
    observations are altered, whereas Oracle adapts to the realized observations.
    """
    job = Job(
        job_id="invariance-job",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
    )

    # Grid A: Forecast says slot 1 (11:00) is greener (100 vs 200).
    # Realized A: slot 1 was indeed greener (80 vs 190).
    grid_a = CarbonGrid(
        [
            CarbonForecastPoint(
                timestamp=base_time,
                predicted_carbon_intensity=200.0,
                slot_specific_uncertainty=5.0,
                realized_carbon_intensity=190.0,
            ),
            CarbonForecastPoint(
                timestamp=base_time + timedelta(hours=1),
                predicted_carbon_intensity=100.0,
                slot_specific_uncertainty=5.0,
                realized_carbon_intensity=80.0,
            ),
        ],
        time_step_minutes=60,
    )

    # Grid B: Exact same forecast! But realized is reversed (slot 0 was 50, slot 1 backfired to 400).
    grid_b = CarbonGrid(
        [
            CarbonForecastPoint(
                timestamp=base_time,
                predicted_carbon_intensity=200.0,
                slot_specific_uncertainty=5.0,
                realized_carbon_intensity=50.0,  # Realized is much lower!
            ),
            CarbonForecastPoint(
                timestamp=base_time + timedelta(hours=1),
                predicted_carbon_intensity=100.0,
                slot_specific_uncertainty=5.0,
                realized_carbon_intensity=400.0,  # Realized spiked!
            ),
        ],
        time_step_minutes=60,
    )

    cfg_fifo = SchedulerConfig(policy=PolicyType.FIFO)
    cfg_naive = SchedulerConfig(policy=PolicyType.NAIVE_GREEN)
    cfg_carb = SchedulerConfig(policy=PolicyType.CARBONOVA, min_improvement_margin=0.05)
    cfg_oracle = SchedulerConfig(policy=PolicyType.ORACLE)

    # Run on Grid A
    d_fifo_a = run_fifo_policy([job], grid_a, cfg_fifo).decisions[0].scheduled_start
    d_naive_a = run_naive_green_policy([job], grid_a, cfg_naive).decisions[0].scheduled_start
    d_carb_a = run_carbonova_policy([job], grid_a, cfg_carb).decisions[0].scheduled_start
    d_oracle_a = run_oracle_policy([job], grid_a, cfg_oracle).decisions[0].scheduled_start

    # Run on Grid B
    d_fifo_b = run_fifo_policy([job], grid_b, cfg_fifo).decisions[0].scheduled_start
    d_naive_b = run_naive_green_policy([job], grid_b, cfg_naive).decisions[0].scheduled_start
    d_carb_b = run_carbonova_policy([job], grid_b, cfg_carb).decisions[0].scheduled_start
    d_oracle_b = run_oracle_policy([job], grid_b, cfg_oracle).decisions[0].scheduled_start

    # Invariance check: Online decisions must be identical across Grid A and Grid B
    assert d_fifo_a == d_fifo_b == base_time
    assert d_naive_a == d_naive_b == base_time + timedelta(hours=1)
    assert d_carb_a == d_carb_b == base_time + timedelta(hours=1)

    # Oracle check: Oracle changes from 11:00 in Grid A (80 gCO2) to 10:00 in Grid B (50 gCO2)
    assert d_oracle_a == base_time + timedelta(hours=1)
    assert d_oracle_b == base_time
