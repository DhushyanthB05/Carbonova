# Carbonova Frontend — “Smarter AI. Cleaner Computing.”

**Member 4: Frontend, Visualizations, Dashboards, and Simulation Integration**
Stack: **React 19 + Vite 6 + TypeScript 5.7 + Tailwind CSS 3.4 + Recharts 2.15**

Carbonova is an operational carbon-aware scheduler designed for high-performance AI training and batch workloads. This frontend provides the full user interface, real-time workload scheduling simulation, empirical policy benchmarking, and interactive carbon replay engine.

---

## 1. Quickstart & Setup Instructions

### Prerequisites
- Node.js >= 18.0.0 (v20+ recommended)
- npm or pnpm

### Installation & Development
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start local development server with Hot Module Replacement (HMR)
npm run dev
# The application will launch at http://localhost:5173
```

### Production Build & Preview
```bash
# Typecheck and compile optimized production chunks
npm run build

# Preview the production build locally
npm run preview
```

### Automated Testing
```bash
# Run Vitest test suite (48 tests covering metrics, algorithms, routing, and validation)
npm test -- --run
```

---

## 2. Environment Variables & API Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `""` (Empty string) | URL of the live FastAPI backend (e.g. `http://localhost:8000`). If left blank or unreachable, the frontend seamlessly operates in transparent **Demo Mode (Simulation)**. |

---

## 3. Data Source, Region, Period & Provenance Fallback

- **Grid Balancing Authority:** California ISO (`CAISO-Z2` Regional Balancing Authority).
- **Time-Series Horizon:** 24-Hour empirical diurnal trace with solar duck curve and evening fossil peaking.
- **Resolution:** 15-minute slot sampling interval (displayed in UTC internally and mapped to local PST).
- **Intensity Units:** Grams of CO₂ equivalent per kilowatt-hour ($\text{gCO}_2\text{e/kWh}$).
- **Offline / Backup Demostate:** If the live provider or backend server is offline, the client renders recorded telemetry from CAISO OASIS, clearly badged as `Recorded Grid Carbon` and `Demo Mode (Simulation)`.

---

## 4. API Endpoints & Workload Schema

### API Contract (§11)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Backend status, engine mode, and version string. |
| `GET` | `/api/carbon?region=CAISO-Z2` | 24-hour trace, uncertainty ($\sigma$), solar/gas generation mix, and metadata. |
| `POST` | `/api/jobs` | Submits and validates a computational job into the queue. |
| `DELETE` | `/api/jobs/:id` | Removes a workload from the scheduling queue. |
| `POST` | `/api/schedule/run` | Executes the GreenSchedule solver with custom $\lambda$ and capacity constraints. |
| `GET` | `/api/schedule/results` | Retrieves empirical multi-policy benchmark results across sensitivity scenarios. |
| `POST` | `/api/inference` | Evaluates prompt semantic complexity and routes to Tier-1 vs Tier-2 LLM. |

### Workload Schema (§5, §7.1)
```json
{
  "job_id": "batch-001",
  "job_type": "batch_inference",
  "arrival_time": "2026-10-25T09:00:00Z",
  "deadline": "2026-10-25T17:00:00Z",
  "duration_minutes": 60,
  "energy_kwh": 1.8,
  "priority": 2,
  "deferrable": true,
  "resource_requirement": 1
}
```

---

## 5. Mathematical Formulations & Constraints

1. **Operational Emissions:**
   $$\text{Emissions (gCO}_2\text{e)} = \text{Energy (kWh)} \times \text{Carbon Intensity (gCO}_2\text{e/kWh)}$$

2. **Heuristic Risk-Adjusted Carbon Score:**
   $$\text{risk\_score}(s) = \hat{\mu}(s) + \lambda \cdot \hat{\sigma}(s)$$
   - $\hat{\mu}(s)$: Predicted mean carbon intensity for window $s$.
   - $\hat{\sigma}(s)$: Forecast uncertainty standard deviation.
   - $\lambda \ge 0$: Risk aversion hyperparameter (configurable from 0.0 to 2.5).

3. **Avoided Emissions & Reduction Percentage:**
   $$\Delta E = \max(0, E_{\text{baseline}} - E_{\text{scheduled}})$$
   $$\text{Reduction } \% = \frac{E_{\text{baseline}} - E_{\text{scheduled}}}{E_{\text{baseline}}} \times 100\% \quad (\text{Returns 'N/A' if } E_{\text{baseline}} \le 0)$$

