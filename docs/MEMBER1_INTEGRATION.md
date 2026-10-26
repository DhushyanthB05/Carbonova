# Member 1 Integration Contract: Carbon Data, Forecasting & Scheduler Engine

**Module Developer:** Dhushyanth (Member 1)
**Branch:** `dhushyanth`
**Repository Path:** `C:\Users\Dhushyanth B\OneDrive\Desktop\Carbonova`
**Target Consumers:** Member 2 (Backend API / Orchestration) & Member 3 (Frontend / Dashboard)
**Current Test Status:** 54 passing unit tests (100% pass rate)

---

## 1. Executive Summary & Deliverables Overview

Member 1 has completed and formally verified all foundational carbon data ingestion, trace validation, machine learning forecasting, conformal uncertainty estimation, provider fallbacks, and scheduling engine components. Members 2 and 3 can integrate directly with these Python modules without waiting for further forecasting work.

### Core Deliverables Provided by Member 1:
1. **Clean Modeling Datasets (Great Britain NESO Data):**
   * [`data/carbon_trace_2023_modeling.csv`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/data/carbon_trace_2023_modeling.csv) (17,520 half-hour intervals, 5 documented anomalies with verified historical outturn replacements, 0 nulls, 0 data leakage).
   * [`data/carbon_trace_2024_modeling.csv`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/data/carbon_trace_2024_modeling.csv) (17,568 half-hour intervals, strictly out-of-sample evaluation trace).
2. **Trained Production Model:**
   * [`models/random_forest_carbonova.joblib`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/models/random_forest_carbonova.joblib) (100-tree Random Forest, 17 engineered features, 2024 test MAE: 4.1455 gCO2/kWh vs. fair 30-min baseline 4.9265 gCO2/kWh and 24h baseline 40.7313 gCO2/kWh).
3. **Calibrated Split Conformal Uncertainty (Global & Slot-Specific Diurnal):**
   * [`reports/uncertainty_metrics.json`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/reports/uncertainty_metrics.json) (Nominal 90% coverage cutoff: Global $\hat{q} = 9.7424\ \text{gCO}_2/\text{kWh}$, achieving 92.40% empirical coverage on 2024; Diurnal regime cutoffs: solar 8.2760, ramp 9.3182, peak 10.4554, baseload 11.2830, achieving 92.58% overall coverage).
4. **Production Forecasting & Provider Module:**
   * [`backend/carbon/schemas.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/carbon/schemas.py) (Pydantic data models).
   * [`backend/carbon/provider.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/carbon/provider.py) (`CarbonDataProvider`, `ProvenanceMetadata`, `DataStatus`).
   * [`backend/carbon/service.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/carbon/service.py) (`CarbonForecastService`).
5. **Workload Scheduling & Trace Simulation Module:**
   * [`backend/scheduler/schemas.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/scheduler/schemas.py) (`WorkloadJob`, `SchedulingDecision`, `DecisionType`).
   * [`backend/scheduler/engine.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/scheduler/engine.py) (`FIFOScheduler`, `CarbonovaScheduler`, `WorkloadScheduler`).
   * [`backend/scheduler/simulation.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/scheduler/simulation.py) (`TraceSimulationEngine`, `SyntheticWorkloadGenerator`).
