# Carbonova

**Smarter AI. Cleaner Computing.**

Carbonova is an explainable, carbon-aware AI workload scheduling platform that schedules flexible AI workloads during lower-carbon periods while respecting deadlines, resource capacity, and forecast uncertainty.

## Core Features

- Carbon-aware scheduling for flexible AI workloads.
- Feasibility checks for job arrivals, durations, deadlines, and resource capacity.
- Comparison of FIFO, naive-green, Carbonova, and perfect-forecast greedy policies.
- Uncertainty-aware scheduling with a configurable minimum-improvement margin.
- Evaluation of emissions, waiting time, deadline success, and backfire rate.
- Reproducible experiments and automated tests.
- Dashboard with a Carbon Time Machine visualization.

## Technology Stack

- **Backend:** Python, FastAPI, Pydantic
- **Data & Evaluation:** Pandas, NumPy
- **Testing:** pytest
- **Frontend:** React, Vite, Tailwind CSS, Recharts
- **Storage:** CSV and SQLite where needed

## Project Structure

```text
Carbonova/
├── backend/
│   ├── app/
│   ├── carbon/
│   ├── scheduler/
│   ├── evaluation/
│   └── tests/
├── frontend/
├── data/
│   ├── carbon_trace.csv
│   ├── scenarios/
│   └── results/
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

## Data Transparency

Carbon intensity data, forecasts, and workload energy estimates will be documented. Synthetic or recorded traces will never be presented as live grid data.

## Development Status

- Core scheduler models, feasibility engine, baselines, and uncertainty-aware heuristic implemented.
- Reproducible job scenario generator, 4-policy benchmark runner, and sensitivity experiments implemented.
- Automated test suite with 17 passing tests established.

## Getting Started

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Automated Pytest Suite

```bash
pytest -v
```

### 3. Run Reproducible Evaluation Benchmarks & Sensitivity Experiments

```bash
python backend/evaluation/run_experiments.py
```

Generated reproducible scenarios and comparison outputs will be stored in:
- `data/scenarios/` (Standard 24h, Contention, Tight Deadlines, Urgent Control)
- `data/results/` (Policy comparison report, frontend dashboard payload, sensitivity sweeps)

## Project Goal

Reduce avoidable AI-computing emissions through explainable, uncertainty-aware workload scheduling and reproducible evaluation.
