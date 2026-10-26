#!/usr/bin/env python3
"""
Forecast Uncertainty Estimation for Carbonova Carbon Intensity Forecasting

STEP 4: Split Conformal Prediction for Next-Half-Hour Carbon Intensity Forecasts

Objective:
  Estimate calibrated 90% prediction intervals around point predictions produced
  by the trained Random Forest model (models/random_forest_carbonova.joblib) using
  split conformal prediction.

Calibration & Evaluation Partitions:
  - 2023 Model-Fitting Period      : 14,016 rows (2023-01-01T00:00Z -> 2023-10-19T23:30Z, 80%)
  - 2023 Validation Period         : 1,752 rows (2023-10-20T00:00Z -> 2023-11-25T11:30Z, 10%)
  - 2023 Uncertainty-Calibration   : 1,752 rows (2023-11-25T12:00Z -> 2023-12-31T23:30Z, 10%)
  - 2024 Final Out-of-Sample Test  : 17,568 rows (2024-01-01T00:00Z -> 2024-12-31T23:30Z)

Outputs:
  - reports/uncertainty_predictions_2024.csv
  - reports/uncertainty_metrics.json
"""

import json
from pathlib import Path
import sys
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd

# Check dependencies before running
try:
    import joblib
    from sklearn.metrics import mean_absolute_error, mean_squared_error
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
NOMINAL_COVERAGE: float = 0.90
ALPHA: float = 1.0 - NOMINAL_COVERAGE


