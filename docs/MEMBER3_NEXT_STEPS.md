# Carbonova — Member 3 Evaluation, Backtesting & Benchmarking Guide

**Target Audience:** Member 3 (Evaluation Specialist)
**Author:** Member 2 (Scheduling Engine & Metrics Lead)
**Specification Reference:** `Carbonova_Finalised_Locked_Project_Report.docx`
**Prerequisites:** All 98 backend tests passing (`pytest -v backend/tests`)

---

## 1. Ownership Contract & Guiding Rules

Member 2 has delivered a fully verified scheduling engine, carbon provider adapter, and metrics module. As Member 3, your responsibility is to design the rigorous experimental evaluation, rolling backtests, and sensitivity analyses.

### Sacred Architectural Rules
1. **Never Re-implement Scheduling Logic:** Always call `SchedulingEngine.run_policy()` or `SchedulingEngine.run_all_policies()`. Do not write custom dispatch loops.
2. **Never Re-implement Metrics:** Always use the metrics returned in `PolicyScheduleResult.metrics` or call `backend.scheduler.metrics.compute_schedule_metrics()`. This guarantees identical mathematical definitions across the team.
3. **Respect Forecast Isolation:** Online policies (`fifo`, `naive_green`, `carbonova`) must only consume predicted carbon intensity and uncertainty. Realized emissions are scored strictly post-hoc.
4. **Reproducibility First:** Every experiment, synthetic workload, and backtest run must accept an explicit `random_seed` and be fully reproducible.

---

## 2. Recommended Directory Layout

Member 3 should establish the following layout in the repository root:

```text
Carbonova/
├── evaluation/
│   ├── __init__.py
│   ├── workload_generator.py      # Synthetic & trace-driven job generators
│   ├── rolling_backtest.py        # 2024 rolling window backtest runner
│   ├── sensitivity_analysis.py    # Parameter sweep scripts (lambda, margin, capacity)
│   └── scenarios.py               # Volatile, flat, high-uncertainty scenarios
├── scripts/
│   ├── run_all_evaluations.py     # Master execution script
│   └── generate_report_tables.py  # Markdown / LaTeX table exporter
└── results/
    ├── figures/                   # Pareto curves, boxplots, timeseries
    └── tables/                    # CSVs and JSONs of empirical metrics
```

---

## 3. Workload Generation Specifications

The locked project report specifies realistic AI cluster workloads across three primary job archetypes:

| Job Type | Resource Req (GPUs) | Duration | Deferrable | Arrival Pattern | Energy (kWh) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LLM Fine-Tuning** | 2.0 – 4.0 | 2 – 6 hours | Yes (Slack: 4 – 12 hrs) | Poisson / Clustered | 20.0 – 80.0 |
| **Batch Inference** | 1.0 – 2.0 | 30 – 90 mins | Yes (Slack: 2 – 6 hrs) | Periodic / Batch bursts | 5.0 – 15.0 |
| **Interactive / Critical**| 1.0 | 30 – 60 mins | **No** (Must run ASAP) | Random uniform | 2.0 – 8.0 |

### Starter Generator Snippet

```python
import random
from datetime import datetime, timedelta, timezone
from typing import List
from backend.scheduler.models import Job

def generate_synthetic_workload(
    window_start: datetime,
    num_jobs: int = 25,
    cluster_capacity: float = 4.0,
    seed: int = 42,
) -> List[Job]:
    random.seed(seed)
    jobs = []

    for i in range(num_jobs):
        arrival_offset_min = random.choice([0, 30, 60, 120, 180, 240, 360])
        arrival = window_start + timedelta(minutes=arrival_offset_min)

        job_type = random.choices(["training", "batch_inference", "critical"], weights=[0.4, 0.4, 0.2])[0]

        if job_type == "training":
            duration = random.choice([60, 120, 180])
            slack_hours = random.choice([4, 6, 8])
            deferrable = True
            req = random.choice([1.0, 2.0])
            energy = duration / 60.0 * req * 4.0
        elif job_type == "batch_inference":
            duration = random.choice([30, 60])
            slack_hours = random.choice([2, 4])
            deferrable = True
            req = 1.0
            energy = duration / 60.0 * req * 2.5
        else: # critical
            duration = random.choice([30, 60])
            slack_hours = 0
            deferrable = False
            req = 1.0
            energy = duration / 60.0 * req * 2.0

        deadline = arrival + timedelta(minutes=duration) + timedelta(hours=slack_hours)
        jobs.append(Job(
            job_id=f"job-{seed}-{i:03d}",
            job_type=job_type,
            arrival_time=arrival,
            deadline=deadline,
            duration_minutes=duration,
            energy_kwh=energy,
            deferrable=deferrable,
            resource_requirement=req,
        ))
    return jobs
```

---

## 4. Required Experimental Scenarios

### Scenario A: High-Volatility Grid Conditions (Summer / Autumn)
- **Trace Window:** July 15 – July 22, 2024 or September 10 – September 17, 2024.
- **Hypothesis:** Significant diurnal solar swings allow Naive-Green and Carbonova to achieve $>15\%$ emissions reductions over FIFO.

