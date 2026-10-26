# CARBONOVA: FRONTEND MASTER SPECIFICATION & IMPLEMENTATION BLUEPRINT

> **Application Name:** Carbonova
> **Tagline:** “Smarter AI. Cleaner Computing.”
> **Primary Module (P0):** GreenSchedule
> **Optional Module (P1):** GreenGate
> **Frontend Stack (Locked):** React + Vite + Tailwind CSS + Recharts
> **Scope:** Member 4 (Frontend, Visualizations, Dashboards, Carbon Time Machine, API Integration, Presentation & Demo Coordination)

---

## 1. Identity & Visual Principles

### 1.1 Brand Identity & Rules
- **Name:** Carbonova (*locked; do not rename*).
- **Tagline:** *"Smarter AI. Cleaner Computing."*
- **Design Philosophy:** Clean, authoritative climate-tech analytics platform inspired by modern developer infrastructure and enterprise sustainability dashboards.
- **Color Palette (Locked Sustainability Theme):**
  - Primary Green: `#16A34A` (Clean solar/wind, positive deltas, primary actions)
  - Forest Green: `#14532D` (Brand accents, high-contrast headers)
  - Main Background: `#F8FAFC` / `#F7F9F7`
  - Card Background: `#FFFFFF`
  - Text Primary: `#111827` / `#18251E`
  - Text Secondary: `#64748B`
  - Borders: `#E2E8F0` / `#E5EAE5`
  - Warning / Alert: `#D97706` (High carbon grid windows, backfire hazards)
  - Error: `#DC2626` (Infeasible SLA deadlines, capacity over-allocation)

### 1.2 Visual Hierarchy (§12.2)
1. **Carbon Timeline $\rightarrow$ Schedule $\rightarrow$ Proof Chart $\rightarrow$ Detail.**
2. **Units on Every Axis:** Grams of CO₂e per kilowatt-hour ($\text{gCO}_2\text{e/kWh}$), kilowatt-hours ($\text{kWh}$), kilograms of CO₂e ($\text{kgCO}_2\text{e}$), minutes, or percentages.
3. **Timezone Convention:** Displayed in local time (PST) while tracked and transmitted in UTC (`Z` notation).
4. **Predicted vs. Realized Distinction:** The UI must always distinguish predicted forecast metrics ($\hat{\mu}$, $\hat{\sigma}$) from realized evaluation metrics.
5. **No Synthetic Data Silently Presented as Live:** The application must never present synthetic, mock, or recorded traces as live feeds.
6. **No Unqualified Savings Claims:** Never display an isolated savings percentage without naming the **baseline policy**, the **sample size**, and the **trace provenance**.

---

## 2. Screens Required (§12.1)

| Route | Screen Name | Required Content & Visual Elements |
| :--- | :--- | :--- |
| `/` | **Overview Dashboard** | Trace provenance badge; 24h carbon curve with uncertainty area; total jobs count; scheduled jobs count; estimated emissions; baseline comparison KPI cards. |
| `/submit-job` | **Job Submission** | Editable job intake form; real-time feasibility and SLA validation; urgency / deferrable toggle; estimated carbon preview; active queue table with delete and reset confirmations. |
| `/schedule-results` | **Schedule Results** | Gantt-like execution timeline; job execution blocks; deadline markers; cluster resource capacity ceiling; carbon heat strip; interactive parameter tuning drawer; traceable mathematical explanations; JSON & CSV export. |
| `/policy-comparison` | **Policy Comparison** | 4 policies side-by-side (FIFO vs Naive-Green vs Carbonova vs Oracle); emissions avoided, deadline attainment, queue delay, backfire rate; 6 sensitivity scenarios; normalized fleet impact calculator. |
| `/carbon-time-machine` | **Carbon Time Machine** | Interactive time scrubber (06:00 to 24:00); play/pause/step ($\pm 15$m); playback speed (1x–10x); cumulative emissions by policy; uncertainty ($\lambda$) dial with **real solver recomputation**; dynamic "Explain What Changed" rationale. |
| `/methodology` | **Methodology & Provenance** | Scientific models; MOER vs average grid factor; heuristic risk scoring formulas; backfire mechanics; data provenance badges; known limitations; 6 academic & industry literature citations. |
| `/greengate` | **GreenGate AI Router (Optional P1)** | Query complexity analysis; model tier routing (Tier-1 Mistral-7B vs Tier-2 Llama-3-70B); configurable quality floor slider; latency; escalation rate; energy & carbon savings; request audit log. |

