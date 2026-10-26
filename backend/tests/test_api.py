"""
Integration tests for FastAPI endpoints:
- GET /api/health
- GET /api/carbon
- POST /api/jobs
- POST /api/schedule/run
- GET /api/schedule/results
"""

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.storage import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    store.clear_jobs()
    yield
    store.clear_jobs()


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Member 2" in data["member_responsibility"]


def test_carbon_endpoint():
    response = client.get("/api/carbon?time_step_minutes=60")
    assert response.status_code == 200
    points = response.json()
    assert isinstance(points, list)
    assert len(points) > 0
    pt = points[0]
    assert "timestamp" in pt
    assert "predicted_carbon_intensity" in pt
    assert "slot_specific_uncertainty" in pt
    assert pt["provenance"] == "SYNTHETIC"


def test_jobs_submission_and_listing():
    now = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    job_payload = {
        "job_id": "api-job-1",
        "job_type": "training",
        "arrival_time": now.isoformat(),
        "deadline": (now + timedelta(hours=4)).isoformat(),
        "duration_minutes": 60,
        "energy_kwh": 12.0,
        "priority": 1,
        "deferrable": True,
        "resource_requirement": 2.0,
    }

    # Submit job
    res = client.post("/api/jobs", json=job_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["total_stored_jobs"] == 1
    assert data["initial_feasibility"]["api-job-1"] is True

    # List jobs
    list_res = client.get("/api/jobs")
    assert list_res.status_code == 200
    jobs = list_res.json()
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == "api-job-1"


def test_jobs_duplicate_ids_rejected():
    now = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    jobs_payload = [
        {
            "job_id": "dup-id",
            "arrival_time": now.isoformat(),
            "deadline": (now + timedelta(hours=2)).isoformat(),
            "duration_minutes": 60,
            "energy_kwh": 5.0,
        },
        {
            "job_id": "dup-id",
            "arrival_time": now.isoformat(),
            "deadline": (now + timedelta(hours=3)).isoformat(),
            "duration_minutes": 60,
            "energy_kwh": 5.0,
        },
    ]
    res = client.post("/api/jobs", json=jobs_payload)
    assert res.status_code == 422
    assert "Duplicate job IDs" in res.json()["detail"]


def test_schedule_run_endpoint_and_history():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    schedule_payload = {
        "jobs": [
            {
                "job_id": "job-api-sched",
                "arrival_time": now.isoformat(),
                "deadline": (now + timedelta(hours=4)).isoformat(),
                "duration_minutes": 60,
                "energy_kwh": 8.0,
                "deferrable": True,
            }
        ],
        "config": {
            "policy": "carbonova",
            "job_ordering": "earliest_arrival_first",
            "risk_lambda": 0.5,
            "min_improvement_margin": 0.05,
            "cluster": {
                "total_capacity": 4.0,
                "time_step_minutes": 60,
            },
        },
        "run_all_policies": True,
    }

    run_res = client.post("/api/schedule/run", json=schedule_payload)
    assert run_res.status_code == 200
    res_data = run_res.json()

    assert "fifo" in res_data["results"]
    assert "carbonova" in res_data["results"]
    assert "naive_green" in res_data["results"]
    assert "comparative_summary" in res_data

    # Query run history
    history_res = client.get("/api/schedule/results")
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert len(history_data) >= 1
    assert history_data[0]["job_count"] == 1


def test_schedule_run_with_absolute_score_margin():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    schedule_payload = {
        "jobs": [
            {
                "job_id": "job-api-abs",
                "arrival_time": now.isoformat(),
                "deadline": (now + timedelta(hours=3)).isoformat(),
                "duration_minutes": 60,
                "energy_kwh": 10.0,
                "deferrable": True,
            }
        ],
        "config": {
            "policy": "carbonova",
            "job_ordering": "least_deadline_slack_first",
            "risk_lambda": 1.0,
            "min_improvement_margin": 10.0,
            "margin_unit": "absolute_score",
        },
        "run_all_policies": False,
    }

    res = client.post("/api/schedule/run", json=schedule_payload)
    assert res.status_code == 200
    data = res.json()
    assert "carbonova" in data["results"]
    d = data["results"]["carbonova"]["decisions"][0]
    assert d["improvement_score"] is not None
    assert "gCO2eq/kWh" in d["reason"]
