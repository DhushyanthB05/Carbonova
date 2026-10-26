"""
Carbonova Production Carbon Forecasting Model Training Script.

Reproduces the Random Forest Regressor artifact (models/random_forest_carbonova.joblib)
from the verified historical 2023 Great Britain NESO modeling trace.

Guarantees:
- Strict chronological forward splitting: 80% train, 20% validation, zero lookahead.
- Zero data leakage: 2024 test data is never touched during feature fitting, model training,
  or conformal calibration.
- Deterministic reproduction via fixed random seed (random_state=42).
- Explicit provenance and environment logging.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CarbonovaModelTraining")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_2023 = PROJECT_ROOT / "data" / "carbon_trace_2023_modeling.csv"
DEFAULT_DATA_2024 = PROJECT_ROOT / "data" / "carbon_trace_2024_modeling.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "random_forest_carbonova.joblib"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "reports" / "random_forest_metrics.json"

FEATURE_NAMES: List[str] = [
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

TARGET_COLUMN: str = "modeled_intensity_gco2_per_kwh"

MODEL_HYPERPARAMETERS: Dict[str, object] = {
    "n_estimators": 100,
    "max_depth": 16,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "max_features": 1.0,
    "random_state": 42,
    "n_jobs": -1,
}

TRAIN_SPLIT_ROWS = 14016  # 80% of 2023 (Jan 1, 00:00Z to Oct 19, 23:30Z)


def load_and_validate_training_data(filepath: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads 2023 modeling trace and performs chronological train/validation split.
    Guarantees no lookahead data leakage.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Training dataset not found: {filepath}")

    df = pd.read_csv(filepath)
    if "timestamp_utc" not in df.columns:
        raise ValueError("Missing 'timestamp_utc' column.")
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Missing target column '{TARGET_COLUMN}'.")

    # Validate feature presence
    missing_feats = [f for f in FEATURE_NAMES if f not in df.columns]
    if missing_feats:
        raise ValueError(f"Missing required feature columns: {missing_feats}")

    # Check for NaN in features or target
    nan_counts = df[FEATURE_NAMES + [TARGET_COLUMN]].isna().sum()
    if nan_counts.any():
        raise ValueError(f"Null values detected in training columns: {nan_counts[nan_counts > 0].to_dict()}")

    train_df = df.iloc[:TRAIN_SPLIT_ROWS].copy()
    val_df = df.iloc[TRAIN_SPLIT_ROWS:].copy()

    # Leakage check: verify timestamps are strictly chronological
    train_max_time = pd.to_datetime(train_df["timestamp_utc"]).max()
    val_min_time = pd.to_datetime(val_df["timestamp_utc"]).min()
    if train_max_time >= val_min_time:
        raise ValueError(f"Data leakage detected: train_max ({train_max_time}) >= val_min ({val_min_time})")

    logger.info("Chronological split validated:")
    logger.info(f"  Train: {len(train_df)} rows ({train_df['timestamp_utc'].iloc[0]} -> {train_max_time})")
    logger.info(f"  Validation: {len(val_df)} rows ({val_min_time} -> {val_df['timestamp_utc'].iloc[-1]})")

    return train_df, val_df


def train_model(train_df: pd.DataFrame) -> RandomForestRegressor:
    """
    Fits RandomForestRegressor with exact locked hyperparameters.
    """
    X_train = train_df[FEATURE_NAMES]
    y_train = train_df[TARGET_COLUMN]

    logger.info(f"Training RandomForestRegressor on {len(X_train)} samples with 17 features...")
    start_time = datetime.now()
    rf = RandomForestRegressor(**MODEL_HYPERPARAMETERS)
    rf.fit(X_train, y_train)
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Training completed in {elapsed:.2f} seconds.")

    return rf


def evaluate_model(
    model: RandomForestRegressor,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> Dict[str, Dict[str, float]]:
    """
    Computes standard MAE, RMSE, and R2 on validation and out-of-sample test traces.
    """
    # 2023 Validation
    X_val = val_df[FEATURE_NAMES]
    y_val = val_df[TARGET_COLUMN]
    val_preds = model.predict(X_val)

    val_metrics = {
        "mae_gco2_per_kwh": round(float(mean_absolute_error(y_val, val_preds)), 4),
        "rmse_gco2_per_kwh": round(float(root_mean_squared_error(y_val, val_preds)), 4),
        "r2_score": round(float(r2_score(y_val, val_preds)), 4),
    }

    # 2024 Out-of-sample Test
    X_test = test_df[FEATURE_NAMES]
    y_test = test_df[TARGET_COLUMN]
    test_preds = model.predict(X_test)

    test_metrics = {
        "mae_gco2_per_kwh": round(float(mean_absolute_error(y_test, test_preds)), 4),
        "rmse_gco2_per_kwh": round(float(root_mean_squared_error(y_test, test_preds)), 4),
        "r2_score": round(float(r2_score(y_test, test_preds)), 4),
    }

    return {"validation_2023": val_metrics, "test_2024": test_metrics}


def main():
    parser = argparse.ArgumentParser(description="Train and reproduce Carbonova's production Random Forest model.")
    parser.add_argument("--data-2023", type=Path, default=DEFAULT_DATA_2023, help="Path to 2023 modeling trace CSV")
    parser.add_argument("--data-2024", type=Path, default=DEFAULT_DATA_2024, help="Path to 2024 evaluation trace CSV")
    parser.add_argument("--output-model", type=Path, default=None, help="Destination for serialized model (.joblib)")
    parser.add_argument("--verify-stored", action="store_true", help="Verify retrained predictions against existing models/ artifact")
    args = parser.parse_args()

    logger.info("=== Carbonova Model Reproducibility Runner ===")
    logger.info(f"Scikit-learn version in runtime: {sklearn.__version__}")
    logger.info(f"Numpy version: {np.__version__}, Pandas: {pd.__version__}, Joblib: {joblib.__version__}")

    # 1. Load data
    train_df, val_df = load_and_validate_training_data(args.data_2023)
    test_df = pd.read_csv(args.data_2024)

    # 2. Train
    model = train_model(train_df)

    # 3. Evaluate
    metrics = evaluate_model(model, val_df, test_df)
    logger.info(f"2023 Validation Metrics: {json.dumps(metrics['validation_2023'], indent=2)}")
    logger.info(f"2024 Test Metrics:       {json.dumps(metrics['test_2024'], indent=2)}")

    # 4. Optional verification against stored artifact
    if args.verify_stored:
        if not DEFAULT_MODEL_PATH.exists():
            logger.warning(f"Cannot verify: stored model not found at {DEFAULT_MODEL_PATH}")
        else:
            stored_model = joblib.load(DEFAULT_MODEL_PATH)
            X_test = test_df[FEATURE_NAMES]
            stored_preds = stored_model.predict(X_test)
            new_preds = model.predict(X_test)
            max_diff = float(np.max(np.abs(new_preds - stored_preds)))
            logger.info(f"Verification vs stored model across {len(X_test)} samples:")
            logger.info(f"  Max absolute difference: {max_diff:.8f} gCO2/kWh")
            if max_diff < 1e-4:
                logger.info("  RESULT: VERIFIED NUMERICALLY IDENTICAL.")
            else:
                logger.warning(f"  RESULT: Numerical divergence detected (max_diff={max_diff:.6f}).")

    # 5. Save if output path requested
    if args.output_model:
        args.output_model.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, args.output_model)
        logger.info(f"Saved retrained model artifact to: {args.output_model}")


if __name__ == "__main__":
    main()
