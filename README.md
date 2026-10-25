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
│   └── tests/
├── frontend/
├── data/
├── .gitignore
└── README.md
```

## Data Transparency

Carbon intensity data, forecasts, and workload energy estimates will be documented. Synthetic or recorded traces will never be presented as live grid data.

## Development Status

Initial project structure established. Backend APIs, scheduling algorithms, evaluation pipeline, tests, and dashboard will be developed incrementally.

## Getting Started

Setup and execution instructions will be added as the implementation progresses.

## Project Goal

Reduce avoidable AI-computing emissions through explainable, uncertainty-aware workload scheduling and reproducible evaluation.
