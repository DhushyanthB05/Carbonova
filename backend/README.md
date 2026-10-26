# Carbonova Core Scheduling Engine (Member 2 Responsibility)

Welcome to the Carbonova Core Scheduling Engine backend documentation. This document details the mathematical specifications, time semantics, scheduling policies, reusable metrics, API contracts, and integration interfaces for team members.

---

## 1. Architectural Architecture

```text
backend/
├── app/
│   ├── main.py             # FastAPI entrypoint with CORS & routers
│   ├── storage.py          # Session job & run history store
│   └── routers/
│       ├── health.py       # GET /api/health
│       ├── carbon.py       # GET /api/carbon
│       ├── jobs.py         # POST & GET /api/jobs
│       └── schedule.py     # POST /api/schedule/run & GET /api/schedule/results
├── carbon/
│   ├── interface.py        # Typed CarbonDataProvider & CarbonForecastPoint (Contract for Member 1)
│   └── synthetic.py        # Deterministic SYNTHETIC test fixtures
├── scheduler/
│   ├── models.py           # Pydantic schemas (Job, DecisionRecord, SchedulerConfig, etc.)
│   ├── time_grid.py        # Discrete slot alignment & half-open [start, finish) intervals
│   ├── capacity.py         # Multi-slot capacity tracker & reservation enforcement
│   ├── ordering.py         # Deterministic Earliest-Arrival (EAF) & Least-Deadline-Slack (LDSF)
│   ├── policies.py         # FIFO, Naive-Green, Carbonova Uncertainty-Aware, Oracle
│   ├── metrics.py          # Reusable evaluation metrics for Member 3
│   └── engine.py           # Unified SchedulingEngine orchestrating multi-policy comparisons
└── tests/                  # 32 comprehensive pytest unit & integration tests
```

---

## 2. Mathematical Formulations & Semantics

### 2.1 Time Semantics and Discretization
- **Timezone**: All internal operations, comparisons, and timestamps are strictly timezone-aware **UTC**.
- **Execution Interval**: Modeled as half-open intervals $[t_{\text{start}}, t_{\text{finish}})$. If Job A finishes at 11:00 and Job B starts at 11:00, they do **not** overlap.
- **Slot Alignment**:
  - Let $\Delta t$ be `time_step_minutes` (e.g. 60 min).
  - Duration is converted to discrete slots: $K = \lceil \text{duration\_minutes} / \Delta t \rceil$.
  - Earliest slot boundary for a job arriving at $t_{\text{arr}}$ is $\text{align\_to\_next\_slot}(t_{\text{arr}}, \Delta t)$.

### 2.2 Feasibility Conditions
A candidate start slot $t$ is feasible for job $j$ if and only if:
1. $t \ge \text{align\_to\_next\_slot}(j.\text{arrival\_time}, \Delta t)$
2. $t + K \cdot \Delta t \le j.\text{deadline}$
3. All slots in $[t, t + K \cdot \Delta t)$ exist in the carbon grid.
4. For every slot $\tau \in [t, t + K \cdot \Delta t)$, the cluster capacity satisfies:
   $$\text{used\_capacity}(\tau) + j.\text{resource\_requirement} \le \text{total\_capacity}$$

Jobs whose duration exceeds $(j.\text{deadline} - j.\text{arrival\_time})$ or whose resource requirement exceeds total cluster capacity are flagged as **`INITIALLY_INFEASIBLE`** and never scheduled.

### 2.3 Policy Definitions
1. **FIFO / Earliest-Feasible**:
   - Dispatches jobs using the configured job order.
   - Selects the earliest feasible candidate start slot $t_{\text{earliest}}$.

2. **Naive-Green**:
   - Forecast-greedy policy.
   - Average predicted carbon intensity over $K$ slots:
     $$\bar{I}_{\text{pred}}(t) = \frac{1}{K} \sum_{k=0}^{K-1} I_{\text{pred}}(t + k \cdot \Delta t)$$
   - Selects $t^* = \arg\min_{t \in T_{\text{feasible}}} \bar{I}_{\text{pred}}(t)$.
   - Tie-breaker: earliest timestamp.

3. **Carbonova Uncertainty-Aware Policy**:
   - Calculates slot risk score with non-negative parameter $\lambda_{\text{risk}} \ge 0$:
     $$\text{risk\_score}(t) = \bar{I}_{\text{pred}}(t) + \lambda_{\text{risk}} \cdot \bar{\sigma}(t)$$
     where $\bar{\sigma}(t)$ is the average slot-specific uncertainty over the job's execution duration.
   - Let $t^*$ minimize $\text{risk\_score}(t)$, and $t_{\text{earliest}}$ be the earliest feasible slot.
   - **Configurable Margin Semantics (`MarginUnit`)**:
     - `relative_percentage` (default):
       $$\Delta_{\text{imp}} = \frac{\text{risk\_score}(t_{\text{earliest}}) - \text{risk\_score}(t^*)}{\text{risk\_score}(t_{\text{earliest}})} \ge \text{min\_improvement\_margin}$$
       (e.g., $0.05 = 5\%$ relative risk reduction).
     - `absolute_score`:
       $$\Delta_{\text{score}} = \text{risk\_score}(t_{\text{earliest}}) - \text{risk\_score}(t^*) \ge \text{min\_improvement\_margin}$$
       (e.g., $15.0\text{ gCO}_2\text{eq}/\text{kWh}$ absolute risk reduction).
   - **Decision Rule**:
     - If $j.\text{deferrable} == \text{False}$: run immediately at $t_{\text{earliest}}$.
     - Else if improvement meets the configured margin threshold: delay and execute at $t^*$.
     - Else: execute at $t_{\text{earliest}}$ (delay rejected due to insufficient risk improvement).
   - **Finish Time Semantics**: A job starting at $t$ finishes at $t + j.\text{duration\_timedelta}$ (e.g. 45 min duration finishes at $t + 45\text{m}$, while reserving 1 discrete slot for cluster capacity).

