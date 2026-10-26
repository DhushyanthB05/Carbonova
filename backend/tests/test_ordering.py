"""
Unit tests for deterministic job ordering (EAF and LDSF) and tie-breaking.
"""

from datetime import datetime, timedelta, timezone
from backend.scheduler.models import Job, JobOrdering
from backend.scheduler.ordering import compute_job_slack_seconds, sort_jobs


def test_earliest_arrival_first_ordering():
    t0 = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    j1 = Job(
        job_id="job-late",
        arrival_time=t0 + timedelta(hours=2),
        deadline=t0 + timedelta(hours=6),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    j2 = Job(
        job_id="job-early",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=5),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    j3 = Job(
        job_id="job-early-urgent",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    ordered = sort_jobs([j1, j2, j3], ordering=JobOrdering.EARLIEST_ARRIVAL_FIRST)
    # Both j2 and j3 arrive at t0, but j3 has earlier deadline (t0+3h vs t0+5h)
    assert [j.job_id for j in ordered] == ["job-early-urgent", "job-early", "job-late"]


def test_least_deadline_slack_first_ordering():
    t0 = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    # j1: window 3 hours, duration 1 hr -> slack = 2 hours
    j1 = Job(
        job_id="j-slack-2h",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=3),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    # j2: window 4 hours, duration 3 hrs -> slack = 1 hour (more urgent!)
    j2 = Job(
        job_id="j-slack-1h",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=4),
        duration_minutes=180,
        energy_kwh=1.0,
    )
    # j3: window 1 hour, duration 1 hr -> slack = 0 hours (most urgent!)
    j3 = Job(
        job_id="j-slack-0h",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=1),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    ordered = sort_jobs([j1, j2, j3], ordering=JobOrdering.LEAST_DEADLINE_SLACK_FIRST)
    assert [j.job_id for j in ordered] == ["j-slack-0h", "j-slack-1h", "j-slack-2h"]


def test_deterministic_tie_breaker_by_job_id():
    t0 = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    # Identical parameters except job_id
    j_b = Job(
        job_id="job-B",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=4),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    j_a = Job(
        job_id="job-A",
        arrival_time=t0,
        deadline=t0 + timedelta(hours=4),
        duration_minutes=60,
        energy_kwh=1.0,
    )
    ordered_eaf = sort_jobs([j_b, j_a], ordering=JobOrdering.EARLIEST_ARRIVAL_FIRST)
    assert [j.job_id for j in ordered_eaf] == ["job-A", "job-B"]

    ordered_ldsf = sort_jobs([j_b, j_a], ordering=JobOrdering.LEAST_DEADLINE_SLACK_FIRST)
    assert [j.job_id for j in ordered_ldsf] == ["job-A", "job-B"]
