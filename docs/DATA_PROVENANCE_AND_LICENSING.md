# Carbonova — Data Provenance, Licensing & Model Reproducibility Specification

**Author:** Member 2 (Core Scheduling Engine & Metrics)
**Scope:** Data Sourcing, Anomaly Imputations, Model Lineage, and Licensing Compliance
**Authoritative Reference:** `Carbonova_Finalised_Locked_Project_Report.docx`

---

## 1. Primary Carbon Data Provenance: Great Britain NESO

### A. Source Authority and API
* **Primary Authority:** National Energy System Operator (NESO) of Great Britain (formerly National Grid ESO).
* **Research Partners:** Environmental Defense Fund Europe (EDF Europe) and the Department of Computer Science at the University of Oxford.
* **Official API Service:** NESO Carbon Intensity API (`https://api.carbonintensity.org.uk/`).
* **API Documentation:** [https://carbon-intensity.github.io/api-definitions/](https://carbon-intensity.github.io/api-definitions/)
* **Geographic Coverage:** National Great Britain electricity transmission grid (`GB`).
* **Temporal Resolution:** Half-hour electricity settlement periods ($48$ intervals per day), strictly UTC timestamps.
* **Physical Units:** Grams of carbon dioxide per kilowatt-hour ($\text{gCO}_2/\text{kWh}$).

### B. Licensing Terms & Mandatory Attribution
* **Primary Licence:** **Creative Commons Attribution 4.0 International (CC BY 4.0)**.
* **Terms Reference:** [https://github.com/carbon-intensity/terms](https://github.com/carbon-intensity/terms)
* **Official Attribution Statement:**
  > *"Contains public sector information published by the National Energy System Operator (NESO) and licensed under the Creative Commons Attribution 4.0 International Licence (CC BY 4.0)."*
* **Compliance Note:** Any academic paper, dashboard, or redistributed dataset derived from this trace must retain this attribution statement.

---

## 2. Telemetry Anomaly Recovery & Elexon BMRS Provenance

### A. Telemetry Dropouts in the 2023 Trace
During data integrity screening of `data/carbon_trace_2023_modeling.csv` ($17{,}520$ half-hour intervals), exactly five intervals were identified with zero-intensity telemetry failure (`raw: 0.0 gCO2/kWh`):

| Row in 2023 Trace | Timestamp (UTC) | Raw API Intensity | Modeled / Imputed Outturn | Imputation Method | Verified Source |
| :---: | :---: | :---: | :---: | :--- | :--- |
| **1442** | `2023-01-31T01:00Z` | $0.0\text{ gCO}_2/\text{kWh}$ | **$94.0\text{ gCO}_2/\text{kWh}$** | `neso_historic_outturn` | Elexon BMRS Metered Physical Generation |
| **7555** | `2023-06-07T09:30Z` | $0.0\text{ gCO}_2/\text{kWh}$ | **$174.0\text{ gCO}_2/\text{kWh}$** | `neso_historic_outturn` | Elexon BMRS Metered Physical Generation |
| **7556** | `2023-06-07T10:00Z` | $0.0\text{ gCO}_2/\text{kWh}$ | **$185.0\text{ gCO}_2/\text{kWh}$** | `neso_historic_outturn` | Elexon BMRS Metered Physical Generation |
| **7557** | `2023-06-07T10:30Z` | $0.0\text{ gCO}_2/\text{kWh}$ | **$179.0\text{ gCO}_2/\text{kWh}$** | `neso_historic_outturn` | Elexon BMRS Metered Physical Generation |
| **7558** | `2023-06-07T11:00Z` | $0.0\text{ gCO}_2/\text{kWh}$ | **$173.0\text{ gCO}_2/\text{kWh}$** | `neso_historic_outturn` | Elexon BMRS Metered Physical Generation |

### B. Elexon BMRS Separate Licensing Terms
* **Imputation Authority:** Elexon Balancing Mechanism Reporting Service (BMRS).
* **Licensing Scope:** Elexon market data is governed by the **Balancing and Settlement Code (BSC) Open Data Provisions**, which is distinct from CC BY 4.0. Elexon allows research and commercial utilization subject to attribution of Elexon as the data provider.
* **Dual-Source Attribution Requirement:**
  > *"Carbon intensity traces contain data from the NESO Carbon Intensity API (CC BY 4.0) with five telemetry dropout intervals cross-referenced against authoritative metered fuel-mix tables published by Elexon BMRS under BSC Data Terms."*

---

## 3. Production Model Lineage & Reproducibility

### A. Model Specification
* **Model Class:** `sklearn.ensemble.RandomForestRegressor`
* **Artifact Path:** `models/random_forest_carbonova.joblib` ($9.19\text{ MB}$)
* **Hyperparameters:**
  ```python
  {
      "n_estimators": 100,
      "max_depth": 16,
      "min_samples_split": 5,
      "min_samples_leaf": 2,
      "max_features": 1.0,
      "random_state": 42,
      "n_jobs": -1,
  }
  ```
* **Engineered Features ($17$):**
  `lag_1_half_hour`, `lag_2_half_hour`, `lag_48_half_hour`, `lag_336_half_hour`,
  `rolling_mean_past_24h`, `rolling_std_past_24h`, `hour`, `day_of_week`, `month`,
  `is_weekend`, `settlement_period`, `sin_hour`, `cos_hour`, `sin_period`,
  `cos_period`, `sin_day_of_week`, `cos_day_of_week`.

### B. Chronological Splitting (Zero Lookahead Leakage)
1. **Model Fitting Split:** `2023-01-01T00:00Z` to `2023-10-19T23:30Z` ($n = 14{,}016$ samples, 80% of 2023).
2. **Model Validation Split:** `2023-10-20T00:00Z` to `2023-11-25T11:30Z` ($n = 1{,}752$ samples, 10% of 2023).
3. **Conformal Calibration Split:** `2023-11-25T12:00Z` to `2023-12-31T23:30Z` ($n = 1{,}752$ samples, 10% of 2023).
4. **Out-of-Sample Evaluation Trace:** `2024-01-01T00:00Z` to `2024-12-31T23:30Z` ($n = 17{,}568$ samples, 100% of 2024).

### C. Standalone Retraining Script
The training workflow is reproducible via:
```bash
python scripts/train_carbon_model.py --verify-stored
```
* **Numerical Verification:** Re-training with scikit-learn 1.9.1 reproduces the stored model predictions on all $17{,}568$ samples of 2024 with a maximum absolute difference of **$0.000000\text{ gCO}_2/\text{kWh}$**.
* **Metrics Verified:**
  - 2023 Validation: $\text{MAE} = 4.8039$, $\text{RMSE} = 6.4704$, $R^2 = 0.9926$
  - 2024 Out-of-sample: $\text{MAE} = 4.1455$, $\text{RMSE} = 5.6275$, $R^2 = 0.9912$

### D. Scikit-Learn Version Analysis
* **Originating Environment:** Scikit-learn `1.9.0`.
* **Runtime Environment:** Scikit-learn `1.9.1`.
* **Warning Emitted:** `InconsistentVersionWarning`.
* **Recommendation:** Because retrained model predictions under 1.9.1 are bit-for-bit identical ($0.000000\text{ diff}$), the model artifact can safely be re-saved under 1.9.1 whenever authorized, or `scikit-learn==1.9.0` can be pinned in `requirements.txt`.

---

## 4. Uncertainty Quantification Scope & Methodology

### A. Native 30-Minute Settlement Periods: Formally Calibrated Conformal Intervals
* **Method:** Inductive Split-Conformal Prediction.
* **Calibration Set:** Final $1{,}752$ intervals of 2023 (Nov 25 – Dec 31).
* **Nominal Coverage:** $90.0\%$ ($\alpha = 0.10$).
* **Finite-Sample Rank:** $k = \lceil 1753 \times 0.90 \rceil = 1578$.
* **Global Cutoff:** $\hat{q}_{\text{global}} = 9.7424\text{ gCO}_2/\text{kWh}$ (achieves $92.40\%$ empirical coverage on 2024).
* **Diurnal Regime Cutoffs:**
  - `night_baseload` (00:00 – 06:30 UTC): $\hat{q} = 11.2830\text{ gCO}_2/\text{kWh}$ ($93.61\%$ coverage)
  - `morning_ramp` (07:00 – 11:30 UTC): $\hat{q} = 9.3182\text{ gCO}_2/\text{kWh}$ ($92.87\%$ coverage)
  - `afternoon_solar` (12:00 – 16:30 UTC): $\hat{q} = 8.2760\text{ gCO}_2/\text{kWh}$ ($90.60\%$ coverage)
  - `evening_peak` (17:00 – 23:30 UTC): $\hat{q} = 10.4554\text{ gCO}_2/\text{kWh}$ ($92.82\%$ coverage)
* **Metadata Tag:** `"formal_conformal_calibrated": True`.

### B. Aggregated 60-Minute Hourly Slots: Conservative Heuristic Risk Scores
* **Aggregation Rule:** Arithmetic mean of constituent half-hour quantiles: $\overline{\sigma} = (\sigma_0 + \sigma_1)/2.0$.
* **Empirical Evidence (Full 2024 Trace, 8,784 Hours):** The interval $[\overline{L}, \overline{U}]$ contains the realized hourly average carbon intensity in **$96.61\%$** of hours (8,486 / 8,784).
* **Statistical Meaning:** Because averaging correlated time-series variables reduces variance, linear interval averaging produces **super-coverage** ($96.61\% > 90.0\%$).
* **Scientific Scope:** It is a **conservative heuristic scheduling-risk score** that guarantees $\ge 90\%$ coverage, but it is **not** a newly calibrated marginal 90% conformal predictor for hourly series.
* **Metadata Tag:** `"formal_conformal_calibrated": False`, `"uncertainty_type": "conservative_heuristic_risk_score"`.
