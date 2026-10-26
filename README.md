# Carbonova

> **Smarter AI. Cleaner Computing.**
> An explainable, uncertainty-aware carbon-intelligent workload scheduler and inference router for sustainable AI infrastructure.

---

## 1. Executive Summary & Problem Statement

As artificial intelligence workloads grow exponentially, data center electricity consumption is placing unprecedented strain on regional power grids. During peak demand hours, grid operators fire up carbon-intensive fossil peaker plants (emitting >450 gCO₂e/kWh), whereas during midday hours, abundant solar and wind power is frequently curtailed (wasted at near-zero marginal emissions).

However, **naive carbon-aware scheduling frequently backfires**:
- Grid carbon forecasts carry substantial uncertainty due to cloud cover, wind variability, and transmission bottlenecks.
- Schedulers that naively wait for forecasted troughs often shift jobs directly into unexpected fossil peaks, resulting in **higher realized emissions than immediate dispatch** (the *carbon backfire* phenomenon).
- Naive algorithms stack flexible jobs into the same hour, exceeding GPU cluster capacity or violating mission-critical completion deadlines (SLAs).

**Carbonova** solves these challenges by combining:
1. **Uncertainty-Aware Heuristic Scoring**: Evaluates candidate execution windows using risk-penalized upper bounds ($\mu + \lambda\sigma$) to systematically avoid backfire.
2. **Hard SLA & Capacity Bounds**: Guarantees zero deadline violations while respecting physical hardware constraints (GPU nodes).
3. **Multi-Policy Empirical Benchmarking**: Evaluates scheduling resilience across sensitivity scenarios, including flat carbon curves (verifying zero manufactured savings) and high-noise regimes.
4. **Data Provenance Transparency**: Every metric, trace point, and score is tagged with explicit data lineage badges (Recorded, Live, Synthetic, Measured, Tool-Estimated, Assumption-Based).
5. **GreenGate AI Semantic Router**: Cascades incoming LLM queries between lightweight Tier-1 (7B) and deep Tier-2 (70B) models based on prompt complexity and real-time grid intensity.

---

## 2. Platform Architecture

```
                          ┌───────────────────────────────────┐
                          │         Carbonova UI/UX           │
                          │   (React 19 + Vite + Tailwind)    │
                          └─────────────────┬─────────────────┘
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    ▼                                               ▼
     ┌─────────────────────────────┐               ┌─────────────────────────────┐
     │   FastAPI Backend (Proxy)   │               │   In-Browser Pure TS        │
     │   (Optional / Live Grid)    │               │   Simulation & Solver Engine│
     │   • GET /api/health         │  (Fallback)   │   • solveJobsSchedule()     │
     │   • GET /api/carbon         ├──────────────►│   • runPolicyBenchmark()    │
     │   • POST /api/schedule/run  │               │   • runGreenGateInference() │
     │   • POST /api/jobs          │               │   • Deterministic Trace Replay│
     └─────────────────────────────┘               └─────────────────────────────┘
```

The frontend operates in two seamless modes:
1. **Live API Mode**: When the FastAPI backend (`VITE_API_BASE_URL`) is connected, it fetches live/recorded ISO grid feeds and delegates scheduling tasks.
2. **Self-Contained Simulation Mode**: When offline, the dashboard displays an honest `Demo Mode (Simulation)` provenance badge and executes identical mathematical algorithms directly in pure TypeScript, enabling instant, zero-dependency testing, hackathon demos, and academic evaluation.

---

## 3. Platform Modules & Pages

### 1. Carbon Intelligence Overview (`/`)
- Real-time marginal carbon intensity time-series chart with forecast mean and confidence bounds ($1\sigma$).
- 4 primary metric cards: **Total Realized Emissions (kgCO₂e)**, **Avoided Emissions (%)**, **Average Waiting Time (min)**, and **SLA Attainment (%)**.
- Dispatch window indicator highlighting optimal upcoming low-carbon execution slots.
- Live data provenance pills and quick navigation links.

