"""
Unit Tests for Carbonova Scheduler Schemas, FIFO Baseline, and Carbonova Policy.

Covers:
  - WorkloadJob validation (valid creation, duration <= 0, arrival > deadline, infeasible duration)
  - SchedulingDecision validation (bounds integrity, timestamp sequencing, JSON serialization)
  - FIFOScheduler (arrival ordering, completion time calculation, deadline rejection)
  - CarbonovaScheduler with mocked CarbonForecastService (forecast integration, bounds propagation)
  - CarbonovaScheduler fallback behavior (missing history, forecast errors, degraded data)
  - WorkloadScheduler coordinator interface
"""

from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from backend.carbon.schemas import CarbonForecastResponse, CarbonIntensitySlot
from backend.carbon.service import CarbonForecastService
from backend.scheduler.engine import (
    CarbonovaScheduler,
    FIFOScheduler,
    WorkloadScheduler,
)
from backend.scheduler.schemas import (
    DecisionType,
    SchedulingDecision,
    WorkloadJob,
)


class TestWorkloadJobSchema(unittest.TestCase):
    """Test Pydantic validation rules for WorkloadJob."""

    def test_valid_workload_job_creation(self):
        arrival = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        deadline = datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc)
        job = WorkloadJob(
            job_id="job_001",
            arrival_time_utc=arrival,
            duration_half_hours=4,  # 2 hours
            deadline_time_utc=deadline,
            resource_demand=1.0,
            is_flexible=True,
        )
        self.assertEqual(job.job_id, "job_001")
        self.assertEqual(job.duration_half_hours, 4)
        self.assertTrue(job.is_flexible)
        self.assertEqual(job.arrival_time_utc.tzinfo, timezone.utc)

    def test_duration_must_be_positive(self):
        arrival = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        deadline = datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValidationError):
            WorkloadJob(
                job_id="bad_job",
                arrival_time_utc=arrival,
                duration_half_hours=0,
                deadline_time_utc=deadline,
                resource_demand=1.0,
            )

    def test_arrival_after_deadline_raises(self):
        arrival = datetime(2024, 6, 1, 15, 0, tzinfo=timezone.utc)
        deadline = datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValidationError) as ctx:
            WorkloadJob(
                job_id="bad_job",
                arrival_time_utc=arrival,
                duration_half_hours=2,
                deadline_time_utc=deadline,
                resource_demand=1.0,
            )
        self.assertIn("arrival_time_utc", str(ctx.exception))

    def test_duration_exceeding_deadline_window_raises(self):
        # Window is 1 hour (2 half-hours), but job requires 3 half-hours
        arrival = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        deadline = datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValidationError) as ctx:
            WorkloadJob(
                job_id="infeasible_job",
                arrival_time_utc=arrival,
                duration_half_hours=3,  # requires 1.5 hours
                deadline_time_utc=deadline,
                resource_demand=1.0,
            )
        self.assertIn("Infeasible job", str(ctx.exception))

    def test_negative_resource_demand_raises(self):
        arrival = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        deadline = datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValidationError):
            WorkloadJob(
                job_id="bad_job",
                arrival_time_utc=arrival,
                duration_half_hours=2,
                deadline_time_utc=deadline,
                resource_demand=-1.0,
            )

    def test_job_json_serialization(self):
        job = WorkloadJob(
            job_id="job_json",
            arrival_time_utc=datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
            duration_half_hours=2,
            deadline_time_utc=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
            resource_demand=2.5,
        )
        json_str = job.model_dump_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["job_id"], "job_json")
        self.assertEqual(parsed["duration_half_hours"], 2)


class TestSchedulingDecisionSchema(unittest.TestCase):
    """Test validation and serialization for SchedulingDecision."""

    def test_scheduled_decision_validation(self):
        start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        completion = datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc)
        decision = SchedulingDecision(
            job_id="job_001",
            policy_name="FIFO",
            decision=DecisionType.SCHEDULED,
            scheduled_start_utc=start,
            scheduled_completion_utc=completion,
            reason="Scheduled successfully.",
        )
        self.assertEqual(decision.decision, DecisionType.SCHEDULED)
        self.assertEqual(decision.scheduled_start_utc, start)

    def test_scheduled_decision_missing_times_raises(self):
        with self.assertRaises(ValidationError):
            SchedulingDecision(
                job_id="job_001",
                policy_name="FIFO",
                decision=DecisionType.SCHEDULED,
                scheduled_start_utc=None,
                scheduled_completion_utc=None,
                reason="Scheduled but missing times.",
            )

    def test_scheduled_start_after_completion_raises(self):
        start = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
        completion = datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValidationError):
            SchedulingDecision(
                job_id="job_001",
                policy_name="FIFO",
                decision=DecisionType.SCHEDULED,
                scheduled_start_utc=start,
                scheduled_completion_utc=completion,
                reason="Invalid chronological order.",
            )

    def test_decision_json_serialization(self):
        decision = SchedulingDecision(
            job_id="job_002",
            policy_name="Carbonova_Conservative",
            decision=DecisionType.SCHEDULED,
            scheduled_start_utc=datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
            scheduled_completion_utc=datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc),
            predicted_carbon_intensity_gco2_per_kwh=65.5,
            lower_90_gco2_per_kwh=55.7576,
            upper_90_gco2_per_kwh=75.2424,
            uncertainty_width_gco2_per_kwh=19.4848,
            reason="Forecasted and scheduled.",
            data_status="live",
        )
        json_str = decision.model_dump_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["policy_name"], "Carbonova_Conservative")
        self.assertEqual(parsed["predicted_carbon_intensity_gco2_per_kwh"], 65.5)
        self.assertEqual(parsed["data_status"], "live")


