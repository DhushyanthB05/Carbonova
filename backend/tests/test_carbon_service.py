"""
Unit Tests for Carbonova Carbon Forecast Service and Pydantic Schemas.

Covers:
  - Model and calibration metrics loading
  - Feature extraction consistency against ground truth pipeline
  - Conformal prediction interval calculations and non-negativity guarantees
  - Input validation and edge-case handling (insufficient history, gaps, invalid values)
  - Schema integrity and JSON serialization
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
from pydantic import ValidationError

from backend.carbon.schemas import (
    CarbonForecastResponse,
    CarbonIntensitySlot,
    CarbonObservation,
)
from backend.carbon.service import (
    CarbonForecastService,
    EXPECTED_FEATURES,
    MIN_HISTORY_INTERVALS,
    PROJECT_ROOT,
)


class TestModelAndMetricsLoading(unittest.TestCase):
    """Test loading and attribute binding of the trained model and conformal cutoff."""

    def setUp(self):
        self.service = CarbonForecastService()

    def test_successful_initialization(self):
        self.assertIsNotNone(self.service.model)
        self.assertTrue(hasattr(self.service.model, "predict"))
        self.assertEqual(self.service.features, EXPECTED_FEATURES)
        self.assertEqual(len(self.service.features), 17)

    def test_calibrated_conformal_cutoff_loaded(self):
        self.assertAlmostEqual(self.service.q_hat, 9.7424, places=4)
        self.assertEqual(self.service.nominal_coverage, 90.0)

    def test_missing_model_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            CarbonForecastService(model_path="non_existent_model.joblib")

    def test_missing_metrics_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            CarbonForecastService(metrics_path="non_existent_metrics.json")


class TestFeatureGenerationConsistency(unittest.TestCase):
    """Verify that live feature extraction perfectly matches the historical training pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.service = CarbonForecastService()
        cls.data_path = PROJECT_ROOT / "data" / "carbon_trace_2024_modeling.csv"
        cls.df_2024 = pd.read_csv(cls.data_path)
        cls.df_2024["dt"] = pd.to_datetime(cls.df_2024["timestamp_utc"], utc=True)

    def test_feature_values_match_ground_truth(self):
        # Pick row 500 as the evaluation target
        target_idx = 500
        ground_truth_row = self.df_2024.iloc[target_idx]
        target_dt = ground_truth_row["dt"].to_pydatetime()

        # Input buffer: 336 intervals strictly prior to target_idx
        buffer_slice = self.df_2024.iloc[target_idx - MIN_HISTORY_INTERVALS : target_idx]
        intensities = buffer_slice["modeled_intensity_gco2_per_kwh"].to_numpy(dtype=float)

        extracted_features_df = self.service._extract_features(intensities, target_dt)

        self.assertEqual(list(extracted_features_df.columns), EXPECTED_FEATURES)
        for feat in EXPECTED_FEATURES:
            computed_val = float(extracted_features_df[feat].iloc[0])
            expected_val = float(ground_truth_row[feat])
            self.assertAlmostEqual(
                computed_val,
                expected_val,
                places=4,
                msg=f"Feature mismatch in '{feat}': computed={computed_val}, expected={expected_val}",
            )

    def test_cyclical_encodings_bounded(self):
        target_dt = datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc)
        synthetic_intensities = np.full(MIN_HISTORY_INTERVALS, 100.0)
        feats = self.service._extract_features(synthetic_intensities, target_dt)

        for trig_feat in ["sin_hour", "cos_hour", "sin_period", "cos_period", "sin_day_of_week", "cos_day_of_week"]:
            val = float(feats[trig_feat].iloc[0])
            self.assertTrue(-1.0 <= val <= 1.0, f"{trig_feat} out of unit bounds: {val}")