4. **Backfire Rate Under Uncertainty:**
   $$\text{Backfire Rate} = \frac{\sum_{j \in \text{Delayed}} \mathbf{1}\left[I_{\text{realized}}(t_{\text{start}}) > I_{\text{arrival}}\right]}{|\text{Delayed Jobs}|}$$
   - *Statistical Edge Case:* If zero jobs are delayed ($|\text{Delayed Jobs}| = 0$), the formula strictly returns **`'N/A'`**, never `0%`.

5. **Normalized Fleet Scale (EPA GHG Equivalencies):**
   $$\text{Scaled Avoided} = \left(\frac{E_{\text{baseline}} - E_{\text{policy}}}{N_{\text{evaluated}}}\right) \times 1000$$

---

## 6. How to Reproduce the Three-Beat Demo

### Beat 1: See the Carbon Signal (Carbon Time Machine)
1. Navigate to `/carbon-time-machine`.
2. Observe the empirical CAISO carbon intensity curve with diurnal solar duck curve (08:00–16:00 clean dip; 18:00–22:00 peaking gas spike).
3. Click **Play** or scrub the time slider from 06:00 through 24:00 to observe real-time job execution and cumulative emissions updates.

### Beat 2: Make an Uncertainty-Aware Decision
1. Navigate to `/submit-job` and enter an urgent job (tight deadline) and a deferrable training run (broad deadline).
2. Click **Run GreenSchedule Solver** to route to `/schedule-results`.
3. Open the **Parameters Drawer**, adjust $\lambda$ from `0.2` to `2.0`, and click **Re-Solve Schedule**. Notice how jobs shift away from high-variance evening solar shoulders toward guaranteed low-carbon blocks.
4. Read the generated traceable mathematical rationale in the job details drawer.

### Beat 3: Prove the Result (Policy Comparison)
1. Navigate to `/policy-comparison`.
2. Compare the 4 policies (**FIFO Baseline**, **Naive-Green**, **Carbonova GreenSchedule**, and **Perfect-Forecast Oracle** — labeled *Reference Limit*).
3. Toggle between sensitivity scenarios:
   - **Variable**: Demonstrates 28%+ verified carbon savings.
   - **Flat**: Verifies that with 0 variance, savings are strictly $0.0\text{ kg}$ and $0.0\%$.
   - **Noisy**: Demonstrates Naive-Green suffering carbon backfire while Carbonova protects SLAs.
   - **No Delay**: Verifies that backfire rate reports strictly `'N/A'`.

### (Optional Beat 4): GreenGate AI Semantic Router
1. Navigate to `/greengate`.
2. Test a short factual query (routes to compact Tier-1 Mistral-7B, saving 82% energy) vs a complex programming query (routes to Tier-2 Llama-3-70B).
3. Adjust the Quality Floor slider to trigger adaptive escalation.

---

## 7. Known Scope & Limitations

- **Fixed Nominal Power:** Power modeling assumes constant nominal hardware draw across job duration rather than dynamic cycle-accurate NVML telemetry.
- **Gaussian Error Assumption:** Forecast error $\sigma$ is modeled via synthetic Gaussian perturbation rather than multi-modal weather regime switches.
- **Non-Preemptive Batching:** Workloads are modeled as contiguous run intervals without checkpoint-restore migration overhead.

---

## 8. Academic & Industry Literature (§15)

1. **Radovanović, A., et al.** *Carbon-Aware Computing for Datacenters*. ASPLOS 2022 / [arXiv:2106.11750](https://arxiv.org/abs/2106.11750).
2. **Wiesner, P., et al.** *Let's Wait Awhile: Soft Real-Time Workload Shifting*. ACM e-Energy 2021 / [doi:10.1145/3464298.3493399](https://doi.org/10.1145/3464298.3493399).
3. **CarbonScaler.** *Leveraging Carbon-Aware Workload Shifting in Multi-Tenant Clouds*. ACM ASPLOS 2024 / [doi:10.1145/3626788](https://doi.org/10.1145/3626788).
4. **Clover.** *Practical Carbon-Aware AI Workload Scheduling in Heterogeneous Clusters*. ACM EuroSys 2023 / [doi:10.1145/3581784.3607034](https://doi.org/10.1145/3581784.3607034).
5. **Sprout.** *Adaptive Carbon-Aware LLM Inference Routing*. EMNLP 2024 / [aclanthology.org/2024.emnlp-main.1215](https://aclanthology.org/2024.emnlp-main.1215).
6. **Green Software Foundation.** *Carbon Aware SDK Specification*. [greensoftware.foundation](https://github.com/Green-Software-Foundation/carbon-aware-sdk).