class TestFIFOScheduler(unittest.TestCase):
    """Test FIFO baseline scheduling behavior."""

    def setUp(self):
        self.scheduler = FIFOScheduler()
        self.base_time = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)

    def test_empty_job_list(self):
        decisions = self.scheduler.schedule([])
        self.assertEqual(decisions, [])

    def test_fifo_arrival_ordering(self):
        # Submit jobs in reverse arrival order
        job2 = WorkloadJob(
            job_id="job_late",
            arrival_time_utc=self.base_time + timedelta(hours=1),
            duration_half_hours=2,
            deadline_time_utc=self.base_time + timedelta(hours=5),
            resource_demand=1.0,
        )
        job1 = WorkloadJob(
            job_id="job_early",
            arrival_time_utc=self.base_time,
            duration_half_hours=2,
            deadline_time_utc=self.base_time + timedelta(hours=5),
            resource_demand=1.0,
        )

        decisions = self.scheduler.schedule([job2, job1])

        self.assertEqual(len(decisions), 2)
        # First scheduled must be job_early
        self.assertEqual(decisions[0].job_id, "job_early")
        self.assertEqual(decisions[0].scheduled_start_utc, self.base_time)
        self.assertEqual(decisions[0].scheduled_completion_utc, self.base_time + timedelta(hours=1))

        # Second scheduled must be job_late, starting after job_early completes
        self.assertEqual(decisions[1].job_id, "job_late")
        self.assertEqual(decisions[1].scheduled_start_utc, self.base_time + timedelta(hours=1))
        self.assertEqual(decisions[1].scheduled_completion_utc, self.base_time + timedelta(hours=2))

    def test_completion_time_calculation(self):
        # 3 half-hours = 1.5 hours
        job = WorkloadJob(
            job_id="job_calc",
            arrival_time_utc=self.base_time,
            duration_half_hours=3,
            deadline_time_utc=self.base_time + timedelta(hours=4),
            resource_demand=1.0,
        )
        decisions = self.scheduler.schedule([job])

        self.assertEqual(decisions[0].decision, DecisionType.SCHEDULED)
        self.assertEqual(decisions[0].scheduled_start_utc, self.base_time)
        self.assertEqual(decisions[0].scheduled_completion_utc, self.base_time + timedelta(minutes=90))

    def test_deadline_enforcement_and_rejection(self):
        # Job 1 runs from 10:00 to 12:00 (4 half-hours)
        job1 = WorkloadJob(
            job_id="job_blocker",
            arrival_time_utc=self.base_time,
            duration_half_hours=4,
            deadline_time_utc=self.base_time + timedelta(hours=6),
            resource_demand=1.0,
        )
        # Job 2 arrives at 10:30, needs 1 hour (2 half-hours), but has strict deadline of 12:00
        # Because Job 1 occupies queue until 12:00, Job 2 cannot finish until 13:00 -> infeasible!
        job2 = WorkloadJob(
            job_id="job_tight_deadline",
            arrival_time_utc=self.base_time + timedelta(minutes=30),
            duration_half_hours=2,
            deadline_time_utc=self.base_time + timedelta(hours=2),
            resource_demand=1.0,
        )

        decisions = self.scheduler.schedule([job1, job2])

        self.assertEqual(len(decisions), 2)
        self.assertEqual(decisions[0].decision, DecisionType.SCHEDULED)
        self.assertEqual(decisions[1].decision, DecisionType.REJECTED_INFEASIBLE)
        self.assertIsNone(decisions[1].scheduled_start_utc)
        self.assertIn("exceeding deadline", decisions[1].reason)