4. **Perfect-Forecast Greedy Oracle**:
   - Uses realized carbon observations $\bar{R}(t) = \frac{1}{K} \sum_{k=0}^{K-1} R(t + k \cdot \Delta t)$.
   - Selects $t^* = \arg\min_{t \in T_{\text{feasible}}} \bar{R}(t)$.
   - **Strict Forecast Isolation**: Online policies (FIFO, Naive-Green, Carbonova) call `compute_forecast_interval_stats` and cannot access realized carbon intensity. Only Oracle calls `compute_realized_interval_stats`.

---

## 3. Reusable Evaluation Metrics (Member 3 Interface)

All metrics are computed via `backend.scheduler.metrics.compute_schedule_metrics`:

| Metric | Definition | Edge Cases & Rules |
| :--- | :--- | :--- |
| **Total Realized Emissions** | $E_{\text{total}} = \sum_{j \in \text{Scheduled}} j.\text{energy\_kwh} \cdot \bar{R}(j)$ | Expressed in $\text{gCO}_2\text{eq}$. |
| **Emissions Reduction vs Baseline** | $\frac{E_{\text{baseline}} - E_{\text{policy}}}{E_{\text{baseline}}} \times 100\%$ | Typically evaluated against FIFO baseline. |
| **Deadline Success Rate** | $\frac{\text{Scheduled jobs finishing } \le \text{deadline}}{\text{Initially feasible submitted jobs}} \times 100\%$ | Excludes initially infeasible jobs from denominator. |
| **Backfire Rate** | $\frac{\text{Delayed jobs where } E_{\text{realized}} > E_{\text{earliest\_counterfactual}}}{\text{Total delayed jobs}} \times 100\%$ | **CRITICAL**: If 0 jobs are delayed, returns `None` (`"N/A"`), **NOT** `0.0%`. |
| **Oracle Gap** | $\frac{E_{\text{policy}} - E_{\text{oracle}}}{E_{\text{oracle}}} \times 100\%$ | Benchmark comparison. |
| **Waiting Time Statistics** | Mean, median, min, max of $(t_{\text{start}} - t_{\text{arrival}})$ | Minutes. |
| **Forecast Interval Coverage** | $\%$ of realized values falling within $[CI_{\text{lower}}, CI_{\text{upper}}]$ | Evaluated via `compute_forecast_interval_coverage`. |

---

## 4. Integration Contracts for Teammates

### Member 1 (Carbon Forecast Engine)
Implement `backend.carbon.interface.CarbonDataProvider`:
```python
from datetime import datetime
from backend.carbon.interface import CarbonDataProvider, CarbonGrid, CarbonForecastPoint

class LiveCarbonDataProvider(CarbonDataProvider):
    def get_carbon_grid(self, start_time: datetime, end_time: datetime, time_step_minutes: int = 60) -> CarbonGrid:
        # 1. Fetch live or forecast carbon data (ElectricityMaps / National Grid ESO)
        # 2. Populate CarbonForecastPoint instances (with predicted, slot_specific_uncertainty, CI bounds)
        # 3. Return CarbonGrid(points, time_step_minutes=time_step_minutes)
        ...
```

### Member 3 (Evaluation Runner & Experiment Orchestrator)
Call the `SchedulingEngine` directly in Python:
```python
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.models import Job, SchedulerConfig, PolicyType, JobOrdering

# 1. Run all policies with comparative baseline & oracle analysis
multi_response = SchedulingEngine.run_all_policies(jobs=job_trace, carbon_grid=grid)
print(multi_response.comparative_summary)

# 2. Compare Earliest-Arrival-First vs Least-Deadline-Slack-First
ordering_comparison = SchedulingEngine.compare_orderings(
    jobs=job_trace,
    carbon_grid=grid,
    policy=PolicyType.CARBONOVA,
    risk_lambda=0.5,
    min_improvement_margin=0.05,
)
```

### Member 4 (Frontend & Visualization)
Endpoints exposed on FastAPI (`http://localhost:8000`):
- `GET /api/health`: Service health and version check.
- `GET /api/carbon?start_time=...&end_time=...`: Carbon intensity and uncertainty time series for charts.
- `POST /api/jobs`: Submit workload jobs with instant initial feasibility feedback.
- `POST /api/schedule/run`: Trigger scheduling run across FIFO, Naive-Green, Carbonova, and Oracle.
- `GET /api/schedule/results`: Fetch recent run history.

---

## 5. Setup and Verification

### Virtual Environment & Dependencies
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### Running Test Suite
```powershell
pytest backend/tests -v
```

### Starting Backend Server
```powershell
uvicorn backend.app.main:app --reload --port 8000
```
API Documentation will be available at `http://127.0.0.1:8000/docs`.
