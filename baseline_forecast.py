#!/usr/bin/env python3
"""
Baseline Carbon Intensity Forecasting Model for Carbonova

STEP 2: Non-parametric 24-hour Seasonal Persistence Baseline

Forecasting Task:
  Predict carbon intensity for each half-hour settlement period T using the
  corresponding half-hour intensity from the previous day (T - 24 hours):
    baseline_prediction(T) = modeled_intensity(T - 48 half-hour intervals)

Input Files:
  - data/carbon_trace_2023_modeling.csv (Diagnostics / Reference)
  - data/carbon_trace_2024_modeling.csv (Out-of-sample Evaluation)

Outputs:
  - reports/baseline_predictions_2024.csv
  - reports/baseline_metrics.json
"""

import json
from pathlib import Path
import sys
from typing import Dict, Optional, Tuple, Any

import numpy as np
import pandas as pd

DATA_DIR = Path("data")
REPORTS_DIR = Path("reports")

REQUIRED_COLUMNS = [
    "timestamp_utc",
    "modeled_intensity_gco2_per_kwh",
]


def load_and_validate_dataset(filepath: Path) -> pd.DataFrame:
    """Load dataset, validate required columns, parse timestamps, and sort chronologically."""
    if not filepath.exists():
        raise FileNotFoundError(f"Required dataset not found: {filepath.resolve()}")

    df = pd.read_csv(filepath)

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Dataset {filepath.name} is missing required columns: {missing_cols}")

    # Parse timestamps as UTC and sort chronologically
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    if df["timestamp_utc"].isna().any():
        raise ValueError(f"Dataset {filepath.name} contains unparseable timestamps.")

    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    return df