class TestCarbonovaScheduler(unittest.TestCase):
    """Test Carbonova carbon-aware dispatch policy with forecast service integration and fallbacks."""

    def setUp(self):
        self.base_time = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        self.sample_job = WorkloadJob(
            job_id="job_carb",
            arrival_time_utc=self.base_time,
            duration_half_hours=2,
            deadline_time_utc=self.base_time + timedelta(hours=4),
            resource_demand=1.0,
        )

    def test_schedule_with_mocked_carbon_service(self):
        # Create a mock CarbonForecastService returning a valid CarbonForecastResponse
        mock_slot = CarbonIntensitySlot(
            timestamp_utc=self.base_time,
            predicted_intensity_gco2_per_kwh=72.45,
            lower_90_gco2_per_kwh=62.7076,
            upper_90_gco2_per_kwh=82.1924,
            uncertainty_width_gco2_per_kwh=19.4848,
        )
        mock_response = CarbonForecastResponse(
            calibrated_quantile_q_hat_gco2_per_kwh=9.7424,
            data_status="live",
            slots=[mock_slot],
        )

        mock_service = MagicMock(spec=CarbonForecastService)
        mock_service.predict_next_half_hour.return_value = mock_response

        scheduler = CarbonovaScheduler(carbon_service=mock_service)
        mock_history = ["synthetic_history_payload"]

        decisions = scheduler.schedule([self.sample_job], history=mock_history)

        self.assertEqual(len(decisions), 1)
        d = decisions[0]
        self.assertEqual(d.decision, DecisionType.SCHEDULED)
        self.assertEqual(d.policy_name, "Carbonova_Conservative")
        self.assertEqual(d.predicted_carbon_intensity_gco2_per_kwh, 72.45)
        self.assertEqual(d.lower_90_gco2_per_kwh, 62.7076)
        self.assertEqual(d.upper_90_gco2_per_kwh, 82.1924)
        self.assertEqual(d.uncertainty_width_gco2_per_kwh, 19.4848)
        self.assertEqual(d.data_status, "live")
        self.assertIn("Next-half-hour forecast is 72.45 gCO2/kWh", d.reason)
        self.assertIn("Job not deferred", d.reason)
        mock_service.predict_next_half_hour.assert_called_once_with(mock_history)

    def test_fallback_when_history_missing(self):
        # Service exists, but no history provided
        mock_service = MagicMock(spec=CarbonForecastService)
        scheduler = CarbonovaScheduler(carbon_service=mock_service)

        decisions = scheduler.schedule([self.sample_job], history=None)

        self.assertEqual(len(decisions), 1)
        d = decisions[0]
        self.assertEqual(d.decision, DecisionType.SCHEDULED)
        self.assertIsNone(d.predicted_carbon_intensity_gco2_per_kwh)
        self.assertEqual(d.data_status, "fallback_no_forecast")
        self.assertIn("conservative fallback", d.reason)
        mock_service.predict_next_half_hour.assert_not_called()

    def test_fallback_when_carbon_service_raises_error(self):
        mock_service = MagicMock(spec=CarbonForecastService)
        mock_service.predict_next_half_hour.side_effect = ValueError("Insufficient history: 200 intervals")

        scheduler = CarbonovaScheduler(carbon_service=mock_service)
        decisions = scheduler.schedule([self.sample_job], history=["too_short"])

        self.assertEqual(len(decisions), 1)
        d = decisions[0]
        self.assertEqual(d.decision, DecisionType.SCHEDULED)
        self.assertIsNone(d.predicted_carbon_intensity_gco2_per_kwh)
        self.assertEqual(d.data_status, "fallback_no_forecast")
        self.assertIn("Insufficient history", d.reason)

    def test_carbonova_deadline_rejection(self):
        # Infeasible job due to queue blockage
        job1 = WorkloadJob(
            job_id="job_first",
            arrival_time_utc=self.base_time,
            duration_half_hours=4,
            deadline_time_utc=self.base_time + timedelta(hours=6),
            resource_demand=1.0,
        )
        job2 = WorkloadJob(
            job_id="job_misses_deadline",
            arrival_time_utc=self.base_time + timedelta(minutes=30),
            duration_half_hours=2,
            deadline_time_utc=self.base_time + timedelta(hours=2),
            resource_demand=1.0,
        )

        scheduler = CarbonovaScheduler(carbon_service=None)
        decisions = scheduler.schedule([job1, job2])

        self.assertEqual(len(decisions), 2)
        self.assertEqual(decisions[0].decision, DecisionType.SCHEDULED)
        self.assertEqual(decisions[1].decision, DecisionType.REJECTED_INFEASIBLE)


class TestWorkloadSchedulerCoordinator(unittest.TestCase):
    """Test unified coordinator exposing both FIFO and Carbonova policies."""

    def test_coordinator_methods(self):
        base_time = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
        job = WorkloadJob(
            job_id="coord_job",
            arrival_time_utc=base_time,
            duration_half_hours=2,
            deadline_time_utc=base_time + timedelta(hours=4),
            resource_demand=1.0,
        )

        coordinator = WorkloadScheduler()

        fifo_res = coordinator.schedule_fifo([job])
        self.assertEqual(len(fifo_res), 1)
        self.assertEqual(fifo_res[0].policy_name, "FIFO")

        carb_res = coordinator.schedule_carbonova([job])
        self.assertEqual(len(carb_res), 1)
        self.assertEqual(carb_res[0].policy_name, "Carbonova_Conservative")


if __name__ == "__main__":
    unittest.main()
