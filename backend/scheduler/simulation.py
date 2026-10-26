"""
Historical Trace Simulation Engine for Carbonova.

Enables retrospective, trace-driven simulation comparing:
  1. FIFO baseline policy
  2. Carbonova conservative carbon-aware policy

Key Methodological Guarantees:
  - Temporal Non-Leakage: Scheduling decisions receive only information available
    at decision time (historical observations up to T-1).
  - Retrospective Evaluation: Emissions are evaluated strictly after scheduling using
    actual historical outturn readings from the evaluation dataset during the job's
    active execution intervals.
  - Transparent Physical Modeling: Explicitly documents compute power (kW/unit)
    and 30-minute interval durations.
  - Reproducibility: Deterministic synthetic workload generation with configurable seed.
"""

from datetime import datetime, timedelta, timezone
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict

from backend.carbon.service import CarbonForecastService, PROJECT_ROOT
from backend.scheduler.engine import CarbonovaScheduler, FIFOScheduler
from backend.scheduler.schemas import DecisionType, SchedulingDecision, WorkloadJob

DEFAULT_TRACE_PATH = PROJECT_ROOT / "data" / "carbon_trace_2024_modeling.csv"

# Explicit physical and compute assumptions
DEFAULT_POWER_KW_PER_RESOURCE_UNIT: float = 0.7  # 700 Watts per GPU/accelerator unit
HALF_HOUR_DURATION_HOURS: float = 0.5             # 30 minutes = 0.5 hours


class SimulationAssumptions(BaseModel):
    """Documented physical and operational assumptions for emissions calculation."""
    model_config = ConfigDict(extra="forbid")

    power_kw_per_resource_unit: float = Field(
        default=DEFAULT_POWER_KW_PER_RESOURCE_UNIT,
        gt=0.0,
        description="Electrical power demand in kW per unit of workload resource demand."
    )
    interval_duration_hours: float = Field(
        default=HALF_HOUR_DURATION_HOURS,
        gt=0.0,
        description="Duration of each settlement interval in hours (0.5 for 30 minutes)."
    )


class JobSimulationResult(BaseModel):
    """Retrospective evaluation metrics for a single workload job."""
    model_config = ConfigDict(extra="forbid")

    job_id: str
    policy_name: str
    decision: DecisionType
    arrival_time_utc: datetime
    scheduled_start_utc: Optional[datetime] = None
    scheduled_completion_utc: Optional[datetime] = None
    deadline_time_utc: datetime
    waiting_time_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Delay between arrival and execution start in hours."
    )
    duration_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Total execution time in hours."
    )
    energy_kwh: float = Field(
        default=0.0,
        ge=0.0,
        description="Total electrical energy consumed in kWh."
    )
    actual_emissions_gco2: float = Field(
        default=0.0,
        ge=0.0,
        description="Retrospectively calculated actual emissions in grams CO2."
    )
    missed_deadline: bool = Field(
        default=False,
        description="True if job completed after deadline or was rejected due to deadline breach."
    )


class PolicySimulationSummary(BaseModel):
    """Aggregate simulation results for a scheduling policy across a workload trace."""
    model_config = ConfigDict(extra="forbid")

    policy_name: str
    total_jobs: int
    completed_jobs: int
    rejected_jobs: int
    deadline_misses: int
    total_energy_kwh: float
    total_emissions_gco2: float
    average_waiting_time_hours: float
    average_emissions_per_job_gco2: float
    job_results: List[JobSimulationResult]


class SimulationComparisonResult(BaseModel):
    """Side-by-side comparison between FIFO and Carbonova policies."""
    model_config = ConfigDict(extra="forbid")

    simulation_period_start_utc: datetime
    simulation_period_end_utc: datetime
    total_workload_jobs: int
    assumptions: SimulationAssumptions
    fifo_summary: PolicySimulationSummary
    carbonova_summary: PolicySimulationSummary
    emissions_difference_gco2: float = Field(
        description="Carbonova emissions minus FIFO emissions (negative means Carbonova emitted less)."
    )
    emissions_reduction_percent: float = Field(
        description="Percentage reduction in emissions: ((FIFO - Carbonova) / FIFO) * 100."
    )
    waiting_time_difference_hours: float = Field(
        description="Average Carbonova waiting time minus average FIFO waiting time."
    )


