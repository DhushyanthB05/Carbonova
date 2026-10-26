"""
Focused tests for scenario generation and serialization.
Member 3: Evaluation, Metrics, and Reproducibility.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from backend.evaluation.scenarios import (
    DEFAULT_EVALUATION_START,
    DEFAULT_WINTER_START,
    generate_jobs,
    generate_standard_batch_scenario,
    generate_winter_scenario,
    load_jobs_from_json,
    save_jobs_to_json,
)
from backend.scheduler.models import Job


def test_default_start_date():
    """Verifies that scenario generators default to 2024 UTC dates."""
    jobs_std = generate_standard_batch_scenario()
    assert len(jobs_std) == 20
    assert jobs_std[0].arrival_time >= DEFAULT_EVALUATION_START
    assert jobs_std[0].arrival_time.tzinfo == timezone.utc

    jobs_winter = generate_winter_scenario()
    assert len(jobs_winter) == 20
    assert jobs_winter[0].arrival_time >= DEFAULT_WINTER_START
    assert jobs_winter[0].arrival_time.tzinfo == timezone.utc


def test_caller_supplied_custom_start_date():
    """Verifies caller-supplied custom start dates are respected."""
    custom_dt = datetime(2024, 9, 10, 8, 0, tzinfo=timezone.utc)
    jobs = generate_standard_batch_scenario(start_time=custom_dt, seed=99)
    assert jobs[0].arrival_time >= custom_dt
    assert jobs[0].arrival_time.tzinfo == timezone.utc

    # Test timezone-naive input conversion
    naive_dt = datetime(2024, 7, 15, 12, 0)
    jobs_naive = generate_jobs(start_time=naive_dt, seed=77)
    expected_utc = naive_dt.replace(tzinfo=timezone.utc)
    assert jobs_naive[0].arrival_time >= expected_utc
    assert jobs_naive[0].arrival_time.tzinfo == timezone.utc


def test_utc_serialization_of_timestamps():
    """Verifies that saved scenario JSONs format timestamps ending in 'Z' and reload correctly."""
    jobs = generate_standard_batch_scenario()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "test_scenario.json"
        save_jobs_to_json(jobs, tmp_path)

        with open(tmp_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        for item in raw_data:
            assert item["arrival_time"].endswith("Z"), f"Timestamp does not end in Z: {item['arrival_time']}"
            assert item["deadline"].endswith("Z"), f"Deadline does not end in Z: {item['deadline']}"

        loaded_jobs = load_jobs_from_json(tmp_path)
        assert len(loaded_jobs) == len(jobs)
        for original, loaded in zip(jobs, loaded_jobs):
            assert original.job_id == loaded.job_id
            assert original.arrival_time == loaded.arrival_time
            assert original.deadline == loaded.deadline
            assert loaded.arrival_time.tzinfo == timezone.utc


def test_scenario_horizon_and_deadlines():
    """Verifies arrivals and deadlines remain valid and within expected scenario horizons."""
    start = DEFAULT_EVALUATION_START
    horizon = 24
    jobs = generate_jobs(start_time=start, horizon_hours=horizon, n_jobs=30, seed=42)

    max_allowed_deadline = start + timedelta(hours=horizon + 12)
    for j in jobs:
        assert j.arrival_time >= start
        assert j.deadline > j.arrival_time
        assert j.deadline <= max_allowed_deadline
        # Ensure duration fits within arrival to deadline window
        window_minutes = (j.deadline - j.arrival_time).total_seconds() / 60.0
        assert j.duration_minutes <= window_minutes