---

## 3. Workload Intake Schema & Validation Rules (§5, §7.1)

### Job Data Contract
```typescript
export type JobType = 'training' | 'fine_tuning' | 'batch_inference';
export type JobPriority = 'low' | 'normal' | 'high' | 'critical';
export type JobStatus = 'Scheduled' | 'Running' | 'Completed' | 'Failed' | 'Infeasible';

export interface Job {
  id: string; // Stable unique identifier (e.g. "batch-001")
  name: string; // Workload description
  type: JobType; // Category
  arrivalTime: string; // "2026-10-25T09:00:00Z" (earliest allowed start)
  arrivalMinutes: number; // Minutes from 00:00
  deadline: string; // "2026-10-25T17:00:00Z" (latest finish time)
  deadlineMinutes: number; // Minutes from 00:00
  durationMinutes: number; // Expected runtime in minutes (> 0)
  energyKwh: number; // Total energy for one execution (> 0)
  priority: JobPriority; // Tie-break / service policy
  deferrable: boolean; // Whether the job can be shifted
  resourceRequirement: number; // GPU / node demand (integer >= 1)
  resourceLabel?: string; // Hardware descriptor (e.g. "8x NVIDIA H100")
  status: JobStatus;
}
```

### Validation Invariants
1. **Timing Feasibility:** Reject any submission where `deadlineMinutes < arrivalMinutes + durationMinutes`. Surface explicit error: `Deadline must be at least [duration] after arrival`.
2. **Zero Slack Handling:** When `arrivalMinutes + durationMinutes === deadlineMinutes`, accept the job but mark slack as `0 minutes` (non-deferrable).
3. **Identifier Integrity:** Job IDs must be unique across the queue (case-insensitive) and $\ge 3$ characters.
4. **Physical Bounds:** Duration must be $1 \le \text{duration} \le 1440$ minutes (24 hours). Energy must be $> 0\text{ kWh}$.
5. **Urgent & Non-Deferrable Jobs:** If `deferrable === false`, lock the scheduled start time strictly to `arrivalMinutes`.

---

## 4. Scheduler Hyperparameters & Objective Function (§6)

### Heuristic Risk Scoring Formula
$$\text{risk\_score}(s) = \hat{\mu}(s) + \lambda \times \hat{\sigma}(s)$$
- $\hat{\mu}(s)$: Predicted average carbon intensity across slot window $s$ ($\text{gCO}_2\text{e/kWh}$).
- $\hat{\sigma}(s)$: Forecast uncertainty standard deviation across slot window $s$.
- $\lambda \ge 0$: Risk aversion coefficient.
- *Notice:* The risk score is an operational heuristic score, not a guaranteed upper bound and not a proof against backfire.

### Configurable Hyperparameters Exposed in UI
| Parameter | Range / Options | Operational Behavior |
| :--- | :--- | :--- |
| **Risk Aversion ($\lambda$)** | $0.0 \le \lambda \le 2.5$ | $\lambda=0$: behaves like greedy Naive-Green. Higher $\lambda$ shifts jobs away from volatile intervals toward predictable low-carbon baselines. |
| **Minimum Improvement Margin** | $0\% \le \delta \le 30\%$ | Flexible jobs are delayed only if the candidate slot improves upon the arrival slot's risk score by at least $\delta\%$. |
| **Job Ordering Policy** | `Earliest Arrival First` vs `Least Deadline Slack First` | Determines queue dispatch order when resolving contention. |
| **Slot Interval Resolution** | 15 min, 30 min, 60 min | Scheduling discretization step. (Hourly when the source is hourly; never fabricate precision). |
| **Cluster Capacity Limit** | 4 to 32 accelerator nodes | Concurrent GPU limit applied equally across all evaluated policies. |
| **Forecast Error Scale** | $0.0 \le \text{scale} \le 2.0$ | Clearly labeled in UI as a **Simulation Control**, not live grid forecast certainty. |
| **Reproducibility Seed** | Fixed integer (e.g. `42`) | Ensures deterministic, reproducible schedule calculations. |

