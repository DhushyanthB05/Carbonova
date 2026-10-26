"""
Unit Tests for CarbonDataProvider and Data Provenance.

Covers:
  - Valid recorded trace loading and normalization
  - Time range filtering
  - Trace validation guardrails (missing files, empty files, negative values, unparseable timestamps)
  - Data provenance tracking (source name, region, unit, live vs recorded status)
  - Non-crashing fallback behavior
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

import pandas as pd

from backend.carbon.provider import CarbonDataProvider, DataStatus, ProvenanceMetadata
from backend.carbon.schemas import CarbonObservation
from backend.carbon.service import PROJECT_ROOT


class TestCarbonDataProvider(unittest.TestCase):
    """Test suite for CarbonDataProvider."""

    @classmethod
    def setUpClass(cls):
        cls.provider = CarbonDataProvider()
        cls.trace_2024_path = PROJECT_ROOT / "data" / "carbon_trace_2024_modeling.csv"

    def test_load_default_recorded_trace_valid(self):
        observations, metadata = self.provider.load_recorded_trace(self.trace_2024_path)

        self.assertIsInstance(observations, list)
        self.assertEqual(len(observations), 17568)
        self.assertIsInstance(observations[0], CarbonObservation)
        self.assertEqual(observations[0].timestamp_utc.tzinfo, timezone.utc)
        self.assertGreater(observations[0].carbon_intensity_gco2_per_kwh, 0.0)

        # Check provenance metadata
        self.assertIsInstance(metadata, ProvenanceMetadata)
        self.assertEqual(metadata.source_name, "NESO_Great_Britain_Carbon_Intensity")
        self.assertEqual(metadata.region, "GB")
        self.assertEqual(metadata.data_status, DataStatus.RECORDED)
        self.assertEqual(metadata.unit, "gCO2/kWh")
        self.assertEqual(metadata.total_observations, 17568)
        self.assertTrue(metadata.is_observed)
        self.assertIsNone(metadata.fallback_reason)

    def test_load_recorded_trace_with_time_bounds(self):
        start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 6, 1, 23, 30, tzinfo=timezone.utc)

        observations, metadata = self.provider.load_recorded_trace(
            self.trace_2024_path,
            start_time_utc=start,
            end_time_utc=end,
        )

        # 24 hours of 30-minute intervals = 48 observations
        self.assertEqual(len(observations), 48)
        self.assertEqual(observations[0].timestamp_utc, start)
        self.assertEqual(observations[-1].timestamp_utc, end)
        self.assertEqual(metadata.total_observations, 48)

    def test_missing_trace_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            self.provider.load_recorded_trace(Path("non_existent_trace.csv"))

    def test_empty_dataframe_validation_failure(self):
        empty_df = pd.DataFrame()
        is_valid, issues = self.provider.validate_trace_dataframe(empty_df)
        self.assertFalse(is_valid)
        self.assertTrue(any("empty" in msg.lower() for msg in issues))

    def test_missing_timestamp_column_validation_failure(self):
        bad_df = pd.DataFrame({"modeled_intensity_gco2_per_kwh": [50.0, 60.0]})
        is_valid, issues = self.provider.validate_trace_dataframe(bad_df)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing required timestamp" in msg.lower() for msg in issues))

    def test_missing_intensity_column_validation_failure(self):
        bad_df = pd.DataFrame({"timestamp_utc": ["2024-01-01T00:00Z", "2024-01-01T00:30Z"]})
        is_valid, issues = self.provider.validate_trace_dataframe(bad_df)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing required intensity" in msg.lower() for msg in issues))

    def test_negative_intensity_validation_failure(self):
        bad_df = pd.DataFrame({
            "timestamp_utc": ["2024-01-01T00:00Z", "2024-01-01T00:30Z"],
            "modeled_intensity_gco2_per_kwh": [50.0, -10.0],
        })
        is_valid, issues = self.provider.validate_trace_dataframe(bad_df)
        self.assertFalse(is_valid)
        self.assertTrue(any("negative" in msg.lower() for msg in issues))

    def test_unparseable_timestamp_validation_failure(self):
        bad_df = pd.DataFrame({
            "timestamp_utc": ["2024-01-01T00:00Z", "invalid_timestamp_string"],
            "modeled_intensity_gco2_per_kwh": [50.0, 60.0],
        })
        is_valid, issues = self.provider.validate_trace_dataframe(bad_df)
        self.assertFalse(is_valid)
        self.assertTrue(any("unparseable" in msg.lower() for msg in issues))

    def test_get_live_or_fallback_returns_recorded_trace(self):
        observations, metadata = self.provider.get_live_or_fallback(buffer_length=48)

        self.assertEqual(len(observations), 48)
        self.assertEqual(metadata.data_status, DataStatus.RECORDED)
        self.assertIn("safely fell back", metadata.fallback_reason.lower())

    def test_get_live_or_fallback_corrupt_path_handles_gracefully(self):
        broken_provider = CarbonDataProvider(default_trace_path="completely_corrupt_path.csv")
        observations, metadata = broken_provider.get_live_or_fallback(buffer_length=48)

        # Non-crashing safety: returns empty list with explicit fallback status
        self.assertEqual(observations, [])
        self.assertEqual(metadata.data_status, DataStatus.FALLBACK_NO_FORECAST)
        self.assertIn("failed to load", metadata.fallback_reason.lower())


if __name__ == "__main__":
    unittest.main()