6. **Automated Unit Test Suites (54 Tests Total, 100% Pass):**
   * [`backend/tests/test_carbon_provider.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/tests/test_carbon_provider.py) (10 tests).
   * [`backend/tests/test_carbon_service.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/tests/test_carbon_service.py) (20 tests).
   * [`backend/tests/test_scheduler.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/tests/test_scheduler.py) (19 tests).
   * [`backend/tests/test_scheduler_simulation.py`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/backend/tests/test_scheduler_simulation.py) (5 tests).

---

## 2. Carbon Data Provider Interface

### A. Python Import Path
```python
from backend.carbon.provider import CarbonDataProvider, DataStatus, ProvenanceMetadata
from backend.carbon.schemas import CarbonObservation
```

### B. Trace Loading & Fallback Methods
```python
provider = CarbonDataProvider()

# 1. Load recorded historical trace with integrity validation
observations, metadata = provider.load_recorded_trace(
    filepath="data/carbon_trace_2024_modeling.csv",
    start_time_utc=None,   # Optional datetime filter
    end_time_utc=None
)

# 2. Get live observations with automatic, non-crashing fallback
# In offline environments, automatically falls back to verified recorded trace
obs_buffer, prov = provider.get_live_or_fallback(buffer_length=336)
print(prov.data_status)      # DataStatus.RECORDED
print(prov.fallback_reason)  # "Live NESO API endpoint offline/unconfigured; safely fell back to verified recorded trace."
```

---

## 3. Carbon Forecast Service Interface

### A. Python Import Path
```python
from backend.carbon.service import CarbonForecastService
from backend.carbon.schemas import (
    CarbonForecastResponse,
    CarbonIntensitySlot,
    CarbonObservation,
)
```

### B. Initialization
```python
# Automatically resolves model, metrics, and provider relative to project root
forecast_service = CarbonForecastService()
```

### C. Required Input History & Timestamp Conventions
* **Buffer Length:** At least **336 continuous half-hour intervals** (7 full days) to calculate `lag_336_half_hour` and 24-hour rolling statistics.
* **Automatic Fallback:** If `history=None` is passed, the service automatically sources the most recent 336 recorded intervals via `CarbonDataProvider`.
* **Timestamps:** ISO 8601 UTC strings or timezone-aware `datetime.datetime` objects.
* **Continuity:** Must be contiguous at 30-minute intervals without missing slots or negative values.

### D. Prediction Method Signature
```python
response: CarbonForecastResponse = forecast_service.predict_next_half_hour(
    history=None,                    # Optional: defaults to provider's recorded buffer
    target_timestamp=None,           # Optional: defaults to last_timestamp + 30 min
    data_status="live",              # Optional operational status
    uncertainty_mode="global"        # 'global' (q_hat=9.7424) or 'diurnal' (slot-specific)
)
```

### E. Exact Response Schema (`CarbonForecastResponse`)
```json
{
  "generated_at_utc": "2024-06-15T14:00:00Z",
  "model_name": "RandomForestRegressor_Conformal",
  "model_version": "1.0.0",
  "data_status": "live",
  "nominal_interval_label": "Nominal 90% Prediction Interval",
  "calibrated_quantile_q_hat_gco2_per_kwh": 9.7424,
  "slots": [
    {
      "timestamp_utc": "2024-06-15T14:30:00Z",
      "predicted_intensity_gco2_per_kwh": 65.4125,
      "lower_90_gco2_per_kwh": 55.6701,
      "upper_90_gco2_per_kwh": 75.1549,
      "uncertainty_width_gco2_per_kwh": 19.4848,
      "model_name": "RandomForestRegressor_Conformal",
      "forecast_horizon": "next_half_hour"
    }
  ],
  "disclaimer": "Nominal 90% prediction intervals calibrated via split conformal prediction on historical grid observations. Intervals provide empirical coverage under exchangeable conditions and do not guarantee future performance under non-stationary grid regime shifts."
}
```

---

## 4. Workload Scheduler Interface

### A. Python Import Path
```python
from backend.scheduler.engine import (
    FIFOScheduler,
    CarbonovaScheduler,
    WorkloadScheduler,
)
from backend.scheduler.schemas import (
    WorkloadJob,
    SchedulingDecision,
    DecisionType,
)
```

### B. Workload Job Schema (`WorkloadJob`)
```python
from datetime import datetime, timezone

job = WorkloadJob(
    job_id="job_train_001",
    arrival_time_utc=datetime(2024, 6, 15, 14, 0, tzinfo=timezone.utc),
    duration_half_hours=4,       # 2 hours total execution time
    deadline_time_utc=datetime(2024, 6, 15, 20, 0, tzinfo=timezone.utc),
    resource_demand=2.0,         # e.g., 2 accelerator/GPU units
    is_flexible=True             # Allows carbon-aware optimization
)
```
* **Validation Rules:**
  * `duration_half_hours > 0`
  * `resource_demand > 0.0`
  * $T_{\text{arrival}} \le T_{\text{deadline}}$
  * Feasibility check: $T_{\text{arrival}} + (\text{duration} \times 30\text{ min}) \le T_{\text{deadline}}$.

### C. Dispatch Execution
```python
scheduler = WorkloadScheduler(carbon_service=forecast_service)

# 1. FIFO baseline dispatch
fifo_decisions: List[SchedulingDecision] = scheduler.schedule_fifo(jobs)

# 2. Carbonova conservative carbon-aware dispatch
carbonova_decisions: List[SchedulingDecision] = scheduler.schedule_carbonova(
    jobs=jobs,
    history=None                 # Auto-sources history from provider if omitted
)
```

### D. Exact Decision Schema (`SchedulingDecision`)
```json
{
  "job_id": "job_train_001",
  "policy_name": "Carbonova_Conservative",
  "decision": "SCHEDULED",
  "scheduled_start_utc": "2024-06-15T14:00:00Z",
  "scheduled_completion_utc": "2024-06-15T16:00:00Z",
  "predicted_carbon_intensity_gco2_per_kwh": 65.4125,
  "lower_90_gco2_per_kwh": 55.6701,
  "upper_90_gco2_per_kwh": 75.1549,
  "uncertainty_width_gco2_per_kwh": 19.4848,
  "reason": "Dispatched immediately at earliest feasible slot 2024-06-15T14:00:00+00:00 (completes at 2024-06-15T16:00:00+00:00). Next-half-hour forecast is 65.41 gCO2/kWh with nominal 90% conformal interval [55.67, 75.15] gCO2/kWh. Job not deferred because verified multi-step trajectory is unavailable to establish future savings.",
  "data_status": "live"
}
```

---

## 5. Historical Trace Simulation Interface

### A. Python Import Path
```python
from backend.scheduler.simulation import (
    TraceSimulationEngine,
    SyntheticWorkloadGenerator,
    SimulationAssumptions,
    SimulationComparisonResult,
)
```

### B. Usage Example
```python
# 1. Initialize simulation engine using historical 2024 grid trace
sim_engine = TraceSimulationEngine(
    carbon_service=forecast_service,
    assumptions=SimulationAssumptions(
        power_kw_per_resource_unit=0.7,   # 700 Watts / GPU
        interval_duration_hours=0.5       # 30-min settlement intervals
    )
)

# 2. Generate reproducible workload trace
workload_gen = SyntheticWorkloadGenerator(seed=42)
jobs = workload_gen.generate(
    start_time_utc=datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc),
    num_jobs=25
)

