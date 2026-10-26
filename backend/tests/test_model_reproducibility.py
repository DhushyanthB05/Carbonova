"""
Unit Tests for Carbonova Carbon Forecast Model Reproducibility and Data Lineage.

Verifies:
- Model artifact hyperparameters, feature schema, and random seed integrity.
- Chronological forward splitting and absence of lookahead data leakage.
- Non-negativity and consistency of out-of-sample inference.
- Existence of standalone training script and provenance documentation.
"""

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from scripts.train_carbon_model import (
    DEFAULT_DATA_2023,
    DEFAULT_DATA_2024,
    DEFAULT_MODEL_PATH,
    FEATURE_NAMES,
    MODEL_HYPERPARAMETERS,
    TARGET_COLUMN,
    TRAIN_SPLIT_ROWS,
)


def test_model_artifact_parameters_and_features():
    assert DEFAULT_MODEL_PATH.exists(), f"Model artifact not found at {DEFAULT_MODEL_PATH}"
    model = joblib.load(DEFAULT_MODEL_PATH)

    # Check feature count and names
    assert hasattr(model, "feature_names_in_")
    assert list(model.feature_names_in_) == FEATURE_NAMES
    assert model.n_features_in_ == 17

    # Check hyperparameters
    params = model.get_params()
    assert params["n_estimators"] == MODEL_HYPERPARAMETERS["n_estimators"]
    assert params["max_depth"] == MODEL_HYPERPARAMETERS["max_depth"]
    assert params["min_samples_split"] == MODEL_HYPERPARAMETERS["min_samples_split"]
    assert params["min_samples_leaf"] == MODEL_HYPERPARAMETERS["min_samples_leaf"]
    assert params["random_state"] == MODEL_HYPERPARAMETERS["random_state"]


def test_training_data_chronological_integrity_and_zero_leakage():
    assert DEFAULT_DATA_2023.exists()
    assert DEFAULT_DATA_2024.exists()

    df23 = pd.read_csv(DEFAULT_DATA_2023)
    df24 = pd.read_csv(DEFAULT_DATA_2024)

    assert len(df23) == 17520
    assert len(df24) == 17568

    train_df = df23.iloc[:TRAIN_SPLIT_ROWS]
    val_df = df23.iloc[TRAIN_SPLIT_ROWS:]

    t_train_max = pd.to_datetime(train_df["timestamp_utc"]).max()
    t_val_min = pd.to_datetime(val_df["timestamp_utc"]).min()
    t_val_max = pd.to_datetime(val_df["timestamp_utc"]).max()
    t_test_min = pd.to_datetime(df24["timestamp_utc"]).min()

    # Assert strict chronological forward order: train < val <= test
    assert t_train_max < t_val_min, "Leakage: Train set overlaps with validation set!"
    assert t_val_max <= t_test_min, "Leakage: 2023 validation overlaps with 2024 test set!"

    # Zero nulls
    assert not train_df[FEATURE_NAMES + [TARGET_COLUMN]].isna().any().any()
    assert not df24[FEATURE_NAMES + [TARGET_COLUMN]].isna().any().any()


def test_model_inference_on_2024_evaluation_trace():
    model = joblib.load(DEFAULT_MODEL_PATH)
    df24 = pd.read_csv(DEFAULT_DATA_2024)

    X_test = df24[FEATURE_NAMES]
    y_test = df24[TARGET_COLUMN]

    preds = model.predict(X_test)
    assert len(preds) == 17568
    assert np.all(preds > 0.0), "Predicted carbon intensities must be strictly positive"

    mae = float(np.mean(np.abs(preds - y_test)))
    rmse = float(np.sqrt(np.mean((preds - y_test) ** 2)))

    # Must match documented report metrics (4.1455 MAE, 5.6275 RMSE) within tight numerical tolerance
    assert abs(mae - 4.1455) < 0.01
    assert abs(rmse - 5.6275) < 0.01


def test_provenance_and_training_scripts_exist():
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "train_carbon_model.py"
    provenance_doc = project_root / "docs" / "DATA_PROVENANCE_AND_LICENSING.md"

    assert script_path.exists(), "scripts/train_carbon_model.py must exist"
    assert provenance_doc.exists(), "docs/DATA_PROVENANCE_AND_LICENSING.md must exist"