### 2. Workload Intake & Submission (`/submit-job`)
- Interactive job intake form supporting model training, LoRA fine-tuning, and batch inference.
- Real-time pre-flight validation: verifies duration feasibility against arrival and deadline ($d_{\text{arrival}} + \Delta t \le d_{\text{deadline}}$) and checks GPU availability.
- Carbon impact preview: dynamically projects immediate vs. optimal scheduled emissions before submission.
- One-click synthetic workload generators for rapid demo testing.

### 3. Schedule Results & Dispatch Gantt (`/schedule-results`)
- Interactive Gantt timeline displaying arrival boundaries, scheduled windows, and hard deadlines.
- Grid carbon heat strip mapping historical and forecasted marginal carbon intensity.
- Hardware capacity utilization strip tracking GPU concurrency against cluster limits.
- Deep job inspector drawer detailing solver rationale, risk scores, and energy breakdowns.
- One-click schedule export to **JSON** or **CSV**.
- Embedded solver parameter controls allowing live recalculation.

### 4. Policy Comparison & Benchmarks (`/policy-comparison`)
- Side-by-side benchmark across 4 standardized policies:
  - **FIFO (Baseline)**: Earliest feasible dispatch, zero carbon awareness.
  - **Naive Green**: Greedy minimum forecast ($\lambda = 0$), blind to uncertainty.
  - **Carbonova**: Uncertainty-aware, risk-penalized ($\lambda = 1.0$), SLA-guaranteed.
  - **Perfect-Forecast Oracle**: Theoretical reference ceiling with known hindsight (strictly labeled as an unachievable reference limit).
- 6 sensitivity scenarios: *Variable Diurnal*, *Flat Carbon Curve (Zero Variance)*, *High Forecast Noise*, *Tight Deadlines*, *Resource Contention*, and *Zero Delay Allowed*.
- **Flat Carbon Honesty**: Under flat carbon intensity, the scheduler strictly outputs `0.0 kg avoided emissions` (never manufacturing savings).
- **Backfire Honesty**: When zero jobs are delayed, Backfire Rate returns `N/A` rather than `0.0%`.
- **Fleet Scaling Calculator**: Scales batch savings up to 1,000, 10,000, or 50,000 workloads with official **EPA Greenhouse Gas Equivalencies** (urban tree-months and gallons of gasoline avoided).

### 5. Carbon Time Machine (`/carbon-time-machine`)
- Temporal playback controls: Scrub slider across 24 hours, Play/Pause, Step (-15m / +15m), Reset, and Speed selector (1x, 2x, 5x, 10x).
- Visual playhead marker on the carbon intensity curve indicating time $t$.
- Instantaneous telemetry at time $t$: Marginal carbon intensity, clean generation share (%), cumulative emissions emitted, and live workload queue breakdown (Running, Deferred, Completed).
- Live hyperparameter tuning: Sliders for $\lambda$, forecast error scale ($\sigma$), minimum improvement threshold, and cluster GPU capacity.
- **Explain What Changed**: Traceable natural-language rationale generated from mathematical differentials when parameters are adjusted.

### 6. Scientific Methodology (`/methodology`)
- Publication-quality documentation detailing:
  - Marginal Operating Emissions Rate (MOER) vs. Average emissions.
  - Mathematical risk formulation: $\text{risk\_score}(t) = \hat{\mu}(t) + \lambda \cdot \hat{\sigma}(t)$.
  - Operational emissions equation: $[ \text{Power (kW)} \times \text{Duration (h)} \times \text{PUE} \times \text{Intensity (g/kWh)} ] / 1,000$.
  - The carbon backfire phenomenon and denominator edge-case handling.
  - Full data provenance taxonomy and scientific scope limitations.
  - Academic literature citations (Radovanovic et al. 2022, Dodge et al. 2022, Wiesner et al. 2021).

### 7. GreenGate AI Semantic Router (`/greengate`)
- Extension module for optimizing real-time LLM inference carbon.
- Cascades queries between **Tier-1 Small** (7B parameters, 50W TDP, ~0.008 kWh) and **Tier-2 Large** (70B parameters, 400W TDP, ~0.045 kWh).
- Interactive prompt test bench with pre-configured prompts (Summarization, Entity Extraction, Distributed Systems Architecture, Formal Proofs).
- Configurable Quality Floor Guard with automatic escalation if confidence thresholds fail.
- Live request log recording latency, energy, quality score, and avoided emissions percentage.