### Scenario B: Flat-Carbon Grid Baseline (Stress Test)
- **Trace Window:** Select consecutive days with steady baseload (low wind/solar variation) or create an artificial flat grid.
- **Hypothesis:** In the absence of carbon differentials, Carbonova must not defer jobs unnecessarily. The backfire rate should remain $0.0\%$, and mean deferral time should equal FIFO.

### Scenario C: High Forecast Uncertainty / Storm Fronts
- **Trace Window:** Winter storms (January 15 – January 22, 2024).
- **Hypothesis:** Naive-Green suffers a high backfire rate ($>10\%$) due to large forecast errors during volatile ramp periods. Carbonova's risk penalty ($\lambda \cdot \sigma$) hedges against false clean valleys, keeping backfire rate near $0\%$.

### Scenario D: Multi-Capacity Contention Sweep
- **Capacities:** Total cluster capacity $C \in \{2.0, 4.0, 8.0, 16.0\}$.
- **Hypothesis:** Under tight capacity ($C=2.0$), queuing delays interact with carbon valley alignment. LDSF ordering preserves deadline feasibility significantly better than EAF.

---

## 5. Hyperparameter Sensitivity Sweeps

Member 3 must execute systematic parametric grid searches over:

1. **Risk Uncertainty Penalty ($\lambda$):**
   - Values: $\lambda \in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]$.
   - Metric to plot: Pareto frontier of *Emissions Reduction vs. FIFO (%)* against *Backfire Rate (%)*.
   - Expected result: As $\lambda$ increases, backfires vanish to $0$, with a slight conservative trade-off in emissions savings.

2. **Minimum Improvement Margin ($m$):**
   - Relative Margin: $m \in [0.0, 0.02, 0.05, 0.10, 0.15, 0.20]$ ($0\%$ to $20\%$).
   - Metric to plot: Mean Job Deferral Time (minutes) vs. Emissions Savings.
   - Expected result: Non-zero margins prevent marginal deferrals (e.g., delaying 4 hours for a $0.5\%$ gain).

3. **Job Ordering Strategies:**
   - Compare `JobOrdering.EARLIEST_ARRIVAL_FIRST` vs `JobOrdering.LEAST_DEADLINE_SLACK_FIRST`.
   - Use helper: `SchedulingEngine.compare_orderings()`.
   - Metric to evaluate: Number of capacity-infeasible jobs and deadline violations under peak contention.

---

## 6. Standardized Evaluation Output Table Template

Member 3's final report script should export tables in this exact format:

| Policy | Realized Emissions (kgCO2) | Reduction vs. FIFO (%) | Oracle Gap (%) | Backfire Rate (%) | Deadline Success (%) | Mean Delay (min) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FIFO (Baseline)** | 142.80 | — | 18.2% | N/A | 100.0% | 0.0 |
| **Naive-Green** | 124.30 | 12.95% | 4.8% | 14.2% | 98.4% | 114.5 |
| **Carbonova ($\lambda=0.5, m=0.05$)** | 121.50 | 14.92% | 2.5% | 1.8% | 100.0% | 96.2 |
| **Greedy Oracle (Benchmark)**| 118.40 | 17.08% | 0.0% | 0.0% | 100.0% | 128.0 |

---

## 7. Master Backtesting Skeleton for Member 3

```python
"""
Starter script: evaluation/rolling_backtest.py
Run with: python -m evaluation.rolling_backtest
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure backend is accessible
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.carbon.neso_provider import NESORealTraceCarbonDataProvider
from backend.scheduler.engine import SchedulingEngine
from backend.scheduler.models import ClusterConfig, JobOrdering, MarginUnit, SchedulerConfig
from evaluation.workload_generator import generate_synthetic_workload

def run_season_backtest(start_date: datetime, num_days: int = 7, seed: int = 42):
    provider = NESORealTraceCarbonDataProvider(uncertainty_mode="diurnal")

    config = SchedulerConfig(
        job_ordering=JobOrdering.LEAST_DEADLINE_SLACK_FIRST,
        risk_lambda=0.5,
        min_improvement_margin=0.05,
        margin_unit=MarginUnit.RELATIVE_PERCENTAGE,
        cluster=ClusterConfig(total_capacity=4.0, time_step_minutes=60),
    )

    daily_results = []
    for day in range(num_days):
        window_start = start_date + timedelta(days=day)
        window_end = window_start + timedelta(days=1)

        grid = provider.get_carbon_grid(window_start, window_end, time_step_minutes=60)
        jobs = generate_synthetic_workload(window_start, num_jobs=20, seed=seed + day)

        response = SchedulingEngine.run_all_policies(jobs, grid, config)
        daily_results.append(response.comparative_summary)
        print(f"Day {day+1} completed: Carbonova reduction = {response.comparative_summary['emissions_reduction_vs_fifo_pct']['carbonova']}%")

    return daily_results

if __name__ == "__main__":
    summer_start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    print("Launching Member 3 Rolling Summer Backtest...")
    run_season_backtest(summer_start, num_days=7)
```
