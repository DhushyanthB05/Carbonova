"""
Unit tests for explainable decision records and ordering comparisons (EAF vs LDSF).
"""

from datetime import datetime, timedelta, timezone
import pytest

from backend.carbon.synthetic import create_mock_carbon_grid
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
    JobOrdering,
    PolicyType,
    SchedulerConfig,
)


@pytest.fixture
def base_time():
    return datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)


def test_explainability_decision_record_populated(base_time):
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 100.0, 150.0],
        uncertainties=[10.0, 10.0, 10.0],
        realized_values=[200.0, 100.0, 150.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="job-explain",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=5.0,
    )
    config = SchedulerConfig(policy=PolicyType.CARBONOVA, risk_lambda=0.5, min_improvement_margin=0.05)
    result = SchedulingEngine.run_policy([job], grid, config)

    assert len(result.decisions) == 1
    d = result.decisions[0]
    assert d.job_id == "job-explain"
    assert d.policy == PolicyType.CARBONOVA
    assert d.feasibility_status == FeasibilityStatus.SCHEDULED
    assert d.scheduled_start == base_time + timedelta(hours=1)
    assert d.scheduled_finish == base_time + timedelta(hours=2)
    assert d.predicted_carbon_intensity == 100.0
    assert d.slot_uncertainty == 10.0
    assert d.risk_score == 100.0 + 0.5 * 10.0  # 105.0
    assert d.earliest_risk_score == 200.0 + 0.5 * 10.0  # 205.0
    assert d.waiting_time_minutes == 60.0
    assert d.deadline_slack_minutes == 120.0
    assert "Delayed by 60m" in d.reason
    assert "risk reduction" in d.reason


def test_compare_orderings_eaf_vs_ldsf(base_time):
    """
    Scenario: Capacity = 1.0.
    Job 1 arrives at 10:00, deadline 13:00 (slack = 2h), duration 1h.
    Job 2 arrives at 10:30, deadline 11:30 (slack = 0h, urgent!), duration 1h.

    Under EAF (ordered by arrival time):
    Job 1 arrives at 10:00 -> evaluated first. Scheduled at 10:00-11:00.
    Job 2 arrives at 10:30 -> next slot is 11:00. 11:00-12:00 > deadline 11:30 -> Capacity infeasible!

    Under LDSF (ordered by slack):
    Job 2 has slack 0h vs Job 1 slack 2h -> Job 2 evaluated first!
    Job 2 gets next slot 11:00? Wait, 11:00 to 12:00 exceeds 11:30!
    """
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[100.0, 100.0, 100.0, 100.0],
        time_step_minutes=60,
    )
    cluster = ClusterConfig(total_capacity=1.0, time_step_minutes=60)

    # Job 1 arrives earlier (10:00), deadline 13:00 (slack = 120 min)
    j1 = Job(
        job_id="j1_early",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=1.0,
        resource_requirement=1.0,
    )
    # Job 2 arrives slightly later (10:15, snaps to 11:00), deadline 12:00 (slack = 45 min)
    j2 = Job(
        job_id="j2_tight",
        arrival_time=base_time + timedelta(minutes=15),
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=1.0,
        resource_requirement=1.0,
    )

    comparison = SchedulingEngine.compare_orderings(
        jobs=[j1, j2],
        carbon_grid=grid,
        policy=PolicyType.FIFO,
        cluster_config=cluster,
    )

    eaf_decisions = comparison["earliest_arrival_first"]["decisions"]
    ldsf_decisions = comparison["least_deadline_slack_first"]["decisions"]

    # In EAF: j1 arrived at 10:00, j2 arrived at 10:15 -> j1 is first
    assert eaf_decisions[0]["job_id"] == "j1_early"
    assert eaf_decisions[1]["job_id"] == "j2_tight"

    # In LDSF: j2 slack is (120 - 15 - 60) = 45m; j1 slack is (180 - 60) = 120m -> j2 is tighter!
    assert ldsf_decisions[0]["job_id"] == "j2_tight"
    assert ldsf_decisions[1]["job_id"] == "j1_early"


def test_run_all_policies_summary(base_time):
    grid = create_mock_carbon_grid(
        start_time=base_time,
        values=[200.0, 100.0],
        realized_values=[190.0, 110.0],
        time_step_minutes=60,
    )
    job = Job(
        job_id="batch-job",
        arrival_time=base_time,
        deadline=base_time + timedelta(hours=2),
        duration_minutes=60,
        energy_kwh=10.0,
    )
    multi_response = SchedulingEngine.run_all_policies([job], grid)

    assert "fifo" in multi_response.results
    assert "naive_green" in multi_response.results
    assert "carbonova" in multi_response.results
    assert "oracle" in multi_response.results
    assert multi_response.comparative_summary["total_jobs"] == 1
