"""
Carbon Forecast Service for Carbonova.

Encapsulates:
  - Model loading from repository models/ directory
  - Calibrated conformal quantile retrieval from reports/uncertainty_metrics.json
    (supporting both global and slot-specific diurnal regime uncertainty)
  - Strict backward-looking feature engineering (autoregressive lags, rolling stats, cyclical time)
  - One-step-ahead next-half-hour point forecasting and nominal 90% prediction intervals
  - Bound validation and non-negative intensity guarantees
  - Integration with CarbonDataProvider for safe recorded trace loading and fallback
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd

from backend.carbon.provider import CarbonDataProvider, DataStatus
from backend.carbon.schemas import (
    CarbonForecastResponse,
    CarbonIntensitySlot,
    CarbonObservation,
)

# Project root resolution (parent of backend/carbon)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "random_forest_carbonova.joblib"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "reports" / "uncertainty_metrics.json"

EXPECTED_FEATURES: List[str] = [
    "lag_1_half_hour",
    "lag_2_half_hour",
    "lag_48_half_hour",
    "lag_336_half_hour",
    "rolling_mean_past_24h",
    "rolling_std_past_24h",
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "settlement_period",
    "sin_hour",
    "cos_hour",
    "sin_period",
    "cos_period",
    "sin_day_of_week",
    "cos_day_of_week",
]

MIN_HISTORY_INTERVALS: int = 336  # 7 days of 48 half-hour intervals
MIN_REGIME_SAMPLE_SIZE: int = 50   # Threshold below which slot-specific falls back to global


class CarbonForecastService:
    """
    Service for generating live one-step-ahead carbon intensity forecasts
    with nominal 90% split conformal prediction bounds.
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        metrics_path: Optional[Union[str, Path]] = None,
        data_provider: Optional[CarbonDataProvider] = None,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.metrics_path = Path(metrics_path) if metrics_path else DEFAULT_METRICS_PATH

        self.model = self._load_model(self.model_path)
        self.q_hat, self.nominal_coverage, self.diurnal_regimes = self._load_calibration_metrics(self.metrics_path)
        self.features = list(EXPECTED_FEATURES)
        self.data_provider = data_provider or CarbonDataProvider()

    @staticmethod
    def _load_model(path: Path) -> Any:
        """Load and validate the trained Random Forest model."""
        if not path.exists():
            raise FileNotFoundError(f"Model file not found at: {path.resolve()}")

        model = joblib.load(path)
        if not hasattr(model, "predict"):
            raise ValueError(f"Loaded object from {path} does not have a predict method.")

        if hasattr(model, "feature_names_in_"):
            model_features = list(model.feature_names_in_)
            if model_features != EXPECTED_FEATURES:
                raise ValueError(
                    f"Model feature mismatch. Expected: {EXPECTED_FEATURES}, got: {model_features}"
                )

        return model

    @staticmethod
    def _load_calibration_metrics(path: Path) -> Tuple[float, float, Dict[str, Any]]:
        """Read and validate the calibrated conformal quantile from uncertainty metrics."""
        if not path.exists():
            raise FileNotFoundError(f"Uncertainty metrics report not found at: {path.resolve()}")

        with open(path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)

        try:
            cal_details = metrics_data["conformal_calibration_details"]
            q_hat = float(cal_details["quantile_half_width_q_hat_gco2_per_kwh"])
            nominal_coverage = float(metrics_data.get("nominal_coverage_percent", 90.0))
            diurnal_regimes = metrics_data.get("slot_specific_diurnal_calibration", {}).get("groups", {})
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(
                f"Failed to parse conformal calibration details from {path}: {err}"
            ) from err

        if q_hat <= 0.0:
            raise ValueError(f"Invalid conformal quantile cutoff: {q_hat} (must be strictly positive).")

        return q_hat, nominal_coverage, diurnal_regimes

    @staticmethod
    def get_diurnal_regime(settlement_period: int) -> str:
        """
        Classify 30-minute settlement period (1-48) into diurnal grid regime.
          - night_baseload : periods 1-13 (00:00 - 06:30 UTC)
          - morning_ramp   : periods 14-23 (07:00 - 11:30 UTC)
          - afternoon_solar: periods 24-33 (12:00 - 16:30 UTC)
          - evening_peak   : periods 34-48 (17:00 - 23:30 UTC)
        """
        if settlement_period <= 13:
            return "night_baseload"
        elif settlement_period <= 23:
            return "morning_ramp"
        elif settlement_period <= 33:
            return "afternoon_solar"
        else:
            return "evening_peak"

    def _normalize_history(
        self,
        history: Union[pd.DataFrame, List[Dict[str, Any]], List[CarbonObservation]],
    ) -> Tuple[List[datetime], np.ndarray]:
        """
        Normalize input history into sorted UTC timestamps and intensity arrays,
        performing validation checks for length, non-negativity, and continuity.
        """
        timestamps: List[datetime] = []
        intensities: List[float] = []

        if isinstance(history, pd.DataFrame):
            # Identify timestamp column
            ts_col = None
            for candidate in ["timestamp_utc", "dt", "datetime", "DATETIME"]:
                if candidate in history.columns:
                    ts_col = candidate
                    break
            if ts_col is None:
                raise ValueError("Input DataFrame missing timestamp column ('timestamp_utc').")

            # Identify intensity column
            val_col = None
            for candidate in [
                "carbon_intensity_gco2_per_kwh",
                "modeled_intensity_gco2_per_kwh",
                "CARBON_INTENSITY",
                "intensity",
            ]:
                if candidate in history.columns:
                    val_col = candidate
                    break
            if val_col is None:
                raise ValueError(
                    "Input DataFrame missing carbon intensity column ('carbon_intensity_gco2_per_kwh')."
                )

            dt_series = pd.to_datetime(history[ts_col], utc=True, errors="coerce")
            if dt_series.isna().any():
                raise ValueError("Historical observations contain unparseable or null timestamps.")

            val_series = pd.to_numeric(history[val_col], errors="coerce")
            if val_series.isna().any():
                raise ValueError("Historical observations contain null or non-numeric intensity values.")

            sorted_df = pd.DataFrame({"dt": dt_series, "val": val_series}).sort_values("dt").reset_index(drop=True)
            timestamps = sorted_df["dt"].dt.to_pydatetime().tolist()
            intensities = sorted_df["val"].to_numpy(dtype=float)

        elif isinstance(history, list):
            parsed_records: List[Tuple[datetime, float]] = []
            for item in history:
                if isinstance(item, CarbonObservation):
                    dt = item.timestamp_utc
                    val = float(item.carbon_intensity_gco2_per_kwh)
                elif isinstance(item, dict):
                    ts_raw = item.get("timestamp_utc") or item.get("dt") or item.get("datetime")
                    val_raw = (
                        item.get("carbon_intensity_gco2_per_kwh")
                        if "carbon_intensity_gco2_per_kwh" in item
                        else item.get("modeled_intensity_gco2_per_kwh")
                        if "modeled_intensity_gco2_per_kwh" in item
                        else item.get("intensity")
                    )
                    if ts_raw is None or val_raw is None:
                        raise ValueError("Historical dict record missing timestamp or intensity.")

                    if isinstance(ts_raw, datetime):
                        dt = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=timezone.utc)
                    else:
                        dt = pd.to_datetime(ts_raw, utc=True).to_pydatetime()

                    val = float(val_raw)
                else:
                    raise TypeError(f"Unsupported record type in history list: {type(item)}")

                parsed_records.append((dt, val))

            parsed_records.sort(key=lambda x: x[0])
            timestamps = [r[0] for r in parsed_records]
            intensities = np.array([r[1] for r in parsed_records], dtype=float)

        else:
            raise TypeError(f"History must be DataFrame or list of records, got {type(history)}")

        # Validation: minimum length
        if len(timestamps) < MIN_HISTORY_INTERVALS:
            raise ValueError(
                f"Insufficient history: {len(timestamps)} intervals provided. "
                f"At least {MIN_HISTORY_INTERVALS} half-hour intervals (7 full days) are required "
                f"to calculate lag_336_half_hour."
            )

        # Validation: non-negative and finite
        if np.any(np.isnan(intensities)) or np.any(np.isinf(intensities)):
            raise ValueError("Historical intensity values contain NaN or infinite readings.")
        if np.any(intensities < 0.0):
            raise ValueError("Historical intensity values cannot be negative.")

        # Validation: contiguous 30-minute intervals
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i - 1]
            if delta != timedelta(minutes=30):
                raise ValueError(
                    f"Temporal discontinuity detected between {timestamps[i-1].isoformat()} "
                    f"and {timestamps[i].isoformat()} (delta: {delta}). "
                    "Expected continuous 30-minute settlement intervals."
                )

        return timestamps, intensities

    def _extract_features(
        self,
        intensities: np.ndarray,
        target_dt: datetime,
    ) -> pd.DataFrame:
        """
        Extract the exact 17 features expected by the trained model for target timestamp T.
        Uses observations strictly prior to T (up to T-1).
        """
        # Autoregressive lags from past observations
        lag_1 = float(intensities[-1])    # T - 1 (30 min prior)
        lag_2 = float(intensities[-2])    # T - 2 (60 min prior)
        lag_48 = float(intensities[-48])  # T - 48 (24 h prior)
        lag_336 = float(intensities[-336]) # T - 336 (7 d prior)

        # Rolling window statistics strictly over past 48 half-hours (24 hours prior)
        past_48 = intensities[-48:]
        rolling_mean = round(float(np.mean(past_48)), 2)
        rolling_std = round(float(np.std(past_48, ddof=1)), 2)

        # Calendar features for target interval T
        hour = target_dt.hour
        day_of_week = target_dt.weekday()  # Monday=0, Sunday=6
        month = target_dt.month
        is_weekend = int(day_of_week >= 5)
        settlement_period = (hour * 2) + (target_dt.minute // 30) + 1

        # Cyclical harmonic trigonometric encodings
        sin_hour = round(float(np.sin(2 * np.pi * hour / 24.0)), 6)
        cos_hour = round(float(np.cos(2 * np.pi * hour / 24.0)), 6)
        sin_period = round(float(np.sin(2 * np.pi * settlement_period / 48.0)), 6)
        cos_period = round(float(np.cos(2 * np.pi * settlement_period / 48.0)), 6)
        sin_day_of_week = round(float(np.sin(2 * np.pi * day_of_week / 7.0)), 6)
        cos_day_of_week = round(float(np.cos(2 * np.pi * day_of_week / 7.0)), 6)

        feature_dict: Dict[str, float] = {
            "lag_1_half_hour": lag_1,
            "lag_2_half_hour": lag_2,
            "lag_48_half_hour": lag_48,
            "lag_336_half_hour": lag_336,
            "rolling_mean_past_24h": rolling_mean,
            "rolling_std_past_24h": rolling_std,
            "hour": hour,
            "day_of_week": day_of_week,
            "month": month,
            "is_weekend": is_weekend,
            "settlement_period": settlement_period,
            "sin_hour": sin_hour,
            "cos_hour": cos_hour,
            "sin_period": sin_period,
            "cos_period": cos_period,
            "sin_day_of_week": sin_day_of_week,
            "cos_day_of_week": cos_day_of_week,
        }

        return pd.DataFrame([feature_dict])[EXPECTED_FEATURES]

    def predict_next_half_hour(
        self,
        history: Optional[Union[pd.DataFrame, List[Dict[str, Any]], List[CarbonObservation]]] = None,
        target_timestamp: Optional[Union[str, datetime]] = None,
        data_status: Optional[str] = None,
        uncertainty_mode: str = "global",
    ) -> CarbonForecastResponse:
        """
        Generate a one-step-ahead carbon intensity forecast with calibrated 90% conformal bounds.

        Parameters:
            history: Optional historical observations (at least 336 half-hours up to T-1).
                     If omitted, automatically loads verified recorded fallback trace via CarbonDataProvider.
            target_timestamp: Optional timestamp for target slot T. Must be exactly 30 minutes
                              after the latest observation in history.
            data_status: Operational status label ('live', 'recorded', 'fallback_persistence', etc.).
            uncertainty_mode: 'global' for single 90% conformal quantile, or 'diurnal'/'slot_specific'
                              for regime-specific conformal intervals with automatic global fallback.

        Returns:
            CarbonForecastResponse containing the predicted slot and uncertainty bounds.
        """
        # Load fallback history from CarbonDataProvider if omitted
        if history is None:
            history, prov = self.data_provider.get_live_or_fallback(buffer_length=MIN_HISTORY_INTERVALS)
            if data_status is None:
                data_status = prov.data_status.value
        elif data_status is None:
            data_status = "live"

        timestamps, intensities = self._normalize_history(history)
        latest_obs_dt = timestamps[-1]

        # Determine target interval T (one-step ahead)
        expected_target_dt = latest_obs_dt + timedelta(minutes=30)
        if target_timestamp is not None:
            if isinstance(target_timestamp, str):
                target_dt = pd.to_datetime(target_timestamp, utc=True).to_pydatetime()
            elif isinstance(target_timestamp, datetime):
                target_dt = target_timestamp if target_timestamp.tzinfo else target_timestamp.replace(tzinfo=timezone.utc)
            else:
                raise TypeError(f"target_timestamp must be datetime or ISO string, got {type(target_timestamp)}")

            if target_dt != expected_target_dt:
                raise ValueError(
                    f"Invalid target timestamp: {target_dt.isoformat()}. "
                    f"One-step-ahead forecasting requires target_timestamp to be exactly 30 minutes "
                    f"after latest observation ({expected_target_dt.isoformat()})."
                )
        else:
            target_dt = expected_target_dt

        # Feature extraction
        features_df = self._extract_features(intensities, target_dt)

        # Model inference
        pred_raw = float(self.model.predict(features_df)[0])
        pred_intensity = max(0.0, round(pred_raw, 4))

        # Select conformal quantile: global vs slot-specific diurnal
        settlement_period = (target_dt.hour * 2) + (target_dt.minute // 30) + 1
        interval_label = f"Nominal {self.nominal_coverage:.0f}% Prediction Interval"

        if uncertainty_mode in ("diurnal", "slot_specific"):
            regime = self.get_diurnal_regime(settlement_period)
            group_info = self.diurnal_regimes.get(regime, {})
            # Verify minimum sample size before applying slot-specific quantile
            if group_info.get("sample_size_n", 0) >= MIN_REGIME_SAMPLE_SIZE and "quantile_half_width_q_hat_gco2_per_kwh" in group_info:
                q_hat_selected = float(group_info["quantile_half_width_q_hat_gco2_per_kwh"])
                interval_label = f"Nominal {self.nominal_coverage:.0f}% Prediction Interval (Diurnal: {regime})"
            else:
                q_hat_selected = self.q_hat
                interval_label = f"Nominal {self.nominal_coverage:.0f}% Prediction Interval (Global Fallback)"
        else:
            q_hat_selected = self.q_hat

        # Conformal interval calculation (nominal 90%)
        # Lower bound clamped at 0.0 (physical impossibility of negative carbon intensity)
        lower_bound = max(0.0, round(pred_intensity - q_hat_selected, 4))
        upper_bound = max(lower_bound, round(pred_intensity + q_hat_selected, 4))
        width = round(upper_bound - lower_bound, 4)

        slot = CarbonIntensitySlot(
            timestamp_utc=target_dt,
            predicted_intensity_gco2_per_kwh=pred_intensity,
            lower_90_gco2_per_kwh=lower_bound,
            upper_90_gco2_per_kwh=upper_bound,
            uncertainty_width_gco2_per_kwh=width,
            model_name="RandomForestRegressor_Conformal",
            forecast_horizon="next_half_hour",
        )

        response = CarbonForecastResponse(
            generated_at_utc=datetime.now(timezone.utc),
            model_name="RandomForestRegressor_Conformal",
            model_version="1.0.0",
            data_status=data_status,
            nominal_interval_label=interval_label,
            calibrated_quantile_q_hat_gco2_per_kwh=round(q_hat_selected, 4),
            slots=[slot],
        )

        return response