class TestIntervalCalculation(unittest.TestCase):
    """Test one-step-ahead prediction and conformal prediction bounds."""

    @classmethod
    def setUpClass(cls):
        cls.service = CarbonForecastService()
        cls.data_path = PROJECT_ROOT / "data" / "carbon_trace_2024_modeling.csv"
        df = pd.read_csv(cls.data_path).iloc[:MIN_HISTORY_INTERVALS]
        cls.history_df = df[["timestamp_utc", "carbon_intensity_gco2_per_kwh"]].copy()

    def test_predict_next_half_hour_valid_response(self):
        response = self.service.predict_next_half_hour(self.history_df)

        self.assertIsInstance(response, CarbonForecastResponse)
        self.assertEqual(len(response.slots), 1)

        slot = response.slots[0]
        self.assertIsInstance(slot, CarbonIntensitySlot)
        self.assertGreater(slot.predicted_intensity_gco2_per_kwh, 0.0)
        self.assertGreaterEqual(slot.lower_90_gco2_per_kwh, 0.0)
        self.assertGreater(slot.upper_90_gco2_per_kwh, slot.lower_90_gco2_per_kwh)

        # Bound ordering and interval width check
        expected_width = round(slot.upper_90_gco2_per_kwh - slot.lower_90_gco2_per_kwh, 4)
        self.assertAlmostEqual(slot.uncertainty_width_gco2_per_kwh, expected_width, places=4)
        self.assertTrue(slot.lower_90_gco2_per_kwh <= slot.predicted_intensity_gco2_per_kwh <= slot.upper_90_gco2_per_kwh)

    def test_lower_bound_zero_truncation_when_near_zero(self):
        # Mock model predict to return a small positive intensity (e.g. 5.0)
        mock_service = CarbonForecastService()
        mock_service.model = MagicMock()
        mock_service.model.predict.return_value = np.array([5.0])

        response = mock_service.predict_next_half_hour(self.history_df)
        slot = response.slots[0]

        # 5.0 - 9.7424 = -4.7424, but must be clamped to 0.0
        self.assertEqual(slot.predicted_intensity_gco2_per_kwh, 5.0)
        self.assertEqual(slot.lower_90_gco2_per_kwh, 0.0)
        self.assertAlmostEqual(slot.upper_90_gco2_per_kwh, 5.0 + 9.7424, places=4)
        self.assertAlmostEqual(slot.uncertainty_width_gco2_per_kwh, slot.upper_90_gco2_per_kwh - 0.0, places=4)

    def test_slot_specific_diurnal_uncertainty(self):
        # Target timestamp is 2024-01-08 00:00Z (period 1 = night_baseload regime)
        response = self.service.predict_next_half_hour(self.history_df, uncertainty_mode="diurnal")
        slot = response.slots[0]

        # In night_baseload regime, q_hat is 11.2830 gCO2/kWh
        self.assertAlmostEqual(response.calibrated_quantile_q_hat_gco2_per_kwh, 11.2830, places=3)
        self.assertIn("Diurnal", response.nominal_interval_label)
        self.assertTrue(slot.lower_90_gco2_per_kwh <= slot.predicted_intensity_gco2_per_kwh <= slot.upper_90_gco2_per_kwh)

    def test_slot_specific_fallback_to_global_on_insufficient_sample(self):
        # Modify diurnal regimes to have a group with sample size < 50 for night_baseload
        service = CarbonForecastService()
        service.diurnal_regimes["night_baseload"] = {"sample_size_n": 20, "quantile_half_width_q_hat_gco2_per_kwh": 7.0}

        response = service.predict_next_half_hour(self.history_df, uncertainty_mode="diurnal")
        # Must fall back to global q_hat 9.7424 because 20 < MIN_REGIME_SAMPLE_SIZE (50)
        self.assertAlmostEqual(response.calibrated_quantile_q_hat_gco2_per_kwh, 9.7424, places=4)
        self.assertIn("Global Fallback", response.nominal_interval_label)

    def test_predict_without_explicit_history_loads_fallback(self):
        # Invoking predict_next_half_hour without history should safely source fallback trace via provider
        response = self.service.predict_next_half_hour()
        self.assertIsInstance(response, CarbonForecastResponse)
        self.assertEqual(len(response.slots), 1)
        self.assertGreater(response.slots[0].predicted_intensity_gco2_per_kwh, 0.0)
        self.assertEqual(response.data_status, "recorded")


