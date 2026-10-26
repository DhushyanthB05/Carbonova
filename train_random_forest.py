#!/usr/bin/env python3
"""
Random Forest Carbon Intensity Forecasting Model for Carbonova

STEP 3: Supervised Machine Learning for Next-Half-Hour Carbon Intensity Prediction

Objective:
  Predict carbon intensity for the next half-hour interval T using information
  available at prediction time (the conclusion of interval T-1).

Target:
  modeled_intensity_gco2_per_kwh

Features (17):
  - Autoregressive Lags: lag_1_half_hour, lag_2_half_hour, lag_48_half_hour, lag_336_half_hour
  - Rolling Stats      : rolling_mean_past_24h, rolling_std_past_24h
  - Calendar Features  : hour, day_of_week, month, is_weekend, settlement_period
  - Cyclical Encodings : sin_hour, cos_hour, sin_period, cos_period, sin_day_of_week, cos_day_of_week

Exclusions:
  - forecast_gco2_per_kwh (historical publication timing unverified)
  - Raw carbon_intensity_gco2_per_kwh, is_anomaly, anomaly_type, source_type,
    treatment_method, treatment_note (metadata / uncorrected anomalies)

Chronological Split:
  - Training   : 2023 (first 80%, Jan 01 - Oct 20)
  - Validation : 2023 (last 20%, Oct 21 - Dec 31)
  - Final Test : 2024 (full year, strictly out-of-sample)
"""

import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd

# Check dependencies before running
try:
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
except ImportError as err:
    print(f"[Error] Required dependency missing: {err.name}", file=sys.stderr)
    print("Please ensure scikit-learn and joblib are installed.", file=sys.stderr)
    sys.exit(1)

DATA_DIR = Path("data")
MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

