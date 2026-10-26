# Carbonova — Member 2 Scheduler & Metrics Engine Handoff Contract

**Author:** Member 2 (Core Scheduling Engine & Metrics)
**Target Consumer:** Member 3 (Evaluation, Rolling Backtests & Benchmarking)
**Status:** Formally Verified & Ready for Evaluation Harness Integration
**Test Suite Verification:** 98 passing tests (`pytest -v backend/tests`)

---

## 1. Overview & System Ownership

Member 2 has finalized the core GreenSchedule scheduling engine, multi-policy coordinators, reusable metric calculation module, and carbon data provider adapter.

### Ownership Boundaries
* **Member 2 Owns:**
  - Workload job feasibility evaluation and discrete time-grid snapping.
  - Multi-node / multi-unit resource capacity tracking over half-open intervals $[t_{\text{start}}, t_{\text{finish}})$.
  - The four locked scheduling policies: FIFO, Naive-Green, Carbonova (uncertainty-aware), and Greedy Oracle.
  - Reusable, test-verified metric calculations (emissions, baseline reductions, oracle gaps, backfire rate with `N/A` handling, and interval coverage).
  - The Great Britain NESO real-trace adapter (`NESORealTraceCarbonDataProvider`) and synthetic fallback provider.
* **Member 3 Owns:**
  - Synthetic workload generation and trace window selection across the 2024 NESO evaluation trace.
  - Rolling backtests, random seed control, and Monte Carlo scenario variations.
  - Sensitivity analysis across risk penalties ($\lambda$), minimum-improvement margins, cluster capacities, and orderings (EAF vs. LDSF).
  - Reproducibility scripts, aggregation of means/spread across runs, and reporting tables.
* **Non-Negotiable Rule:** Member 3 must call Member 2's authoritative scheduler and metric functions directly. **Do not create a parallel scheduler or reimplement the emissions formulas.**

---

## 2. Public Importable Modules & Signatures

All core functions and schemas are strictly typed using Pydantic v2 and Python type annotations.

### A. Data Schemas & Configurations
```python
from backend.scheduler.models import (
    Job,                          # Workload job definition
    ClusterConfig,                # Total cluster capacity and time_step_minutes
    SchedulerConfig,              # Policy, ordering, risk_lambda, min_improvement_margin
    PolicyType,                   # Enum: FIFO, NAIVE_GREEN, CARBONOVA, ORACLE
    JobOrdering,                  # Enum: EARLIEST_ARRIVAL_FIRST, LEAST_DEADLINE_SLACK_FIRST
    MarginUnit,                   # Enum: RELATIVE_PERCENTAGE, ABSOLUTE_SCORE
    FeasibilityStatus,            # Enum: SCHEDULED, INITIALLY_INFEASIBLE, CAPACITY_INFEASIBLE
    DecisionRecord,               # Explainable scheduling decision record per job
    PolicyScheduleResult,         # Single policy output with decisions and metrics
    MultiPolicyScheduleResponse,  # Unified cross-policy comparative response
)
```

### B. Carbon Data Providers & Grids
```python
from backend.carbon.interface import (
    CarbonDataProvider,           # Abstract base class
    CarbonForecastPoint,          # Discrete slot forecast point
    CarbonGrid,                   # Regular indexed time-series grid
)
from backend.carbon.neso_provider import NESORealTraceCarbonDataProvider
from backend.carbon.synthetic import SyntheticCarbonDataProvider
from backend.app.storage import (
    set_carbon_provider,          # Register custom or real provider
    get_carbon_provider,          # Retrieve active provider
    reset_carbon_provider,        # Revert to default synthetic provider
)
```

### C. Scheduling Engine & Policy Coordinators
```python
from backend.scheduler.engine import SchedulingEngine

# 1. Execute a single policy on a job batch
result: PolicyScheduleResult = SchedulingEngine.run_policy(
    jobs: Sequence[Job],
    carbon_grid: CarbonGrid,
    config: Optional[SchedulerConfig] = None,
)

# 2. Execute all four policies for comparative benchmarking
response: MultiPolicyScheduleResponse = SchedulingEngine.run_all_policies(
    jobs: Sequence[Job],
    carbon_grid: CarbonGrid,
    config: Optional[SchedulerConfig] = None,
)

# 3. Sensitivity helper: Compare EAF vs LDSF orderings under identical conditions
ordering_comparison: Dict[str, Any] = SchedulingEngine.compare_orderings(
    jobs: Sequence[Job],
    carbon_grid: CarbonGrid,
    policy: PolicyType = PolicyType.CARBONOVA,
    risk_lambda: float = 0.5,
    min_improvement_margin: float = 0.05,
    margin_unit: MarginUnit = MarginUnit.RELATIVE_PERCENTAGE,
    cluster_config: Optional[ClusterConfig] = None,
)
```