class SyntheticWorkloadGenerator:
    """
    Deterministic synthetic workload generator for reproducible scheduling evaluations.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(
        self,
        start_time_utc: datetime,
        num_jobs: int = 20,
        arrival_interval_minutes: int = 60,
        min_duration_half_hours: int = 1,
        max_duration_half_hours: int = 4,
        min_slack_half_hours: int = 2,
        max_slack_half_hours: int = 8,
        min_resource_demand: float = 1.0,
        max_resource_demand: float = 4.0,
        flexible_probability: float = 0.85,
    ) -> List[WorkloadJob]:
        """
        Generate a list of guaranteed-feasible WorkloadJob instances.
        """
        jobs: List[WorkloadJob] = []
        current_time = start_time_utc if start_time_utc.tzinfo else start_time_utc.replace(tzinfo=timezone.utc)

        for i in range(num_jobs):
            # Advance arrival time
            arrival_offset = timedelta(minutes=self.rng.randint(0, arrival_interval_minutes))
            job_arrival = current_time + arrival_offset

            duration = self.rng.randint(min_duration_half_hours, max_duration_half_hours)
            slack = self.rng.randint(min_slack_half_hours, max_slack_half_hours)

            # Deadline ensures feasibility at creation: arrival + duration + slack
            execution_time = timedelta(minutes=30 * duration)
            slack_time = timedelta(minutes=30 * slack)
            deadline = job_arrival + execution_time + slack_time

            resource = round(self.rng.uniform(min_resource_demand, max_resource_demand), 1)
            is_flex = self.rng.random() < flexible_probability

            jobs.append(
                WorkloadJob(
                    job_id=f"job_{i+1:03d}",
                    arrival_time_utc=job_arrival,
                    duration_half_hours=duration,
                    deadline_time_utc=deadline,
                    resource_demand=resource,
                    is_flexible=is_flex,
                )
            )

            # Advance baseline time for next job
            current_time = job_arrival

        return jobs


class TraceSimulationEngine:
    """
    Executes trace-driven evaluations using historical Great Britain carbon intensity data.
    """

    def __init__(
        self,
        trace_data_path: Optional[Union[str, Path]] = None,
        carbon_service: Optional[CarbonForecastService] = None,
        assumptions: Optional[SimulationAssumptions] = None,
    ) -> None:
        self.trace_path = Path(trace_data_path) if trace_data_path else DEFAULT_TRACE_PATH
        self.assumptions = assumptions or SimulationAssumptions()
        self.carbon_service = carbon_service

        self.df_trace = self._load_trace(self.trace_path)
        self.fifo_scheduler = FIFOScheduler()
        self.carbonova_scheduler = CarbonovaScheduler(carbon_service=self.carbon_service)

    @staticmethod
    def _load_trace(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"Trace dataset not found at: {path.resolve()}")

        df = pd.read_csv(path)
        df["dt"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df = df.sort_values("dt").reset_index(drop=True)

        intensity_col = (
            "modeled_intensity_gco2_per_kwh"
            if "modeled_intensity_gco2_per_kwh" in df.columns
            else "carbon_intensity_gco2_per_kwh"
        )
        df["actual_intensity"] = df[intensity_col].astype(float)
        return df[["dt", "actual_intensity"]]

    def _get_actual_intensity_for_slot(self, slot_dt: datetime) -> float:
        """Retrieve actual historical intensity for retrospective emissions accounting."""
        match = self.df_trace[self.df_trace["dt"] == slot_dt]
        if match.empty:
            # Fall back to nearest available slot if exact match is at edge
            nearest_idx = (self.df_trace["dt"] - slot_dt).abs().idxmin()
            return float(self.df_trace.loc[nearest_idx, "actual_intensity"])
        return float(match.iloc[0]["actual_intensity"])

    def _evaluate_decision(
        self,
        job: WorkloadJob,
        decision: SchedulingDecision,
    ) -> JobSimulationResult:
        """
        Retrospectively compute energy consumption and actual emissions for a decision.
        """
        if decision.decision != DecisionType.SCHEDULED or decision.scheduled_start_utc is None:
            return JobSimulationResult(
                job_id=job.job_id,
                policy_name=decision.policy_name,
                decision=decision.decision,
                arrival_time_utc=job.arrival_time_utc,
                deadline_time_utc=job.deadline_time_utc,
                waiting_time_hours=0.0,
                duration_hours=0.0,
                energy_kwh=0.0,
                actual_emissions_gco2=0.0,
                missed_deadline=True,
            )

        start_dt = decision.scheduled_start_utc
        completion_dt = decision.scheduled_completion_utc
        duration_hours = job.duration_half_hours * self.assumptions.interval_duration_hours
        waiting_time_hours = max(0.0, (start_dt - job.arrival_time_utc).total_seconds() / 3600.0)
        missed_deadline = completion_dt > job.deadline_time_utc

        # Energy per 30-minute interval
        power_kw = job.resource_demand * self.assumptions.power_kw_per_resource_unit
        energy_per_interval_kwh = power_kw * self.assumptions.interval_duration_hours
        total_energy_kwh = energy_per_interval_kwh * job.duration_half_hours

        # Retrospectively integrate actual emissions across each executed 30-min interval
        total_emissions_gco2 = 0.0
        for slot_idx in range(job.duration_half_hours):
            slot_time = start_dt + timedelta(minutes=30 * slot_idx)
            actual_intensity = self._get_actual_intensity_for_slot(slot_time)
            slot_emissions = energy_per_interval_kwh * actual_intensity
            total_emissions_gco2 += slot_emissions

        return JobSimulationResult(
            job_id=job.job_id,
            policy_name=decision.policy_name,
            decision=decision.decision,
            arrival_time_utc=job.arrival_time_utc,
            scheduled_start_utc=start_dt,
            scheduled_completion_utc=completion_dt,
            deadline_time_utc=job.deadline_time_utc,
            waiting_time_hours=round(waiting_time_hours, 4),
            duration_hours=round(duration_hours, 4),
            energy_kwh=round(total_energy_kwh, 4),
            actual_emissions_gco2=round(total_emissions_gco2, 2),
            missed_deadline=missed_deadline,
        )

    def _summarize_policy(
        self,
        policy_name: str,
        results: List[JobSimulationResult],
    ) -> PolicySimulationSummary:
        """Aggregate summary metrics for a policy."""
        total_jobs = len(results)
        completed_jobs = sum(1 for r in results if r.decision == DecisionType.SCHEDULED and not r.missed_deadline)
        rejected_jobs = sum(1 for r in results if r.decision == DecisionType.REJECTED_INFEASIBLE)
        deadline_misses = sum(1 for r in results if r.missed_deadline)

        total_energy = sum(r.energy_kwh for r in results)
        total_emissions = sum(r.actual_emissions_gco2 for r in results)
        avg_wait = (
            float(np.mean([r.waiting_time_hours for r in results if r.decision == DecisionType.SCHEDULED]))
            if completed_jobs > 0
            else 0.0
        )
        avg_emissions = total_emissions / completed_jobs if completed_jobs > 0 else 0.0

        return PolicySimulationSummary(
            policy_name=policy_name,
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            rejected_jobs=rejected_jobs,
            deadline_misses=deadline_misses,
            total_energy_kwh=round(total_energy, 4),
            total_emissions_gco2=round(total_emissions, 2),
            average_waiting_time_hours=round(avg_wait, 4),
            average_emissions_per_job_gco2=round(avg_emissions, 2),
            job_results=results,
        )

    def run_simulation(
        self,
        jobs: List[WorkloadJob],
        history: Optional[Any] = None,
        queue_start_time_utc: Optional[datetime] = None,
    ) -> SimulationComparisonResult:
        """
        Execute an identical workload trace against both FIFO and Carbonova policies,
        evaluating actual retrospective emissions from historical grid data.
        """
        if not jobs:
            raise ValueError("Cannot simulate an empty workload trace.")

        # Determine evaluation temporal boundary
        sim_start = min(j.arrival_time_utc for j in jobs)
        sim_end = max(j.deadline_time_utc for j in jobs)

        # 1. Run FIFO policy
        fifo_decisions = self.fifo_scheduler.schedule(jobs, queue_start_time_utc=queue_start_time_utc)
        fifo_results = [
            self._evaluate_decision(job, decision)
            for job, decision in zip(sorted(jobs, key=lambda x: x.arrival_time_utc), fifo_decisions)
        ]
        fifo_summary = self._summarize_policy(FIFOScheduler.POLICY_NAME, fifo_results)

        # 2. Run Carbonova policy
        carbonova_decisions = self.carbonova_scheduler.schedule(
            jobs,
            history=history,
            queue_start_time_utc=queue_start_time_utc,
        )
        carbonova_results = [
            self._evaluate_decision(job, decision)
            for job, decision in zip(sorted(jobs, key=lambda x: x.arrival_time_utc), carbonova_decisions)
        ]
        carbonova_summary = self._summarize_policy(CarbonovaScheduler.POLICY_NAME, carbonova_results)

        # 3. Compute comparative metrics
        emissions_diff = round(carbonova_summary.total_emissions_gco2 - fifo_summary.total_emissions_gco2, 2)
        if fifo_summary.total_emissions_gco2 > 0:
            reduction_pct = round(
                ((fifo_summary.total_emissions_gco2 - carbonova_summary.total_emissions_gco2) / fifo_summary.total_emissions_gco2) * 100.0,
                2,
            )
        else:
            reduction_pct = 0.0

        wait_diff = round(carbonova_summary.average_waiting_time_hours - fifo_summary.average_waiting_time_hours, 4)

        return SimulationComparisonResult(
            simulation_period_start_utc=sim_start,
            simulation_period_end_utc=sim_end,
            total_workload_jobs=len(jobs),
            assumptions=self.assumptions,
            fifo_summary=fifo_summary,
            carbonova_summary=carbonova_summary,
            emissions_difference_gco2=emissions_diff,
            emissions_reduction_percent=reduction_pct,
            waiting_time_difference_hours=wait_diff,
        )