---

## 5. The Four Benchmark Policies (§7)

| Policy | Decision Rule | UI Constraints & Labeling |
| :--- | :--- | :--- |
| **1. FIFO / Baseline** | Earliest feasible slot in chosen job order. | Baseline reference for all avoided carbon deltas. |
| **2. Naive-Green** | Lowest predicted mean intensity ($\hat{\mu}$); zero uncertainty penalty ($\lambda = 0$). | Demonstrates carbon backfire vulnerability under noisy realization curves. |
| **3. Carbonova GreenSchedule** | Minimizes risk score $\hat{\mu} + \lambda \hat{\sigma}$ subject to minimum-improvement rule and capacity. | Production algorithm; balances savings with deadline guarantees. |
| **4. Perfect-Forecast Greedy Oracle** | Uses actual future realized trace with the same greedy scheduler structure. | **Reference Limit Only.** Must be badged `Reference Limit` and **NEVER** called "optimal" or "achievable". |

*Evaluation Rules:* All 4 policies receive the exact same jobs, energy demands, time resolution, capacity ceiling, and evaluation horizon. All are scored against the same realized carbon trace.

---

## 6. Formal Metrics & Mathematical Definitions (§8)

### Formulas
1. **Total Operational Emissions:**
   $$\text{Emissions (gCO}_2\text{e)} = \sum_{j \in \text{Jobs}} E_j \times I_{\text{realized}}(t_{\text{start}, j})$$

2. **Emissions Reduction Percentage:**
   $$\text{Reduction } \% = \frac{E_{\text{FIFO}} - E_{\text{Policy}}}{E_{\text{FIFO}}} \times 100\%$$
   *(Always explicitly name FIFO as the baseline; return `'N/A'` if $E_{\text{FIFO}} \le 0$)*.

3. **Deadline Attainment Success Rate:**
   $$\text{Success } \% = \frac{N_{\text{completed before deadline}}}{N_{\text{feasible at submission}}} \times 100\%$$
   *(The UI must also display the count and list of any initially infeasible jobs)*.

4. **Waiting Time Overhead:**
   $$\text{Overhead} = \text{Mean}(t_{\text{scheduled start}} - t_{\text{arrival}})$$

5. **Carbon Backfire Rate:**
   $$\text{Backfire Rate} = \frac{\sum_{j \in \text{Delayed}} \mathbf{1}\left[I_{\text{realized}}(t_{\text{start}, j}) > I_{\text{arrival}, j}\right]}{|\text{Delayed Jobs}|}$$
   - **Critical Edge Case:** If no jobs were delayed ($|\text{Delayed Jobs}| = 0$), the backfire rate is **strictly `N/A`, never `0%`**.
   - Disclose that the immediate-run counterfactual is per-job and does not model system-wide interactions under capacity contention.

6. **Normalized Fleet Scale (EPA GHG Equivalencies):**
   $$\text{Savings per 1,000 Jobs} = \left(\frac{E_{\text{FIFO}} - E_{\text{Carbonova}}}{N_{\text{evaluated}}}\right) \times 1000$$
   - Gasoline vehicle miles: $1\text{ kgCO}_2\text{e} \approx 2.484\text{ miles}$.
   - Tree seedlings grown for 10 years: $1\text{ metric ton} \approx 16.5\text{ seedlings}$.
   - Smartphones charged: $1\text{ kgCO}_2\text{e} \approx 121.6\text{ smartphones}$.

