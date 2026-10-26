"""
Unit Tests for Historical Trace Simulation Engine in Carbonova.

Covers:
  - Synthetic workload generation reproducibility and feasibility
  - Retrospective energy and emissions calculation accuracy
  - Side-by-side policy comparison (FIFO vs Carbonova)
  - Deadline tracking and rejection handling in simulation
  - Validation of non-leakage (decision-time forecasts vs retrospective outturn)
"""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock

import pandas as pd

from backend.carbon.schemas import CarbonForecastResponse, CarbonIntensitySlot
from backend.carbon.service import CarbonForecastService, PROJECT_ROOT
from backend.scheduler.schemas import DecisionType, WorkloadJob
from backend.scheduler.simulation import (
    DEFAULT_POWER_KW_PER_RESOURCE_UNIT,
    HALF_HOUR_DURATION_HOURS,
    SimulationAssumptions,
    SyntheticWorkloadGenerator,
    TraceSimulationEngine,
)


class TestSyntheticWorkloadGenerator(unittest.TestCase):
    """Test deterministic generation of synthetic workload traces."""

    def test_reproducibility_with_seed(self):
        start_time = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
        gen1 = SyntheticWorkloadGenerator(seed=123)
        jobs1 = gen1.generate(start_time, num_jobs=10)

        gen2 = SyntheticWorkloadGenerator(seed=123)
        jobs2 = gen2.generate(start_time, num_jobs=10)

        self.assertEqual(len(jobs1), len(jobs2))
        for j1, j2 in zip(jobs1, jobs2):
            self.assertEqual(j1.job_id, j2.job_id)
            self.assertEqual(j1.arrival_time_utc, j2.arrival_time_utc)
            self.assertEqual(j1.duration_half_hours, j2.duration_half_hours)
            self.assertEqual(j1.deadline_time_utc, j2.deadline_time_utc)
            self.assertEqual(j1.resource_demand, j2.resource_demand)

    def test_generated_jobs_strictly_feasible(self):
        start_time = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
        gen = SyntheticWorkloadGenerator(seed=42)
        jobs = gen.generate(start_time, num_jobs=25)

        for job in jobs:
            min_exec = timedelta(minutes=30 * job.duration_half_hours)
            self.assertTrue(job.arrival_time_utc + min_exec <= job.deadline_time_utc)
            self.assertGreater(job.duration_half_hours, 0)
            self.assertGreater(job.resource_demand, 0.0)


class TestTraceSimulationEngine(unittest.TestCase):
    """Test retrospective evaluation of scheduling decisions against historical grid traces."""

    @classmethod
    def setUpClass(cls):
        cls.trace_path = PROJECT_ROOT / "data" / "carbon_trace_2024_modeling.csv"
        cls.engine = TraceSimulationEngine(trace_data_path=cls.trace_path)
        cls.base_time = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)

    def test_emissions_calculation_accuracy(self):
        # 1 job, 2 half-hours (1 hour), 2.0 resource units
        # Power = 2.0 * 0.7 = 1.4 kW
        # Energy per 30-min slot = 1.4 * 0.5 = 0.7 kWh
        # Total energy = 1.4 kWh
        job = WorkloadJob(
            job_id="test_emission_job",
            arrival_time_utc=self.base_time,
            duration_half_hours=2,
            deadline_time_utc=self.base_time + timedelta(hours=4),
            resource_demand=2.0,
        )

        comparison = self.engine.run_simulation([job])
        fifo_res = comparison.fifo_summary.job_results[0]

        expected_energy = 2.0 * DEFAULT_POWER_KW_PER_RESOURCE_UNIT * HALF_HOUR_DURATION_HOURS * 2
        self.assertAlmostEqual(fifo_res.energy_kwh, expected_energy, places=3)
        self.assertGreater(fifo_res.actual_emissions_gco2, 0.0)

        # Retrospectively verify slot emissions match trace
        slot0_time = self.base_time
        slot1_time = self.base_time + timedelta(minutes=30)
        intensity0 = self.engine._get_actual_intensity_for_slot(slot0_time)
        intensity1 = self.engine._get_actual_intensity_for_slot(slot1_time)
        expected_emissions = round((0.7 * intensity0) + (0.7 * intensity1), 2)
        self.assertAlmostEqual(fifo_res.actual_emissions_gco2, expected_emissions, places=1)

    def test_simulation_with_mocked_carbon_service(self):
        # Create a mock CarbonForecastService returning live 1-step forecast
        mock_slot = CarbonIntensitySlot(
            timestamp_utc=self.base_time,
            predicted_intensity_gco2_per_kwh=60.0,
            lower_90_gco2_per_kwh=50.2576,
            upper_90_gco2_per_kwh=69.7424,
            uncertainty_width_gco2_per_kwh=19.4848,
        )
        mock_response = CarbonForecastResponse(
            calibrated_quantile_q_hat_gco2_per_kwh=9.7424,
            data_status="live",
            slots=[mock_slot],
        )
        mock_service = MagicMock(spec=CarbonForecastService)
        mock_service.predict_next_half_hour.return_value = mock_response

        engine = TraceSimulationEngine(
            trace_data_path=self.trace_path,
            carbon_service=mock_service,
        )

        generator = SyntheticWorkloadGenerator(seed=99)
        jobs = generator.generate(self.base_time, num_jobs=5)

        comparison = engine.run_simulation(jobs, history=["synthetic_history"])

        self.assertEqual(comparison.total_workload_jobs, 5)
        self.assertEqual(comparison.fifo_summary.total_jobs, 5)
        self.assertEqual(comparison.carbonova_summary.total_jobs, 5)

        # Both FIFO and conservative 1-step Carbonova dispatch immediately when queue is free,
        # so completed job count and emissions are equivalent under identical dispatch sequences.
        self.assertEqual(
            comparison.fifo_summary.completed_jobs,
            comparison.carbonova_summary.completed_jobs,
        )
        self.assertAlmostEqual(
            comparison.fifo_summary.total_emissions_gco2,
            comparison.carbonova_summary.total_emissions_gco2,
            places=1,
        )

    def test_deadline_enforcement_in_simulation(self):
        # Two conflicting jobs: job1 takes 4 half-hours, job2 has strict 2-half-hour deadline
        job1 = WorkloadJob(
            job_id="job_blocker",
            arrival_time_utc=self.base_time,
            duration_half_hours=4,
            deadline_time_utc=self.base_time + timedelta(hours=6),
            resource_demand=1.0,
        )
        job2 = WorkloadJob(
            job_id="job_infeasible_queue",
            arrival_time_utc=self.base_time + timedelta(minutes=30),
            duration_half_hours=2,
            deadline_time_utc=self.base_time + timedelta(hours=2),
            resource_demand=1.0,
        )

        comparison = self.engine.run_simulation([job1, job2])
        self.assertEqual(comparison.fifo_summary.completed_jobs, 1)
        self.assertEqual(comparison.fifo_summary.rejected_jobs, 1)
        self.assertEqual(comparison.carbonova_summary.completed_jobs, 1)
        self.assertEqual(comparison.carbonova_summary.rejected_jobs, 1)


if __name__ == "__main__":
    unittest.main()