class TestInvalidInputHandling(unittest.TestCase):
    """Test validation and guardrails against malformed, insufficient, or corrupted data."""

    def setUp(self):
        self.service = CarbonForecastService()
        base_dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        self.valid_timestamps = [base_dt + timedelta(minutes=30 * i) for i in range(MIN_HISTORY_INTERVALS)]
        self.valid_intensities = [100.0] * MIN_HISTORY_INTERVALS

    def test_insufficient_history_raises(self):
        short_df = pd.DataFrame({
            "timestamp_utc": self.valid_timestamps[:200],
            "carbon_intensity_gco2_per_kwh": self.valid_intensities[:200],
        })
        with self.assertRaises(ValueError) as ctx:
            self.service.predict_next_half_hour(short_df)
        self.assertIn("Insufficient history", str(ctx.exception))

    def test_negative_intensity_raises(self):
        intensities_with_neg = list(self.valid_intensities)
        intensities_with_neg[10] = -5.0
        bad_df = pd.DataFrame({
            "timestamp_utc": self.valid_timestamps,
            "carbon_intensity_gco2_per_kwh": intensities_with_neg,
        })
        with self.assertRaises(ValueError) as ctx:
            self.service.predict_next_half_hour(bad_df)
        self.assertIn("cannot be negative", str(ctx.exception))

    def test_nan_intensity_raises(self):
        intensities_with_nan = list(self.valid_intensities)
        intensities_with_nan[5] = np.nan
        bad_df = pd.DataFrame({
            "timestamp_utc": self.valid_timestamps,
            "carbon_intensity_gco2_per_kwh": intensities_with_nan,
        })
        with self.assertRaises(ValueError) as ctx:
            self.service.predict_next_half_hour(bad_df)
        self.assertIn("null or non-numeric", str(ctx.exception))

    def test_temporal_discontinuity_raises(self):
        # Introduce a 60-minute gap instead of 30 minutes
        timestamps_with_gap = list(self.valid_timestamps)
        timestamps_with_gap[100] = timestamps_with_gap[99] + timedelta(minutes=60)
        gap_df = pd.DataFrame({
            "timestamp_utc": timestamps_with_gap,
            "carbon_intensity_gco2_per_kwh": self.valid_intensities,
        })
        with self.assertRaises(ValueError) as ctx:
            self.service.predict_next_half_hour(gap_df)
        self.assertIn("Temporal discontinuity detected", str(ctx.exception))

    def test_invalid_target_timestamp_raises(self):
        valid_df = pd.DataFrame({
            "timestamp_utc": self.valid_timestamps,
            "carbon_intensity_gco2_per_kwh": self.valid_intensities,
        })
        # Last timestamp is valid_timestamps[-1]. Expected next is +30min.
        wrong_target = self.valid_timestamps[-1] + timedelta(hours=2)
        with self.assertRaises(ValueError) as ctx:
            self.service.predict_next_half_hour(valid_df, target_timestamp=wrong_target)
        self.assertIn("One-step-ahead forecasting requires target_timestamp", str(ctx.exception))


class TestSchemaValidationAndSerialization(unittest.TestCase):
    """Test Pydantic schema validation rules, boundary integrity, and JSON serialization."""

    def test_valid_slot_creation(self):
        slot = CarbonIntensitySlot(
            timestamp_utc=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
            predicted_intensity_gco2_per_kwh=100.0,
            lower_90_gco2_per_kwh=90.2576,
            upper_90_gco2_per_kwh=109.7424,
            uncertainty_width_gco2_per_kwh=19.4848,
        )
        self.assertEqual(slot.predicted_intensity_gco2_per_kwh, 100.0)
        self.assertEqual(slot.forecast_horizon, "next_half_hour")

    def test_inverted_bounds_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            CarbonIntensitySlot(
                timestamp_utc=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
                predicted_intensity_gco2_per_kwh=100.0,
                lower_90_gco2_per_kwh=110.0,
                upper_90_gco2_per_kwh=90.0,
                uncertainty_width_gco2_per_kwh=20.0,
            )

    def test_negative_lower_bound_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            CarbonIntensitySlot(
                timestamp_utc=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
                predicted_intensity_gco2_per_kwh=5.0,
                lower_90_gco2_per_kwh=-4.7424,
                upper_90_gco2_per_kwh=14.7424,
                uncertainty_width_gco2_per_kwh=19.4848,
            )

    def test_json_serialization_round_trip(self):
        slot = CarbonIntensitySlot(
            timestamp_utc=datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc),
            predicted_intensity_gco2_per_kwh=75.5,
            lower_90_gco2_per_kwh=65.7576,
            upper_90_gco2_per_kwh=85.2424,
            uncertainty_width_gco2_per_kwh=19.4848,
        )
        response = CarbonForecastResponse(
            calibrated_quantile_q_hat_gco2_per_kwh=9.7424,
            slots=[slot],
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        self.assertIn("slots", parsed)
        self.assertEqual(len(parsed["slots"]), 1)
        self.assertEqual(parsed["slots"][0]["predicted_intensity_gco2_per_kwh"], 75.5)
        self.assertEqual(parsed["model_name"], "RandomForestRegressor_Conformal")
        self.assertEqual(parsed["nominal_interval_label"], "Nominal 90% Prediction Interval")


if __name__ == "__main__":
    unittest.main()
