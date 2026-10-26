"""
Result Storage and Reproducibility Persistence.
Owned by Member 3 (Sairam) — Evaluation, Metrics & Testing.
Deliverables 6 & Dashboard integration format (Section 11.2).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from backend.evaluation.runner import EvaluationReport


DEFAULT_RESULTS_DIR = Path("data/results")


def save_evaluation_report(report: EvaluationReport, output_dir: str | Path = DEFAULT_RESULTS_DIR) -> Path:
    """
    Saves full EvaluationReport to a formatted JSON file.
    """
    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{report.evaluation_id}.json"

    data = report.model_dump(mode="json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return file_path


def load_evaluation_report(file_path: str | Path) -> EvaluationReport:
    """
    Loads an EvaluationReport from a JSON file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EvaluationReport.model_validate(data)


def export_dashboard_payload(report: EvaluationReport, policy_name: str = "carbonova") -> dict[str, Any]:
    """
    Converts evaluation results to the exact schema specified in Section 11.2 of Master Spec
    for consumption by Member 4's frontend dashboard.
    """
    if policy_name not in report.detailed_schedules:
        raise ValueError(f"Policy '{policy_name}' not found in evaluation report.")

    sched = report.detailed_schedules[policy_name]
    summary = report.summary[policy_name]

    jobs_payload = []
    for j in sched.scheduled_jobs:
        jobs_payload.append(
            {
                "job_id": j.job_id,
                "scheduled_start": j.scheduled_start.isoformat(),
                "scheduled_finish": j.scheduled_finish.isoformat(),
                "predicted_intensity": j.predicted_intensity,
                "uncertainty": j.uncertainty,
                "risk_score": j.risk_score,
                "explanation": j.explanation,
                "is_delayed": j.is_delayed,
                "realized_emissions_gco2e": j.realized_emissions_gco2e,
                "backfired": j.backfired,
            }
        )

    submitted_count = getattr(summary, "submitted_count", len(sched.scheduled_jobs) + len(sched.unscheduled_jobs))

    return {
        "run_id": report.evaluation_id,
        "trace_provenance": report.trace_provenance,
        "policy": policy_name,
        "risk_lambda": sched.risk_lambda,
        "jobs": jobs_payload,
        "metrics": {
            "total_emissions_gco2e": summary.total_emissions_gco2e,
            "emissions_reduction_vs_fifo_pct": summary.emissions_reduction_vs_fifo_pct,
            "deadline_success_pct": summary.deadline_success_pct,
            "backfire_rate_pct": summary.backfire_rate_pct,
            "mean_waiting_minutes": summary.waiting_time_mean_minutes,
            "predicted_savings_gco2e": summary.predicted_savings_gco2e,
            "realized_savings_gco2e": summary.realized_savings_gco2e,
            "oracle_gap_gco2e": summary.oracle_gap_gco2e,
            "submitted_count": submitted_count,
            "scheduled_count": summary.scheduled_count,
            "unscheduled_count": summary.unscheduled_count,
            "completion_rate_pct": getattr(summary, "completion_rate_pct", None),
            "total_energy_executed_kwh": getattr(summary, "total_energy_executed_kwh", 0.0),
            "emissions_per_completed_kwh": getattr(summary, "emissions_per_completed_kwh", None),
        },
    }