def load_datasets() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load and validate 2023 and 2024 modeling datasets."""
    path_2023 = DATA_DIR / "carbon_trace_2023_modeling.csv"
    path_2024 = DATA_DIR / "carbon_trace_2024_modeling.csv"

    if not path_2023.exists():
        raise FileNotFoundError(f"2023 dataset missing: {path_2023.resolve()}")
    if not path_2024.exists():
        raise FileNotFoundError(f"2024 dataset missing: {path_2024.resolve()}")

    df_2023 = pd.read_csv(path_2023)
    df_2024 = pd.read_csv(path_2024)

    for name, df in [("2023", df_2023), ("2024", df_2024)]:
        if TARGET not in df.columns:
            raise ValueError(f"Target column '{TARGET}' missing in {name} dataset.")
        missing_feats = [f for f in FEATURES if f not in df.columns]
        if missing_feats:
            raise ValueError(f"Feature columns missing in {name} dataset: {missing_feats}")
        df["dt"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
        if df["dt"].isna().any():
            raise ValueError(f"Unparseable timestamps detected in {name} dataset.")

    df_2023 = df_2023.sort_values("dt").reset_index(drop=True)
    df_2024 = df_2024.sort_values("dt").reset_index(drop=True)

    return df_2023, df_2024


def load_model():
    """Load the trained Random Forest model and verify compatibility."""
    model_path = MODELS_DIR / "random_forest_carbonova.joblib"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Trained model not found at {model_path.resolve()}. "
            "Please ensure train_random_forest.py has been executed."
        )
    return joblib.load(model_path)


def compute_conformal_quantile(residuals: np.ndarray, alpha: float) -> Tuple[float, int, float]:
    """
    Compute split conformal prediction quantile using finite-sample adjustment.

    Formula:
      k = ceil((n + 1) * (1 - alpha))
      p = k / n
      q_hat = sorted_residuals[k - 1]
    """
    n = len(residuals)
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        raise ValueError(f"Calibration size n={n} too small for nominal coverage {1-alpha:.2f}.")

    empirical_p = k / n
    sorted_residuals = np.sort(residuals)
    q_hat = float(sorted_residuals[k - 1])

    return q_hat, k, empirical_p


def main():
    print("=" * 78)
    print("CARBONOVA: STEP 4 - SPLIT CONFORMAL UNCERTAINTY ESTIMATION (90% INTERVALS)")
    print("=" * 78)

    # 1. Load model and data
    print("Loading datasets and trained model...")
    df_2023, df_2024 = load_datasets()
    rf = load_model()

    print(f"  * 2023 dataset loaded: {len(df_2023):,} rows")
    print(f"  * 2024 dataset loaded: {len(df_2024):,} rows")
    print(f"  * Random Forest model loaded from {MODELS_DIR / 'random_forest_carbonova.joblib'}")

    # 2. Chronological 3-way Split of 2023
    # Model fitting was trained on the first 14,016 rows (80%).
    # The remaining 3,504 rows are partitioned into validation and calibration.
    fit_end_idx = 14016
    val_end_idx = 14016 + 1752  # 15,768

    fit_df = df_2023.iloc[:fit_end_idx].copy()
    val_df = df_2023.iloc[fit_end_idx:val_end_idx].copy()
    cal_df = df_2023.iloc[val_end_idx:].copy()

    fit_start_str = fit_df["dt"].iloc[0].strftime("%Y-%m-%dT%H:%MZ")
    fit_end_str = fit_df["dt"].iloc[-1].strftime("%Y-%m-%dT%H:%MZ")

    val_start_str = val_df["dt"].iloc[0].strftime("%Y-%m-%dT%H:%MZ")
    val_end_str = val_df["dt"].iloc[-1].strftime("%Y-%m-%dT%H:%MZ")

    cal_start_str = cal_df["dt"].iloc[0].strftime("%Y-%m-%dT%H:%MZ")
    cal_end_str = cal_df["dt"].iloc[-1].strftime("%Y-%m-%dT%H:%MZ")

    test_start_str = df_2024["dt"].iloc[0].strftime("%Y-%m-%dT%H:%MZ")
    test_end_str = df_2024["dt"].iloc[-1].strftime("%Y-%m-%dT%H:%MZ")

    print("\n--- Chronological Partitioning ---")
    print(f"  1. Model-Fitting Period    : {len(fit_df):,} rows (80.0%) [{fit_start_str} -> {fit_end_str}]")
    print(f"  2. Validation Period       : {len(val_df):,} rows (10.0%) [{val_start_str} -> {val_end_str}]")
    print(f"  3. Uncertainty Calibration : {len(cal_df):,} rows (10.0%) [{cal_start_str} -> {cal_end_str}]")
    print(f"  4. Final Evaluation (2024) : {len(df_2024):,} rows (100.0%) [{test_start_str} -> {test_end_str}]")
    print("  * Note: Calibration partition was never seen during model fitting or tree induction.")

    # 3. Calibration: Compute absolute residuals on held-out calibration set
    print("\n--- Conformal Calibration (Nominal 90% Coverage) ---")
    cal_preds = rf.predict(cal_df[FEATURES])
    cal_actuals = cal_df[TARGET].values
    cal_residuals = np.abs(cal_actuals - cal_preds)

    n_cal = len(cal_residuals)
    q_hat, k_index, empirical_p = compute_conformal_quantile(cal_residuals, ALPHA)

    print(f"  * Calibration sample size (n) : {n_cal:,} intervals")
    print(f"  * Target quantile index (k)   : {k_index} of {n_cal} (p = {empirical_p:.6f})")
    print(f"  * Conformal quantile (q_hat)  : {q_hat:.4f} gCO2/kWh")
    print(f"  * Calibrated interval half-width: +/- {q_hat:.4f} gCO2/kWh")
    print(f"  * Calibrated full width       : {2 * q_hat:.4f} gCO2/kWh")

    # 4. Evaluation on 2024 (Untouched test period)
    print("\n--- Out-of-Sample Evaluation on 2024 Test Set ---")
    test_preds = rf.predict(df_2024[FEATURES])
    test_actuals = df_2024[TARGET].values
    test_abs_errors = np.abs(test_actuals - test_preds)

    test_mae = float(mean_absolute_error(test_actuals, test_preds))
    test_rmse = float(np.sqrt(mean_squared_error(test_actuals, test_preds)))

    # Compute prediction interval bounds
    lower_bounds = test_preds - q_hat
    upper_bounds = test_preds + q_hat

    # Bound ordering and physical plausibility check
    ordered_correctly = bool(np.all(lower_bounds <= upper_bounds))
    count_negative_lower = int(np.sum(lower_bounds < 0.0))
    min_lower_bound = float(np.min(lower_bounds))
    min_pred = float(np.min(test_preds))

    # Empirical coverage calculation
    covered_mask = (test_actuals >= lower_bounds) & (test_actuals <= upper_bounds)
    empirical_coverage_pct = float(np.mean(covered_mask) * 100.0)
    avg_interval_width = float(np.mean(upper_bounds - lower_bounds))

    print(f"  * Evaluated Rows              : {len(df_2024):,}")
    print(f"  * Point Forecast MAE          : {test_mae:.4f} gCO2/kWh")
    print(f"  * Point Forecast RMSE         : {test_rmse:.4f} gCO2/kWh")
    print(f"  * Nominal Coverage            : {NOMINAL_COVERAGE * 100:.1f}%")
    print(f"  * Empirical 90% Coverage      : {empirical_coverage_pct:.2f}% ({np.sum(covered_mask):,} / {len(df_2024):,})")
    print(f"  * Average Interval Width      : {avg_interval_width:.4f} gCO2/kWh")
    print(f"  * Interval Bounds Ordered     : {ordered_correctly} (lower <= upper)")
    print(f"  * Minimum Lower Bound         : {min_lower_bound:.2f} gCO2/kWh")
    print(f"  * Negative Lower Bounds Count : {count_negative_lower} (No physical truncation required)")

    # 5. Monthly Coverage Breakdown
    print("\n--- 2024 Empirical Coverage Breakdown by Month ---")
    monthly_metrics: Dict[str, Dict[str, Any]] = {}
    df_eval = pd.DataFrame({
        "month_num": df_2024["dt"].dt.month,
        "month_name": df_2024["dt"].dt.strftime("%B"),
        "actual": test_actuals,
        "pred": test_preds,
        "lower": lower_bounds,
        "upper": upper_bounds,
        "covered": covered_mask,
    })

    for m_num, grp in df_eval.groupby("month_num"):
        m_name = grp["month_name"].iloc[0]
        m_cov = float(np.mean(grp["covered"]) * 100.0)
        m_covered_count = int(grp["covered"].sum())
        m_total = len(grp)
        m_mae = float(np.mean(np.abs(grp["actual"] - grp["pred"])))

        monthly_metrics[f"{m_num:02d}_{m_name}"] = {
            "month_number": int(m_num),
            "month_name": m_name,
            "total_intervals": m_total,
            "covered_intervals": m_covered_count,
            "empirical_coverage_percent": round(m_cov, 2),
            "mae_gco2_per_kwh": round(m_mae, 4),
        }
        print(f"  * {m_num:02d} ({m_name:<9s}): {m_cov:6.2f}% coverage ({m_covered_count:,}/{m_total:,} intervals) | MAE: {m_mae:.4f}")

    # 6. Save Predictions CSV
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = REPORTS_DIR / "uncertainty_predictions_2024.csv"
    pred_export_df = pd.DataFrame({
        "timestamp_utc": df_2024["dt"].dt.strftime("%Y-%m-%dT%H:%MZ"),
        "actual_intensity_gco2_per_kwh": test_actuals,
        "predicted_intensity_gco2_per_kwh": np.round(test_preds, 4),
        "lower_90_gco2_per_kwh": np.round(lower_bounds, 4),
        "upper_90_gco2_per_kwh": np.round(upper_bounds, 4),
        "absolute_error_gco2_per_kwh": np.round(test_abs_errors, 4),
    })
    pred_export_df.to_csv(out_csv, index=False)
    print(f"\nSaved 2024 predictions to: {out_csv.resolve()} ({len(pred_export_df):,} rows)")

    # 7. Save Metrics JSON
    out_json = REPORTS_DIR / "uncertainty_metrics.json"
    metrics_payload = {
        "method": "Split Conformal Prediction",
        "target_variable": TARGET,
        "nominal_coverage_percent": round(NOMINAL_COVERAGE * 100.0, 1),
        "alpha": ALPHA,
        "conformal_calibration_details": {
            "calibration_dataset": "data/carbon_trace_2023_modeling.csv (Nov 25 12:00Z -> Dec 31 23:30Z)",
            "sample_size_n": n_cal,
            "finite_sample_rank_k": k_index,
            "empirical_quantile_p": round(empirical_p, 6),
            "quantile_half_width_q_hat_gco2_per_kwh": round(q_hat, 4),
            "interval_full_width_gco2_per_kwh": round(2 * q_hat, 4),
        },
        "chronological_partitions": {
            "model_fitting_2023": {"start": fit_start_str, "end": fit_end_str, "rows": len(fit_df), "share": 0.80},
            "validation_2023": {"start": val_start_str, "end": val_end_str, "rows": len(val_df), "share": 0.10},
            "calibration_2023": {"start": cal_start_str, "end": cal_end_str, "rows": len(cal_df), "share": 0.10},
            "test_2024": {"start": test_start_str, "end": test_end_str, "rows": len(df_2024), "share": 1.00},
        },
        "evaluation_2024_summary": {
            "evaluated_rows": len(df_2024),
            "point_mae_gco2_per_kwh": round(test_mae, 4),
            "point_rmse_gco2_per_kwh": round(test_rmse, 4),
            "empirical_coverage_percent": round(empirical_coverage_pct, 2),
            "covered_intervals": int(np.sum(covered_mask)),
            "average_interval_width_gco2_per_kwh": round(avg_interval_width, 4),
            "bounds_ordered_correctly": ordered_correctly,
            "minimum_lower_bound_gco2_per_kwh": round(min_lower_bound, 4),
            "negative_lower_bounds_count": count_negative_lower,
            "clipping_applied": False,
        },
        "monthly_empirical_coverage_2024": monthly_metrics,
        "theoretical_assumptions_and_limitations": {
            "exchangeability_assumption": (
                "Split conformal prediction guarantees marginal coverage (>= 1 - alpha) under the assumption "
                "that calibration and test residuals are exchangeable (drawn from the same joint distribution)."
            ),
            "time_series_limitations": [
                "Temporal Autocorrelation: Carbon intensity errors exhibit serial dependence; error bursts cluster during anomalous weather fronts.",
                "Diurnal & Seasonal Heteroskedasticity: Prediction variance is higher during midday solar and evening demand ramps than overnight base-load periods.",
                "Grid Structural Shift: Increasing renewable capacity (wind, solar) and coal phase-out alter generation distributions between 2023 and 2024.",
                "Marginal vs Conditional Coverage: Coverage is guaranteed marginally across the distribution, not necessarily conditionally on every specific sub-regime or extreme wind lull.",
            ],
            "validity_statement": (
                "Prediction intervals provide empirical coverage based on finite-sample conformal calibration; "
                "they do not provide unconditional mathematical guarantees under arbitrary non-stationary distribution shifts."
            ),
        },
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    print(f"Saved uncertainty metrics to: {out_json.resolve()}")
    print("=" * 78)


if __name__ == "__main__":
    main()