---

## 7. Data Provenance Badges (§9)

| Badge Label | Color Code | Scientific Definition |
| :--- | :--- | :--- |
| **Measured** | Blue (`#2563EB`) | Direct hardware meter or telemetry (e.g. IPMI/NVML power draw). |
| **Tool-Estimated** | Indigo (`#4F46E5`) | Tool estimation (e.g. CodeCarbon, MLPerf TDP models under documented assumptions). |
| **Assumption-Based** | Slate (`#64748B`) | User-supplied or nominal hardware profile declaration. |
| **Recorded Carbon** | Emerald (`#16A34A`) | Empirical historical grid time-series from documented balancing authorities (e.g. CAISO OASIS). |
| **Synthetic** | Amber (`#D97706`) | Programmatically generated perturbation data for sensitivity testing; *not a claim about real grid conditions*. |

---

## 8. Dynamic Traceable Explanations (§10)

Every scheduling decision must generate a traceable, human-readable sentence built from **actual run values**:
> *"Scheduled at [14:00] rather than [10:00] because the predicted carbon intensity is lower by [95] gCO₂/kWh; the slot remains feasible, leaves [70] minutes of deadline slack, and incurs an uncertainty penalty of [λ·σ = 18] gCO₂/kWh."*

---

## 9. Backend API Contract (§11)

| Endpoint | Method | Input Parameters / Body | Response Schema |
| :--- | :--- | :--- | :--- |
| `/api/health` | `GET` | None | `{ status: string, core: string, version: string, mode: string }` |
| `/api/carbon` | `GET` | `?region=CAISO-Z2` | `{ trace: TracePoint[], metadata: TraceMetadata }` |
| `/api/jobs` | `POST` | `Omit<Job, 'status'>` | `Job` (with validated `status: 'Scheduled'`) |
| `/api/jobs/:id` | `DELETE` | Path parameter `:id` | `{ success: boolean, removed_id: string }` |
| `/api/schedule/run` | `POST` | `{ config: SchedulerConfig, jobs: Job[] }` | `{ jobs: Job[], metrics: EvaluatedMetrics }` |
| `/api/schedule/results` | `GET` | `?scenario=variable` | `PolicyComparisonResult[]` (All 4 policies) |
| `/api/inference` | `POST` | `{ query: string, qualityFloor: number }` | `GreenGateInference` (Tier routing, latency, energy) |

---

## 10. Required Sensitivity Scenarios (§12)

1. **Variable Carbon:** Standard empirical diurnal CAISO duck curve (high solar daytime dip, evening gas spike).
2. **Flat Carbon Curve:** Zero variance ($200\text{ gCO}_2\text{e/kWh}$ constant). Sanity check: **$0.0\text{ kg}$ avoided and $0.0\%$ reduction across all policies**.
3. **Noisy Forecast:** High forecast error ($\pm 40\%$ synthetic perturbation). Demonstrates Naive-Green backfire while Carbonova maintains positive savings.
4. **Tight Deadlines:** Slack reduced to $<30$ minutes. Tests deadline attainment under urgency.
5. **Resource Contention:** Lowered cluster capacity (8 accelerator nodes). Verifies queueing without double-booking.
6. **No Jobs Delayed:** Zero flexible jobs shifted. Sanity check: **Backfire rate displays strictly `'N/A'`**.

---

## 11. Complete Antigravity Build Phases (1 through 10)

### Phase 1: Project Setup, Tooling & Baseline Sanity
- Configure React 19, Vite 6, TypeScript 5.7, Tailwind CSS 3.4, Recharts 2.15, and Vitest.
- Ensure strict TypeScript configuration with zero compiler warnings.
- Establish initial project structure (`src/pages`, `src/components`, `src/utils`, `src/services`, `src/data`, `src/types`).
- Verify build pipeline (`npm run build`, `npm test`).

