"""
Reproducible Workload and Scenario Generator.
Owned by Member 3 (Sairam) — Evaluation, Metrics & Testing.
Deliverable 1 & 6.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from backend.scheduler.models import Job

# Authoritative standard evaluation benchmark anchor dates for the 2024 GB NESO trace
DEFAULT_EVALUATION_START = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
DEFAULT_WINTER_START = datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)


def generate_jobs(
    start_time: Optional[datetime] = None,
    horizon_hours: int = 24,
    n_jobs: int = 20,
    seed: int = 42,
    deferrable_prob: float = 0.8,
    slack_multiplier: float = 2.5,
    max_resource_req: int = 1,
) -> List[Job]:
    """
    Generates a deterministic, reproducible set of AI jobs.
    Uses frozen random seed for exact reproducibility across runs.
    Defaults start_time to DEFAULT_EVALUATION_START (June 1, 2024 UTC) if None.
    """
    if start_time is None:
        start_time = DEFAULT_EVALUATION_START
    elif start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    else:
        start_time = start_time.astimezone(timezone.utc)

    rng = random.Random(seed)
    jobs: List[Job] = []

    job_types = [
        {"type": "training", "duration_range": (120, 240), "energy_range": (4.0, 10.0), "weight": 2},
        {"type": "fine_tuning", "duration_range": (60, 120), "energy_range": (1.5, 4.0), "weight": 3},
        {"type": "batch_inference", "duration_range": (30, 60), "energy_range": (0.5, 1.8), "weight": 5},
    ]

    population = []
    weights = []
    for jt in job_types:
        population.append(jt)
        weights.append(jt["weight"])

    for i in range(1, n_jobs + 1):
        job_id = f"job-{seed}-{i:03d}"
        selected_jt = rng.choices(population, weights=weights, k=1)[0]
        duration = rng.randint(*selected_jt["duration_range"])
        # Align duration to 30 or 60 minute increments
        duration = ((duration + 29) // 30) * 30
        energy = round(rng.uniform(*selected_jt["energy_range"]), 2)

        # Arrival time distributed within the first half/three-quarters of the horizon
        max_arrival_offset = max(0, int((horizon_hours * 60) - (duration * slack_multiplier)))
        arrival_minute = rng.randint(0, max(max_arrival_offset, 0))
        # Round arrival to hour boundaries for clean slotting
        arrival_hour = arrival_minute // 60
        arrival = start_time + timedelta(hours=arrival_hour)

        # Deferrable flag
        is_deferrable = rng.random() < deferrable_prob

        # Deadline slack
        if is_deferrable:
            available_window = max(int(duration * slack_multiplier), duration + 60)
            deadline = arrival + timedelta(minutes=available_window)
        else:
            # Urgent job: deadline is immediate execution window plus small buffer
            deadline = arrival + timedelta(minutes=duration + 30)

        # Ensure deadline doesn't exceed start_time + horizon_hours + 12h
        max_horizon_dt = start_time + timedelta(hours=horizon_hours + 12)
        if deadline > max_horizon_dt:
            deadline = max_horizon_dt
        if deadline <= arrival + timedelta(minutes=duration):
            deadline = arrival + timedelta(minutes=duration + 60)

        priority = rng.choice([1, 2, 3])
        resource_req = float(rng.randint(1, max_resource_req))

        jobs.append(
            Job(
                job_id=job_id,
                job_type=selected_jt["type"],
                arrival_time=arrival,
                deadline=deadline,
                duration_minutes=duration,
                energy_kwh=energy,
                priority=priority,
                deferrable=is_deferrable,
                resource_requirement=resource_req,
            )
        )

    # Sort deterministically by arrival, priority, job_id
    jobs.sort(key=lambda j: (j.arrival_time, j.priority, j.job_id))
    return jobs


def generate_standard_batch_scenario(start_time: Optional[datetime] = None, seed: int = 42) -> List[Job]:
    """Standard 24-hour evaluation scenario with 20 jobs."""
    return generate_jobs(
        start_time=start_time,
        horizon_hours=24,
        n_jobs=20,
        seed=seed,
        deferrable_prob=0.8,
        slack_multiplier=2.5,
    )


def generate_resource_contention_scenario(start_time: Optional[datetime] = None, seed: int = 42) -> List[Job]:
    """High-density scenario with 35 jobs arriving in tight intervals to stress capacity."""
    return generate_jobs(
        start_time=start_time,
        horizon_hours=18,
        n_jobs=35,
        seed=seed,
        deferrable_prob=0.9,
        slack_multiplier=3.0,
    )


def generate_tight_deadline_scenario(start_time: Optional[datetime] = None, seed: int = 42) -> List[Job]:
    """Low slack scenario where jobs have minimal room to shift."""
    return generate_jobs(
        start_time=start_time,
        horizon_hours=24,
        n_jobs=20,
        seed=seed,
        deferrable_prob=0.8,
        slack_multiplier=1.2,
    )


def generate_urgent_only_scenario(start_time: Optional[datetime] = None, seed: int = 42) -> List[Job]:
    """
    Control scenario: All jobs are non-deferrable (urgent).
    Sanity check to prove backfire rate = None (N/A) and waiting time ~ 0.
    """
    return generate_jobs(
        start_time=start_time,
        horizon_hours=24,
        n_jobs=15,
        seed=seed,
        deferrable_prob=0.0,
        slack_multiplier=1.0,
    )


def generate_winter_scenario(start_time: Optional[datetime] = None, seed: int = 42) -> List[Job]:
    """
    Winter high-uncertainty evaluation scenario.
    Defaults to DEFAULT_WINTER_START (January 15, 2024).
    """
    actual_start = start_time if start_time is not None else DEFAULT_WINTER_START
    return generate_jobs(
        start_time=actual_start,
        horizon_hours=24,
        n_jobs=20,
        seed=seed,
        deferrable_prob=0.8,
        slack_multiplier=2.5,
    )


def save_jobs_to_json(jobs: List[Job], filepath: str | Path) -> None:
    """Saves a job list to a JSON file using consistent ISO-8601 UTC representation ending in Z."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = []
    for j in jobs:
        d = j.model_dump(mode="json")
        # Ensure consistent ISO-8601 UTC representation ending in Z
        if "arrival_time" in d and isinstance(d["arrival_time"], str):
            d["arrival_time"] = d["arrival_time"].replace("+00:00", "Z")
            if not d["arrival_time"].endswith("Z"):
                d["arrival_time"] += "Z"
        if "deadline" in d and isinstance(d["deadline"], str):
            d["deadline"] = d["deadline"].replace("+00:00", "Z")
            if not d["deadline"].endswith("Z"):
                d["deadline"] += "Z"
        serialized.append(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2)


def load_jobs_from_json(filepath: str | Path) -> List[Job]:
    """Loads a job list from a JSON file."""
    path = Path(filepath)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Job.model_validate(item) for item in data]