# 3. Run simulation comparison
result: SimulationComparisonResult = sim_engine.run_simulation(jobs)

print(f"Total jobs evaluated: {result.total_workload_jobs}")
print(f"FIFO Total Emissions: {result.fifo_summary.total_emissions_gco2:.2f} gCO2")
print(f"Carbonova Total Emissions: {result.carbonova_summary.total_emissions_gco2:.2f} gCO2")
print(f"Relative Emissions Reduction: {result.emissions_reduction_percent:.2f}%")
```

---

## 6. Fair Baseline Comparison Reference

On the identical 17,568 rows of the 2024 out-of-sample evaluation period:

| Model / Baseline | Horizon | MAE ($\text{gCO}_2/\text{kWh}$) | RMSE ($\text{gCO}_2/\text{kWh}$) | $R^2$ | MAPE (%) | Improvement over Baseline |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Previous-Day Persistence ($T-48$)** | 24 hours | 40.7313 | 53.3597 | 0.2050 | 39.63% | Reference (Seasonal Baseline) |
| **Previous-Half-Hour Persistence ($T-1$)** | 30 minutes | 4.9265 | 6.9948 | 0.9863 | 4.66% | Reference (Fair Horizon Baseline) |
| **Random Forest (17 features)** | 30 minutes | **4.1455** | **5.6275** | **0.9912** | **4.22%** | **+15.85% MAE / +19.55% RMSE vs. $T-1$** |

*Note: While Random Forest shows an 89.82% MAE improvement over the 24-hour persistence baseline, the rigorous scientific comparison for a next-half-hour model is against the 30-minute persistence baseline ($T-1$), where it demonstrates a verified 15.85% MAE improvement.*

---

## 7. Verified Data Provenance, Licensing & Attribution

* **Source Authority:** National Energy System Operator (NESO) of Great Britain (formerly National Grid ESO) in partnership with Environmental Defense Fund Europe and the University of Oxford.
* **Official API Service:** NESO Carbon Intensity API (`https://api.carbonintensity.org.uk/intensity/{from}/{to}`).
* **Official API Documentation:** [https://carbon-intensity.github.io/api-definitions/](https://carbon-intensity.github.io/api-definitions/)
* **Official Terms of Use:** [https://github.com/carbon-intensity/terms](https://github.com/carbon-intensity/terms)
* **Verified Licence:** **Creative Commons Attribution 4.0 International (CC BY 4.0)**.
* **Official Attribution Statement:**
  > *"Contains public sector information published by the National Energy System Operator (NESO) and licensed under the Creative Commons Attribution 4.0 International Licence (CC BY 4.0)."*
* **Physical Units:** Grams of carbon dioxide per kilowatt-hour ($\text{gCO}_2/\text{kWh}$).
* **Sampling Interval:** 30-minute settlement periods (48 half-hour slots per day), strictly UTC.
* **Coverage Scope:** Great Britain National Electricity Transmission System (`GB`).
* **Telemetry Anomaly Recovery:** The 5 zero-intensity telemetry dropout periods in early/mid 2023 were cross-referenced against authoritative Elexon BMRS metered generation outturn tables and replaced with verified values. All modifications are documented with provenance flags in [`data/carbon_trace_2023_modeling.csv`](file:///C:/Users/Dhushyanth%20B/OneDrive/Desktop/Carbonova/data/carbon_trace_2023_modeling.csv).

---

## 8. Forecast Horizon Limitations & Multi-Step Forward Roadmap

* **Current Horizon:** One-step-ahead ($T+1$, 30 minutes ahead).
* **Scheduling Behavior:** Feasible workloads are dispatched immediately at the earliest available slot. Because an out-of-sample evaluated multi-step trajectory ($T+2 \dots T+48$) is not yet implemented, `CarbonovaScheduler` conservatively avoids postponing jobs to prevent speculative emissions claims.
* **Proposed Multi-Step Roadmap:**
  1. *Autoregressive Rollout:* Recursively feed model predictions into autoregressive lag slots ($T-1 \gets \hat{y}_T$) to generate multi-hour forward trajectories.
  2. *Horizon-Dependent Uncertainty:* Inflate conformal quantile $\hat{q}(h)$ as horizon $h$ increases to reflect error accumulation.
  3. *Evaluated Target Horizon:* Benchmark multi-step forecast coverage and backfire rates against the 24-hour persistence baseline ($T-48$).

---

## 9. Member 2 & 3 Integration Checklist

- [x] **Member 1 Deliverables Complete:** All 54 unit tests pass (`backend/tests/`).
- [ ] **FastAPI Router Integration (Member 2):** Connect `CarbonForecastService.predict_next_half_hour()` to `backend/app/` to expose endpoints (`POST /api/v1/carbon/forecast`).
- [ ] **Workload API Integration (Member 2):** Connect incoming job requests to `WorkloadJob` and call `WorkloadScheduler.schedule_carbonova()`.
- [ ] **Dashboard Visualization (Member 3):** Bind `CarbonForecastResponse` to chart widgets to display point predictions and shaded 90% uncertainty envelopes ($[\text{lower}_{90}, \text{upper}_{90}]$).
- [ ] **Carbon Time Machine (Member 3):** Connect `TraceSimulationEngine` output metrics (`JobSimulationResult`, `SimulationComparisonResult`) to frontend replay views.