### D. Reusable Evaluation Metrics
```python
from backend.scheduler.metrics import (
    compute_schedule_metrics,     # Complete metrics suite with baseline & oracle gaps
    calculate_job_emissions,      # Per-job gCO2 calculation: energy_kwh * avg_intensity
    compute_forecast_interval_coverage, # Empirical coverage across confidence intervals
)
```

---

## 3. End-to-End Integration Walkthrough for Member 3

Here is a minimal, complete, and runnable example demonstrating how Member 3 should execute evaluation runs against real 2024 Great Britain NESO data:

```python
from datetime import datetime, timedelta, timezone
from backend.carbon.neso_provider import NESORealTraceCarbonDataProvider
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.models import (
    ClusterConfig,
    FeasibilityStatus,
    Job,
    JobOrdering,
    MarginUnit,
    SchedulerConfig,
)

# 1. Initialize real NESO data provider (2024 Great Britain grid outturn + RF forecasts)
carbon_provider = NESORealTraceCarbonDataProvider()

# 2. Define evaluation time window
eval_start = datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
eval_end = datetime(2024, 6, 1, 18, 0, tzinfo=timezone.utc)

# 3. Obtain CarbonGrid (supports 30m native or 60m aggregated slots)
grid = carbon_provider.get_carbon_grid(
    start_time=eval_start,
    end_time=eval_end,
    time_step_minutes=60,
)

# 4. Define workload batch
jobs = [
    Job(
        job_id="job-01",
        job_type="training",
        arrival_time=eval_start,
        deadline=eval_start + timedelta(hours=4),
        duration_minutes=60,
        energy_kwh=10.0,
        deferrable=False,               # Non-deferrable -> runs immediately at earliest slot
        resource_requirement=1.0,
    ),
    Job(
        job_id="job-02",
        job_type="batch_inference",
        arrival_time=eval_start,
        deadline=eval_start + timedelta(hours=6),
        duration_minutes=60,
        energy_kwh=15.0,
        deferrable=True,                # Deferrable -> eligible for carbon optimization
        resource_requirement=2.0,
    ),
    Job(
        job_id="job-03",
        job_type="fine_tuning",
        arrival_time=eval_start + timedelta(minutes=30),
        deadline=eval_start + timedelta(hours=8),
        duration_minutes=120,
        energy_kwh=25.0,
        deferrable=True,
        resource_requirement=1.0,
    ),
]

# 5. Configure scheduler run
config = SchedulerConfig(
    job_ordering=JobOrdering.LEAST_DEADLINE_SLACK_FIRST,
    risk_lambda=0.5,                    # Uncertainty multiplier
    min_improvement_margin=0.05,        # 5% relative risk reduction threshold
    margin_unit=MarginUnit.RELATIVE_PERCENTAGE,
    cluster=ClusterConfig(
        total_capacity=4.0,             # 4 GPU cluster capacity
        time_step_minutes=60,
    ),
)

# 6. Execute all four policies simultaneously
response = SchedulingEngine.run_all_policies(jobs, grid, config)

# 7. Extract comparative metrics
fifo_res = response.results["fifo"]
naive_res = response.results["naive_green"]
carb_res = response.results["carbonova"]
oracle_res = response.results["oracle"]

print(f"FIFO Total Realized Emissions:      {fifo_res.metrics['total_realized_emissions_gco2']:.2f} gCO2")
print(f"Carbonova Total Realized Emissions: {carb_res.metrics['total_realized_emissions_gco2']:.2f} gCO2")
print(f"Oracle Benchmark Emissions:         {oracle_res.metrics['total_realized_emissions_gco2']:.2f} gCO2")

summary = response.comparative_summary
print(f"Carbonova Reduction vs FIFO:        {summary['emissions_reduction_vs_fifo_pct']['carbonova']}%")
print(f"Carbonova Gap to Oracle:            {summary['oracle_gap_pct']['carbonova']}%")
print(f"Backfire Rate:                      {summary['backfire_rate_display']['carbonova']}")
```

---

## 4. Key Metric Semantics & Methodological Rules