### Phase 2: Design System, Layout Shell & Navigation
- Implement persistent responsive layout shell ([AppShell.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/components/layout/AppShell.tsx)) with sidebar and top telemetry header.
- Enforce sustainability palette (`#16A34A`, `#14532D`, `#F8FAFC`, `#FFFFFF`, `#111827`, `#64748B`, `#E2E8F0`).
- Embed top-level React Error Boundary ([ErrorBoundary.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/components/common/ErrorBoundary.tsx)) and catch-all 404 handler ([NotFound.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/pages/NotFound.tsx)).
- Configure route-based code splitting with `React.lazy` and [PageLoadingFallback.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/components/common/PageLoadingFallback.tsx).

### Phase 3: Overview Dashboard & Provenance Signals
- Build [Overview.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/pages/Overview.tsx).
- Display KPI metrics cards: Current Intensity, 24h Average, Avoided Carbon Today, Realized Reduction %, Clean Generation Share.
- Render 24-hour carbon intensity forecast curve with $\pm 1\sigma$ uncertainty shaded area and scheduled job overlay blocks.
- Render provenance status badge (`Recorded Grid Carbon` / `Demo Mode (Simulation)`).

### Phase 4: Job Intake, Feasibility Validation & Queue Management
- Build [JobSubmission.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/pages/JobSubmission.tsx) and [validation.ts](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/utils/validation.ts).
- Validate arrival, deadline, duration, energy, GPU capacity, and duplicate IDs.
- Surface real-time carbon avoidance estimate for entered parameters.
- Provide active job queue table with modal confirmations for job removal and queue reset.

### Phase 5: Schedule Results Page (§12.1, Phase 5)
- Build [ScheduleResults.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/pages/ScheduleResults.tsx).
- **Gantt Execution Timeline:** Visual horizontal bars depicting job start, duration, and completion aligned to the 24-hour grid clock.
- **Deadline Markers:** Vertical indicator flags showing hard deadline boundaries.
- **Cluster Capacity Ceiling:** Horizontal indicator at 16 accelerator nodes displaying real-time allocation vs ceiling.
- **Carbon Heat Strip:** Diurnal color gradient ribbon mapping low carbon (green) to high carbon (amber/red).
- **Interactive Tuning Drawer:** Sliding panel enabling real-time tuning of $\lambda$, minimum improvement threshold, slot interval, ordering strategy, and capacity limit with instant dynamic re-solve.
- **Job Detail Drawer:** Inspect individual workload rationale, predicted vs realized emissions, and slack margins.
- **Export Engine:** Client-side generation of `carbonova_schedule.json` and `carbonova_schedule.csv`.

### Phase 6: Policy Comparison Page (§12.1, Phase 6)
- Build [PolicyComparison.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/pages/PolicyComparison.tsx).
- **Comparative Metrics Table:** Side-by-side comparison of FIFO, Naive-Green, Carbonova, and Oracle across:
  - Total emissions ($\text{kgCO}_2\text{e}$)
  - Avoided emissions ($\text{kgCO}_2\text{e}$)
  - Percentage reduction ($\%$)
  - Deadline attainment rate ($\%$)
  - Mean queue delay (minutes)
  - Backfire rate ($\%$, with strict `'N/A'` when zero jobs delayed)
- **Predicted vs Realized Chart:** Visual bar chart contrasting anticipated savings against empirical realized savings.
- **Sensitivity Scenario Tabs:** Instant toggling across 6 scenarios (`Variable`, `Flat`, `Noisy`, `Tight`, `Contention`, `No Delay`).
- **Normalized Fleet Impact Calculator:** Extrapolate savings to 100, 1,000, 10,000, and 50,000 jobs with EPA equivalencies (miles driven, tree seedlings grown, smartphones charged).