def verify_and_get_lag48(df: pd.DataFrame, prev_df: Optional[pd.DataFrame] = None) -> pd.Series:
    """
    Extract or derive the 24-hour persistence baseline (T - 48 intervals).
    Verifies lag_48_half_hour if present, or derives by shifting the continuous target series by 48.
    """
    target_col = "modeled_intensity_gco2_per_kwh"
    target_series = df[target_col]

    if "lag_48_half_hour" in df.columns:
        lag_col = df["lag_48_half_hour"]
        # Verification check: for i >= 48 within df, verify lag matches target shifted by 48
        internal_match = np.allclose(
            lag_col.iloc[48:].dropna().values,
            target_series.iloc[:-48].dropna().values,
            atol=1e-5,
        )
        if internal_match:
            return lag_col

    # Derive by continuous concatenation if prev_df is available
    if prev_df is not None:
        combined_target = pd.concat([prev_df[target_col], target_series], ignore_index=True)
        shifted = combined_target.shift(48)
        return shifted.iloc[len(prev_df):].reset_index(drop=True)
    else:
        return target_series.shift(48)


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Calculate MAE, RMSE, R-squared, and MAPE.

    MAPE Handling of Zero Targets:
      All values in modeled_intensity_gco2_per_kwh are strictly positive:
      min is 26.0 gCO2/kWh (2023) and 14.0 gCO2/kWh (2024).
      Division by zero does not occur in this dataset.
    """
    errors = y_true - y_pred
    abs_errors = np.abs(errors)
    sq_errors = errors ** 2

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(sq_errors)))

    ss_res = float(np.sum(sq_errors))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

    # MAPE calculation with zero-target validation
    if np.any(y_true == 0):
        # Exclude zeros if any exist to prevent division by zero
        non_zero_mask = (y_true != 0)
        mape = float(np.mean(np.abs(errors[non_zero_mask]) / y_true[non_zero_mask])) * 100.0
    else:
        mape = float(np.mean(abs_errors / y_true)) * 100.0

    return {
        "mae_gco2_per_kwh": round(mae, 4),
        "rmse_gco2_per_kwh": round(rmse, 4),
        "r2_score": round(r2, 4),
        "mape_percent": round(mape, 2),
    }


def run_baseline_pipeline():
    print("=" * 78)
    print("CARBONOVA: STEP 2 - 24-HOUR SEASONAL PERSISTENCE BASELINE FORECAST")
    print("=" * 78)

    path_2023 = DATA_DIR / "carbon_trace_2023_modeling.csv"
    path_2024 = DATA_DIR / "carbon_trace_2024_modeling.csv"

    # 1. Load and validate datasets
    print("Loading datasets...")
    df_2023 = load_and_validate_dataset(path_2023)
    df_2024 = load_and_validate_dataset(path_2024)

    print(f"  * 2023 modeling dataset loaded: {len(df_2023):,} rows")
    print(f"  * 2024 modeling dataset loaded: {len(df_2024):,} rows")

    # 2. Extract baseline predictions
    # Note: forecast_gco2_per_kwh, raw carbon_intensity_gco2_per_kwh, is_anomaly,
    # anomaly_type, source_type, treatment_method, and treatment_note are strictly EXCLUDED.
    pred_2023 = verify_and_get_lag48(df_2023)
    pred_2024 = verify_and_get_lag48(df_2024, prev_df=df_2023)

    # 3. Align valid pairs
    y_true_2023 = df_2023["modeled_intensity_gco2_per_kwh"].values
    y_pred_2023 = pred_2023.values
    valid_2023 = ~np.isnan(y_true_2023) & ~np.isnan(y_pred_2023)

    y_true_2024 = df_2024["modeled_intensity_gco2_per_kwh"].values
    y_pred_2024 = pred_2024.values
    valid_2024 = ~np.isnan(y_true_2024) & ~np.isnan(y_pred_2024)

    eval_count_2023 = int(np.sum(valid_2023))
    eval_count_2024 = int(np.sum(valid_2024))

    # 4. Compute metrics
    metrics_2023 = calculate_metrics(y_true_2023[valid_2023], y_pred_2023[valid_2023])
    metrics_2024 = calculate_metrics(y_true_2024[valid_2024], y_pred_2024[valid_2024])

    # 5. Display Diagnostics (2023) and Final Evaluation (2024)
    print("\n" + "-" * 78)
    print("2023 BASELINE DIAGNOSTICS (In-Sample / Training Period Reference)")
    print("Note: Non-parametric heuristic baseline; diagnostics serve as reference, NOT model training.")
    print("-" * 78)
    print(f"  Evaluated Rows : {eval_count_2023:,} / {len(df_2023):,}")
    print(f"  MAE            : {metrics_2023['mae_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  RMSE           : {metrics_2023['rmse_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  R-squared (R2) : {metrics_2023['r2_score']:.4f}")
    print(f"  MAPE           : {metrics_2023['mape_percent']:.2f}%")

    print("\n" + "-" * 78)
    print("2024 FINAL BASELINE EVALUATION (Out-of-Sample / Test Period)")
    print("Rolling Evaluation Assumption:")
    print("  At timestamp T, baseline prediction is modeled_intensity(T - 48 intervals).")
    print("  This observation was finalized 24 hours prior to prediction time T.")
    print("  Strict zero future leakage: no observations at or after T are used.")
    print("-" * 78)
    print(f"  Evaluated Rows : {eval_count_2024:,} / {len(df_2024):,}")
    print(f"  MAE            : {metrics_2024['mae_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  RMSE           : {metrics_2024['rmse_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  R-squared (R2) : {metrics_2024['r2_score']:.4f}")
    print(f"  MAPE           : {metrics_2024['mape_percent']:.2f}%")

    # 6. Save 2024 predictions and errors
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pred_df_2024 = pd.DataFrame({
        "timestamp_utc": df_2024["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%MZ"),
        "actual_intensity_gco2_per_kwh": y_true_2024,
        "baseline_prediction_gco2_per_kwh": y_pred_2024,
        "absolute_error_gco2_per_kwh": np.round(np.abs(y_true_2024 - y_pred_2024), 4),
    })

    out_csv = REPORTS_DIR / "baseline_predictions_2024.csv"
    pred_df_2024.to_csv(out_csv, index=False)
    print(f"\nSaved 2024 predictions to: {out_csv.resolve()} ({len(pred_df_2024):,} rows)")

    # 7. Save metrics and assumptions to JSON
    out_json = REPORTS_DIR / "baseline_metrics.json"
    results_payload = {
        "task": "24-hour seasonal persistence baseline carbon-intensity forecasting",
        "model_type": "non-parametric_persistence_baseline",
        "target_variable": "modeled_intensity_gco2_per_kwh",
        "formula": "baseline_prediction(T) = modeled_intensity(T - 48 half-hour intervals)",
        "evaluation_assumptions": {
            "rolling_evaluation": "At interval T, the baseline prediction uses the modeled intensity from T-48 intervals (T - 24 hours), which was fully finalized 24 hours prior to prediction time.",
            "zero_leakage": "No observation at or after prediction time T is used. All inputs are strictly backward-looking.",
            "mape_zero_handling": "In both 2023 and 2024, modeled carbon intensity values are strictly positive (min 26.0 gCO2/kWh in 2023, min 14.0 gCO2/kWh in 2024), so division by zero does not occur.",
            "excluded_inputs": [
                "forecast_gco2_per_kwh",
                "carbon_intensity_gco2_per_kwh",
                "is_anomaly",
                "anomaly_type",
                "source_type",
                "treatment_method",
                "treatment_note",
            ],
        },
        "diagnostics_2023": {
            "description": "2023 Training Period Baseline Diagnostics (In-sample reference; NOT model training)",
            "evaluated_rows": eval_count_2023,
            "total_rows": len(df_2023),
            "metrics": metrics_2023,
        },
        "evaluation_2024": {
            "description": "2024 Final Baseline Evaluation (Out-of-sample test period)",
            "evaluated_rows": eval_count_2024,
            "total_rows": len(df_2024),
            "metrics": metrics_2024,
        },
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"Saved baseline metrics to: {out_json.resolve()}")
    print("=" * 78)


if __name__ == "__main__":
    try:
        run_baseline_pipeline()
    except Exception as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)