### A. Forecast Isolation
* **Online Policies (`fifo`, `naive_green`, `carbonova`):** Evaluate decisions strictly using `CarbonForecastPoint.predicted_carbon_intensity` and `slot_specific_uncertainty`. They never look at `realized_carbon_intensity`.
* **Greedy Oracle (`oracle`):** Evaluates decisions using `CarbonForecastPoint.realized_carbon_intensity` to find the empirical lowest-carbon slot within common feasibility and ordering constraints.
* **Post-Hoc Scoring:** Realized emissions across all policies are calculated using `realized_carbon_intensity` from the verified outturn trace.

### B. Backfire Detection Rule
* A scheduled flexible job "backfires" if it was delayed from its earliest feasible slot ($t_{\text{scheduled}} > t_{\text{earliest}}$) and its realized emissions exceed the counterfactual emissions it would have incurred if executed at $t_{\text{earliest}}$.
* **Mathematical Safety:** If `delayed_jobs_count == 0`, `backfire_rate_pct` returns `None` and displays as `"N/A (No delayed jobs)"` rather than a misleading `0.0%`.

### C. Deadline Success Rate
* Calculated among jobs that were feasible at submission:
  $$\text{Deadline Success Rate} = \frac{\text{Scheduled Jobs Finishing} \le \text{Deadline}}{\text{Total Submitted} - \text{Initially Infeasible Jobs}} \times 100\%$$
* If no feasible jobs are submitted, the rate returns `None` and displays as `"N/A (No feasible jobs submitted)"`.

### D. Counterfactual Disclosure
* As documented in `COUNTERFACTUAL_DISCLOSURE`:
  > *"Per-job counterfactual emissions evaluate each job independently at its earliest feasible slot and do not represent a globally concurrent schedule under system-wide resource contention."*

### E. Uncertainty Metrics and Aggregation Interpretation
* **Native 30-Minute Slots:** Feature formally calibrated split-conformal prediction intervals ($\alpha=0.10, 90\%$ nominal coverage), achieving $92.58\%$ empirical coverage across the 2024 test trace under diurnal regimes.
* **Aggregated 60-Minute Slots:** Hourly uncertainty is derived as the arithmetic mean of constituent settlement periods $\overline{\sigma} = (\sigma_0 + \sigma_1)/2.0$. It represents a **conservative heuristic scheduling-risk score** that achieves $96.61\%$ empirical coverage on 2024 hourly averages (super-coverage due to variance reduction). It must not be cited as a standalone 90% conformal interval for hourly averages.

---

## 5. Member 3 Handoff Checklist

### A. Completed and Verified by Member 2
- [x] Four locked policies implemented: FIFO, Naive-Green, Carbonova, and Greedy Oracle.
- [x] Two job-ordering strategies implemented: EAF and LDSF with deterministic job_id tie-breaking.
- [x] Full discrete-time resource capacity tracker with half-open intervals $[t, t+\text{duration})$.
- [x] Complete explainability records generated for every job (`DecisionRecord` with step-by-step reasoning).
- [x] Reusable metric computation module (`compute_schedule_metrics`) with exact emissions formulas.
- [x] Real Great Britain NESO 2024 trace adapter (`NESORealTraceCarbonDataProvider`) supporting native 30m and aggregated 60m slots.
- [x] Dynamic carbon provider injection hook (`set_carbon_provider`, `get_carbon_provider`, `reset_carbon_provider`).
- [x] Safe synthetic development fallback preserved.
- [x] 98 automated tests passing without regression (`backend/tests/`).

### B. Remaining Evaluation Tasks Owned by Member 3
- [ ] Implement synthetic and trace-derived workload generators for rolling evaluation windows.
- [ ] Run rolling backtests across the entire 2024 NESO trace (e.g., across seasons: Winter peak, Summer solar trough, Spring wind).
- [ ] Perform sensitivity analysis over $\lambda \in [0.0, 2.0]$ and minimum improvement margin $m \in [0.0, 0.20]$.
- [ ] Evaluate flat-carbon scenarios (proves Carbonova defaults to earliest slot without backfiring).
- [ ] Evaluate noisy-forecast scenarios (proves uncertainty penalty mitigates bad delays).
- [ ] Aggregate mean emissions reduction, oracle gaps, and backfire rates across seeds with statistical confidence bounds.
- [ ] Generate figures and markdown tables for the final evaluation report.

### C. Files Member 3 Must NOT Replace
* `backend/scheduler/engine.py` (authoritative engine)
* `backend/scheduler/policies.py` (authoritative policy rules)
* `backend/scheduler/capacity.py` (authoritative cluster capacity tracker)
* `backend/scheduler/models.py` (authoritative data contracts)
* `backend/scheduler/metrics.py` (authoritative evaluation metrics)
* `backend/carbon/interface.py` & `neso_provider.py` (authoritative carbon provider contracts)