### Phase 7: Carbon Time Machine (§4.3, §12.3, Phase 7)
- Build [CarbonTimeMachine.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/pages/CarbonTimeMachine.tsx).
- **Replay Controls:** Play, Pause, Step Forward (+15m), Step Backward (-15m), Playback Speed (1x, 2x, 5x, 10x).
- **Interactive Scrubber:** Range slider across 06:00–24:00 snapping to 15-minute intervals.
- **Synchronized Telemetry Gauges:** Instantaneous display of simulated clock, current grid intensity, and active workload status.
- **Cumulative Emissions Ticker:** Real-time running total comparing FIFO vs Carbonova as time advances.
- **Uncertainty & Slack Dial:** Adjust $\lambda$ during playback to **trigger a real schedule recomputation**.
- **"Explain What Changed" Engine:** Generates natural-language reasoning citing mathematical deltas.
- **Simulation Control Label:** Clearly designate forecast error sliders as simulation controls.

### Phase 8: Methodology, Provenance & URL Persistence (Phase 8)
- Build [Methodology.tsx](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/pages/Methodology.tsx).
- Render mathematical formulations with KaTeX math blocks.
- Detail MOER vs average grid carbon factors.
- Embed all 5 data provenance definitions and known system limitations.
- Provide links and formal citations for all 6 academic/industry works:
  1. Radovanović et al. (ASPLOS 2022, arXiv:2106.11750)
  2. Wiesner et al. (ACM e-Energy 2021, doi:10.1145/3464298.3493399)
  3. CarbonScaler (ASPLOS 2024, doi:10.1145/3626788)
  4. Clover (EuroSys 2023, doi:10.1145/3581784.3607034)
  5. Sprout (EMNLP 2024, aclanthology.org/2024.emnlp-main.1215)
  6. Green Software Foundation Carbon Aware SDK Specification

### Phase 9: Real API Integration & Graceful Simulation Fallback (Phase 9)
- Build [api.ts](file:///c:/Users/elvizanton/OneDrive/Desktop/Carbonova/frontend/src/services/api.ts).
- Implement HTTP requests for all 7 API endpoints against `VITE_API_BASE_URL`.
- Implement transparent fallback to local pure-TypeScript simulation engine when backend is offline.
- Visibly display `Demo Mode (Simulation)` without false claims of live backend connectivity.

### Phase 10: Tests, Accessibility, Documentation & Demo Readiness (Phase 10)
- **Unit & Integration Tests:** 48 passing tests in Vitest covering metrics, scheduling algorithms, validation, API fallback, and routing.
- **Static Analysis:** Zero errors on `npx tsc --noEmit`.
- **Bundle Optimization:** Code splitting with `React.lazy` and `manualChunks`, reducing entry script to 29.8 kB (zero chunks $>500$ kB).
- **Documentation:** Publish `frontend/README.md` containing run commands, `.env.example`, schemas, mathematical formulations, and reproduction steps for the three-beat demo.
- **GreenGate Validation:** Interactive demo module active at `/greengate` with complexity analysis, model tiers, and quality floor escalation.

---

## 12. Definition of Done Checklist (§13)

- [x] A user can submit at least one urgent and one deferrable job with full validation.
- [x] The scheduler assigns feasible slots within deadline boundaries and displays traceable explanations.
- [x] The risk hyperparameter ($\lambda$) slider triggers real mathematical recomputation.
- [x] All four policies (FIFO, Naive-Green, Carbonova, Oracle) are benchmarked on the same jobs and same realized trace.
- [x] Perfect-Forecast Oracle is explicitly labeled `Reference Limit` (never "optimal").
- [x] Flat carbon curve guarantees strictly $0.0\text{ kg}$ avoided and $0.0\%$ reduction.
- [x] Backfire rate returns strictly `'N/A'` when zero jobs are delayed.
- [x] Data provenance badges (`Recorded`, `Synthetic`, `Measured`, `Tool-Estimated`, `Assumption-Based`) are visible.
- [x] Offline demo mode activates automatically when backend is absent, clearly disclosed in the UI.
- [x] The production bundle compiles cleanly with 0 type errors and zero chunks exceeding 500 kB.
- [x] The frontend README documents setup, reproduction steps, schemas, and literature citations.