---

## 4. Mathematical Formulations

### Operational Carbon Emissions
$$\text{Emissions (kgCO}_2\text{e)} = \frac{\text{Energy (kWh)} \times \text{Intensity (gCO}_2\text{e/kWh})}{1,000}$$

Where Energy $(\text{kWh}) = \frac{\text{Power (Watts)} \times \text{Duration (hours)}}{1,000} \times \text{PUE}$ (standard cloud datacenter $\text{PUE} = 1.15$).

### Heuristic Risk Scoring Formula
$$\text{risk\_score}(t) = \hat{\mu}(t) + \lambda \cdot \hat{\sigma}(t)$$

- $\hat{\mu}(t)$: Forecasted mean marginal carbon intensity at slot $t$.
- $\hat{\sigma}(t)$: Forecasted uncertainty standard deviation.
- $\lambda$: Risk-aversion penalty parameter ($\lambda = 0$ reduces to naive green; $\lambda = 1.0$ standard balanced; $\lambda \ge 2.0$ conservative).

### Carbon Backfire Rate
$$\text{Backfire Rate (\%)} = \begin{cases} \frac{\text{Delayed Jobs with Realized Emissions} > \text{Immediate Counterfactual}}{\text{Total Delayed Jobs}} \times 100\% & \text{if Total Delayed Jobs} > 0 \\ \text{N/A} & \text{if Total Delayed Jobs} = 0 \end{cases}$$

### Normalized Fleet Impact Scaling
$$\text{Avoided Fleet Emissions (kgCO}_2\text{e)} = \frac{\text{Avoided Batch Emissions (kg)}}{\text{Batch Job Count}} \times N_{\text{fleet}}$$

- **Gasoline Gallons Avoided**: $\frac{\text{Avoided kgCO}_2\text{e}}{8.887 \text{ kg/gal}}$ (EPA factor).
- **Urban Tree-Months**: $\frac{\text{Avoided kgCO}_2\text{e}}{0.06 \text{ kg/tree-month}}$ (EPA 10-year seedling sequestration factor).

---

## 5. Visual Identity & Design System

The platform adheres to an enterprise sustainability design language:

| Design Token | Hex Code | Role |
| :--- | :--- | :--- |
| **Primary Green** | `#16A34A` | Primary actions, key results, carbon savings, active navigation |
| **Forest Green** | `#166534` | Brand headers, structural accents |
| **Dark Green** | `#14532D` | Brand identity accents, leaf motif |
| **Main Background** | `#F8FAFC` / `#FFFFFF` | Primary workspace, card surfaces |
| **Main Text** | `#111827` | Headings, primary high-contrast data values |
| **Secondary Text** | `#64748B` | Labels, timestamps, explanatory notes |
| **Subtle Borders** | `#E2E8F0` | Clean card boundaries, table separators |
| **Warning / Caution** | `#D97706` | High-carbon alerts, elevated forecast noise |
| **Error / Alert** | `#DC2626` | Infeasible SLA warnings, missed deadlines |

---

## 6. Quickstart Guide

### Prerequisites
- Node.js 18+ (Node.js 20+ recommended)
- npm or pnpm

### Running the Frontend
```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Launch development server
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser. The application will start in **Simulation Mode** with full interactive functionality, requiring zero backend setup.

### Running Unit Tests
```bash
cd frontend
npm run test
```
Executes the Vitest test suite covering emissions formulas, backfire rate edge cases, time formatters, and scheduler policy scenarios.

### Production Build
```bash
cd frontend
npm run build
```
Typechecks via `tsc --noEmit` and bundles optimized production assets into `frontend/dist/`.

---

## 7. License & Academic Citation

Developed for sustainable computing research, hackathons, and production workload orchestration.

If you use Carbonova in academic research, please cite:
```bibtex
@software{carbonova2026,
  title = {Carbonova: Smarter AI. Cleaner Computing},
  author = {Carbonova Systems},
  year = {2026},
  url = {https://github.com/carbonova/carbonova}
}
```