FEATURES: List[str] = [
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

TARGET: str = "modeled_intensity_gco2_per_kwh"

EXCLUDED_COLUMNS: List[str] = [
    "forecast_gco2_per_kwh",
    "carbon_intensity_gco2_per_kwh",
    "is_anomaly",
    "anomaly_type",
    "source_type",
    "treatment_method",
    "treatment_note",
    "region",
]

# Baseline metrics on 2024 test set from STEP 2
BASELINE_2024_MAE = 40.7313
BASELINE_2024_RMSE = 53.3597
BASELINE_2024_R2 = 0.2050

# Documented model hyperparameters (balanced accuracy and low memory footprint)
MODEL_PARAMS: Dict[str, Any] = {
    "n_estimators": 100,
    "max_depth": 16,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "max_features": 1.0,
    "random_state": 42,
    "n_jobs": -1,
}


def load_dataset(filepath: Path) -> pd.DataFrame:
    """Load and validate dataset columns and timestamps."""
    if not filepath.exists():
        raise FileNotFoundError(f"Dataset file not found: {filepath.resolve()}")

    df = pd.read_csv(filepath)

    # Verify target and features exist
    if TARGET not in df.columns:
        raise ValueError(f"Target column '{TARGET}' missing from {filepath.name}.")

    missing_features = [f for f in FEATURES if f not in df.columns]
    if missing_features:
        raise ValueError(f"Feature columns missing from {filepath.name}: {missing_features}")

    # Parse timestamps as UTC and sort chronologically
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    if df["timestamp_utc"].isna().any():
        raise ValueError(f"Invalid timestamps detected in {filepath.name}.")

    df = df.sort_values("timestamp_utc").reset_index(drop=True)

    # Check for NaNs in features and target
    nan_features = df[FEATURES].isna().sum().sum()
    nan_target = df[TARGET].isna().sum()
    if nan_features > 0 or nan_target > 0:
        raise ValueError(
            f"Found {nan_features} NaNs in features and {nan_target} NaNs in target in {filepath.name}."
        )

    return df


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate MAE, RMSE, and R2 metrics."""
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))

    return {
        "mae_gco2_per_kwh": round(mae, 4),
        "rmse_gco2_per_kwh": round(rmse, 4),
        "r2_score": round(r2, 4),
    }


def main():
    print("=" * 78)
    print("CARBONOVA: STEP 3 - RANDOM FOREST CARBON INTENSITY FORECASTING")
    print("=" * 78)

    # 1. Load datasets
    path_2023 = DATA_DIR / "carbon_trace_2023_modeling.csv"
    path_2024 = DATA_DIR / "carbon_trace_2024_modeling.csv"

    print("Loading modeling datasets...")
    df_2023 = load_dataset(path_2023)
    df_2024 = load_dataset(path_2024)

    print(f"  * 2023 dataset loaded: {len(df_2023):,} rows")
    print(f"  * 2024 dataset loaded: {len(df_2024):,} rows")

    # 2. Chronological Train/Val Split within 2023 (80% Train, 20% Val)
    split_idx = int(len(df_2023) * 0.8)
    train_df = df_2023.iloc[:split_idx].copy()
    val_df = df_2023.iloc[split_idx:].copy()

    train_start = train_df["timestamp_utc"].iloc[0].strftime("%Y-%m-%dT%H:%MZ")
    train_end = train_df["timestamp_utc"].iloc[-1].strftime("%Y-%m-%dT%H:%MZ")
    val_start = val_df["timestamp_utc"].iloc[0].strftime("%Y-%m-%dT%H:%MZ")
    val_end = val_df["timestamp_utc"].iloc[-1].strftime("%Y-%m-%dT%H:%MZ")

    test_start = df_2024["timestamp_utc"].iloc[0].strftime("%Y-%m-%dT%H:%MZ")
    test_end = df_2024["timestamp_utc"].iloc[-1].strftime("%Y-%m-%dT%H:%MZ")

    print("\n--- Chronological Split Configuration ---")
    print(f"  * Training Set   : {len(train_df):,} rows ({train_start} -> {train_end})")
    print(f"  * Validation Set : {len(val_df):,} rows ({val_start} -> {val_end})")
    print(f"  * Test Set (2024): {len(df_2024):,} rows ({test_start} -> {test_end})")
    print("  * Note: Shuffling strictly disabled to preserve time-series autoregressive structure.")

    # 3. Prepare Feature Matrices and Targets
    X_train = train_df[FEATURES]
    y_train = train_df[TARGET].values

    X_val = val_df[FEATURES]
    y_val = val_df[TARGET].values

    X_test = df_2024[FEATURES]
    y_test = df_2024[TARGET].values

    # 4. Train Random Forest Model
    print("\n--- Training RandomForestRegressor ---")
    print(f"  * Number of trees   : {MODEL_PARAMS['n_estimators']}")
    print(f"  * Max tree depth    : {MODEL_PARAMS['max_depth']}")
    print(f"  * Min samples split : {MODEL_PARAMS['min_samples_split']}")
    print(f"  * Min samples leaf  : {MODEL_PARAMS['min_samples_leaf']}")
    print(f"  * Random state      : {MODEL_PARAMS['random_state']}")
    print(f"  * Feature count     : {len(FEATURES)}")

    start_time = time.time()
    rf = RandomForestRegressor(**MODEL_PARAMS)
    rf.fit(X_train, y_train)
    train_duration = time.time() - start_time
    print(f"  * Model training completed in {train_duration:.2f} seconds.")

    # 5. Model Evaluation
    print("\n--- Model Evaluation ---")
    # Validation set (2023 last 20%)
    val_preds = rf.predict(X_val)
    val_metrics = calculate_metrics(y_val, val_preds)

    print("2023 Validation Set Metrics (Oct 21 - Dec 31):")
    print(f"  * MAE  : {val_metrics['mae_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  * RMSE : {val_metrics['rmse_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  * R2   : {val_metrics['r2_score']:.4f}")

    # Test set (2024 full year)
    test_preds = rf.predict(X_test)
    test_metrics = calculate_metrics(y_test, test_preds)

    print("\n2024 Final Test Set Metrics (Out-of-Sample, Full Year):")
    print(f"  * MAE  : {test_metrics['mae_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  * RMSE : {test_metrics['rmse_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  * R2   : {test_metrics['r2_score']:.4f}")

    # 6. Baseline Comparison
    mae_diff = BASELINE_2024_MAE - test_metrics["mae_gco2_per_kwh"]
    rmse_diff = BASELINE_2024_RMSE - test_metrics["rmse_gco2_per_kwh"]

    mae_improvement_pct = (mae_diff / BASELINE_2024_MAE) * 100.0
    rmse_improvement_pct = (rmse_diff / BASELINE_2024_RMSE) * 100.0
    r2_improvement = test_metrics["r2_score"] - BASELINE_2024_R2

    print("\n--- Comparison Against 2024 24-Hour Persistence Baseline ---")
    print(f"  * Baseline MAE : {BASELINE_2024_MAE:.4f} gCO2/kWh")
    print(f"  * Model MAE    : {test_metrics['mae_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  * MAE Improvement: {mae_improvement_pct:+.2f}% ({mae_diff:+.4f} gCO2/kWh)")
    print(f"  * Baseline RMSE: {BASELINE_2024_RMSE:.4f} gCO2/kWh")
    print(f"  * Model RMSE   : {test_metrics['rmse_gco2_per_kwh']:.4f} gCO2/kWh")
    print(f"  * RMSE Improvement: {rmse_improvement_pct:+.2f}% ({rmse_diff:+.4f} gCO2/kWh)")
    print(f"  * Baseline R2  : {BASELINE_2024_R2:.4f}")
    print(f"  * Model R2     : {test_metrics['r2_score']:.4f} ({r2_improvement:+.4f})")

    # 7. Save Artifacts
    # A. Save trained model
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "random_forest_carbonova.joblib"
    joblib.dump(rf, model_path, compress=3)
    print(f"\nSaved trained model to: {model_path.resolve()}")

    # B. Save 2024 predictions CSV
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pred_df_2024 = pd.DataFrame({
        "timestamp_utc": df_2024["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%MZ"),
        "actual_intensity_gco2_per_kwh": y_test,
        "predicted_intensity_gco2_per_kwh": np.round(test_preds, 4),
        "absolute_error_gco2_per_kwh": np.round(np.abs(y_test - test_preds), 4),
    })
    pred_csv_path = REPORTS_DIR / "random_forest_predictions_2024.csv"
    pred_df_2024.to_csv(pred_csv_path, index=False)
    print(f"Saved 2024 predictions to: {pred_csv_path.resolve()} ({len(pred_df_2024):,} rows)")

    # C. Save metrics and configuration JSON
    feature_importances = {
        feat: round(float(imp), 6)
        for feat, imp in sorted(zip(FEATURES, rf.feature_importances_), key=lambda x: x[1], reverse=True)
    }

    metrics_payload = {
        "model_type": "RandomForestRegressor",
        "task": "Next-half-hour carbon intensity forecasting",
        "target_variable": TARGET,
        "features": FEATURES,
        "feature_count": len(FEATURES),
        "excluded_columns": EXCLUDED_COLUMNS,
        "model_parameters": MODEL_PARAMS,
        "training_time_seconds": round(train_duration, 2),
        "split_configuration": {
            "train_set": {
                "rows": len(train_df),
                "start": train_start,
                "end": train_end,
                "percentage_of_2023": 80.0,
            },
            "validation_set": {
                "rows": len(val_df),
                "start": val_start,
                "end": val_end,
                "percentage_of_2023": 20.0,
            },
            "test_set_2024": {
                "rows": len(df_2024),
                "start": test_start,
                "end": test_end,
                "description": "Full out-of-sample 2024 test period",
            },
        },
        "evaluation_assumptions": {
            "forecasting_horizon": "Next half-hour (1 step ahead)",
            "prediction_timing": "At start of interval T, actual reading for T-1 is finalized and available.",
            "zero_future_leakage": "No observation at or after interval T is used as a predictor.",
            "anomaly_treatment": "2023 modeled target contains verified historical outturn replacements for the 5 telemetry drops.",
        },
        "validation_metrics_2023": val_metrics,
        "test_metrics_2024": test_metrics,
        "baseline_comparison_2024": {
            "baseline_mae_gco2_per_kwh": BASELINE_2024_MAE,
            "model_mae_gco2_per_kwh": test_metrics["mae_gco2_per_kwh"],
            "mae_improvement_percent": round(mae_improvement_pct, 2),
            "baseline_rmse_gco2_per_kwh": BASELINE_2024_RMSE,
            "model_rmse_gco2_per_kwh": test_metrics["rmse_gco2_per_kwh"],
            "rmse_improvement_percent": round(rmse_improvement_pct, 2),
            "baseline_r2": BASELINE_2024_R2,
            "model_r2": test_metrics["r2_score"],
            "r2_improvement": round(r2_improvement, 4),
        },
        "top_feature_importances": feature_importances,
    }

    metrics_json_path = REPORTS_DIR / "random_forest_metrics.json"
    with open(metrics_json_path, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    print(f"Saved metrics & config to: {metrics_json_path.resolve()}")
    print("=" * 78)


if __name__ == "__main__":
    main()
