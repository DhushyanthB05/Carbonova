import React from 'react';
import {
  BookOpen,
  Cpu,
  AlertTriangle,
  Layers,
  Shield,
  HelpCircle,
  Activity,
  CheckCircle2,
  FileText,
  ExternalLink,
  Zap,
  TrendingDown,
  Scale
} from 'lucide-react';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';

export const Methodology: React.FC = () => {
  return (
    <div className="flex flex-col gap-8 max-w-5xl mx-auto pb-12">
      {/* Title & Introduction */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-emerald-50 text-emerald-700 rounded-lg">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Carbonova Scientific & Engineering Methodology</h1>
            <p className="text-xs text-slate-500">
              Mathematical formulations, uncertainty bounds, carbon backfire prevention, and data provenance
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-700 leading-relaxed border-t border-slate-100 pt-3">
          Carbonova operates as an operational carbon-aware scheduler designed for high-performance AI training and batch workloads.
          Unlike naive greedy algorithms that chase forecasted dips without considering grid forecast uncertainty, Carbonova balances
          risk-penalized marginal carbon forecasts, hardware capacity limits, and hard completion SLAs to guarantee verified emissions reductions.
        </p>
      </div>

      {/* 1. Carbon-Aware Computing Fundamentals */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Activity className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-bold text-slate-900">1. Marginal vs. Average Carbon Intensity</h2>
        </div>

        <p className="text-xs text-slate-600 leading-relaxed">
          The central scientific distinction in carbon-aware computing is between <strong>average carbon intensity</strong> and <strong>marginal carbon intensity</strong>:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex flex-col gap-2">
            <span className="font-bold text-slate-800">Average Grid Intensity</span>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              The total grid emissions divided by total generation across all sources (nuclear, hydro, fossil, renewables) at a given hour.
              Useful for corporate Scope 2 carbon accounting and annual sustainability audits, but <em>misleading for operational dispatch decisions</em>.
            </p>
          </div>

          <div className="p-4 rounded-lg bg-emerald-50/60 border border-emerald-200 flex flex-col gap-2">
            <span className="font-bold text-emerald-900">Marginal Grid Intensity (MOER)</span>
            <p className="text-emerald-800 leading-relaxed text-[11px]">
              The emissions rate of the specific generator that must ramp up or down in response to a 1 kWh change in demand.
              Because solar and wind operate at near-zero marginal cost, additional compute either consumes curtailed renewables (0 gCO₂e/kWh)
              or forces peaking gas plants to throttle up (~450 gCO₂e/kWh). Marginal intensity is the <strong>only scientifically valid signal</strong> for scheduling compute.
            </p>
          </div>
        </div>
      </div>

      {/* 2. Mathematical Formulation */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Scale className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-bold text-slate-900">2. The Heuristic Risk Scoring Formula</h2>
        </div>

        <p className="text-xs text-slate-600 leading-relaxed">
          Grid carbon forecasting is subject to weather fluctuations, wind ramps, cloud cover, and transmission congestion.
          To protect workloads against forecast failure, Carbonova computes an effective carbon score using an upper confidence bound formulation:
        </p>

        {/* Formula Display Box */}
        <div className="bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-center text-sm shadow-inner flex flex-col items-center gap-2">
          <div className="text-emerald-400 font-bold text-base">
            risk_score(t) = μ̂(t) + λ · σ̂(t)
          </div>
          <span className="text-[11px] text-slate-400 font-sans">
            Where μ̂(t) is predicted mean intensity, σ̂(t) is forecast uncertainty standard deviation, and λ is the risk aversion parameter.
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg border border-slate-200 bg-white">
            <span className="font-bold text-slate-900 block mb-1">λ = 0.0 (Risk Neutral)</span>
            <p className="text-[11px] text-slate-500">
              Behaves like naive greedy shifting. Assumes forecasts are 100% accurate, rendering schedules vulnerable to adverse realization spikes.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/40">
            <span className="font-bold text-emerald-900 block mb-1">λ = 1.0 (Balanced Default)</span>
            <p className="text-[11px] text-emerald-700">
              Penalizes volatile hours by adding 1 standard deviation of uncertainty. Prevents scheduling into ambiguous forecast troughs.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-white">
            <span className="font-bold text-slate-900 block mb-1">λ ≥ 2.0 (Conservative / SLA Guard)</span>
            <p className="text-[11px] text-slate-500">
              Only shifts workloads when forecasted savings overwhelmingly exceed the 95th percentile confidence interval of forecast noise.
            </p>
          </div>
        </div>
      </div>

      {/* 3. Operational Emissions Formula */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Zap className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-bold text-slate-900">3. Operational Emissions Calculation</h2>
        </div>

        <p className="text-xs text-slate-600 leading-relaxed">
          The realized operational emissions generated by executing a computational workload during time window [t_start, t_end] are computed as:
        </p>

        <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl font-mono text-center text-xs text-slate-800">
          Emissions (kgCO₂e) = [ Power (kW) × Duration (hours) × PUE × Intensity (gCO₂e/kWh) ] / 1,000
        </div>

        <div className="text-xs text-slate-600 leading-relaxed space-y-2">
          <p>
            <strong>Power Usage Effectiveness (PUE):</strong> Represents datacenter overhead (cooling, power distribution, chillers).
            Carbonova uses an industry-standard modern cloud PUE multiplier of 1.15.
          </p>
          <p>
            <strong>Net Avoided Emissions:</strong> Avoided kgCO₂e = Baseline FIFO Emissions − Realized Scheduled Emissions.
          </p>
        </div>
      </div>

      {/* 4. The Carbon Backfire Phenomenon */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <h2 className="text-sm font-bold text-slate-900">4. The Carbon Backfire Phenomenon & Edge Cases</h2>
        </div>

        <div className="p-4 rounded-lg bg-amber-50/60 border border-amber-200 text-xs text-amber-950 flex flex-col gap-2">
          <span className="font-bold">Definition of Carbon Backfire:</span>
          <p className="leading-relaxed">
            A <em>carbon backfire event</em> occurs whenever a workload is intentionally delayed to wait for a forecasted green window,
            but due to forecast error, the grid intensity during actual execution ends up <strong>higher than the intensity would have been
            if dispatched immediately upon arrival</strong>.
          </p>
        </div>

        <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl font-mono text-center text-xs text-slate-800">
          Backfire Rate (%) = [ Backfired Delayed Jobs / Total Delayed Jobs ] × 100%
        </div>

        <div className="space-y-2 text-xs text-slate-600 leading-relaxed">
          <p>
            <strong>Statistical Edge-Case Handling (N/A):</strong> If zero jobs are delayed (e.g. all workloads are immediate or critical,
            or no windows showed sufficient improvement), the denominator of the Backfire Rate is 0. In this case, Carbonova strictly
            outputs <code>N/A</code> rather than <code>0.0%</code>, preventing deceptive sustainability claims.
          </p>
          <p>
            <strong>Flat Carbon Curve Honesty:</strong> When the grid curve has zero temporal variance (such as during uninterrupted coal or baseload nuclear
            generation), the scheduler reports exactly <code>0.0 kg avoided emissions</code> and <code>0.0% reduction</code>.
          </p>
        </div>
      </div>

      {/* 5. Policy Definitions */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Layers className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-bold text-slate-900">5. Evaluated Scheduling Policies</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-lg border border-slate-200 bg-white">
            <span className="font-bold text-slate-900 block mb-1">FIFO (Earliest Feasible Baseline)</span>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              Dispatches jobs as soon as hardware capacity permits. Represents the status-quo in standard Slurm, Kubernetes, and Ray clusters.
              Zero carbon awareness.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-slate-200 bg-white">
            <span className="font-bold text-slate-900 block mb-1">Naive Green (Uncertainty Blind)</span>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              Optimizes purely for min μ̂(t) within the deadline window. Ignores forecast variance (λ=0).
              Suffers from catastrophic backfire during unexpected wind ramps or solar dropouts.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-emerald-300 bg-emerald-50/40">
            <span className="font-bold text-emerald-900 block mb-1">Carbonova / GreenSchedule</span>
            <p className="text-emerald-800 leading-relaxed text-[11px]">
              Minimizes μ̂(t) + λσ̂(t) subject to cluster capacity and strict SLA deadlines.
              Requires a minimum improvement threshold before authorizing delay.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-slate-200 bg-white">
            <span className="font-bold text-slate-900 block mb-1">Perfect-Forecast Oracle (Reference Limit)</span>
            <p className="text-slate-600 leading-relaxed text-[11px]">
              Theoretical reference ceiling with complete hindsight (σ=0, known realization).
              Clearly distinguished from real-time algorithms as an unachievable theoretical upper bound.
            </p>
          </div>
        </div>
      </div>

      {/* 6. Data Provenance & Limitations */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Shield className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-bold text-slate-900">6. Data Provenance Taxonomy & Assumptions</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Measured</span>
              <ProvenanceBadge type="measured" />
            </div>
            <p className="text-[11px] text-slate-500">Hardware telemetry directly retrieved from physical energy meters (e.g. NVIDIA NVML, RAPL).</p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Tool-Estimated</span>
              <ProvenanceBadge type="tool-estimated" />
            </div>
            <p className="text-[11px] text-slate-500">Computed via scientific models combining nominal power profiles, PUE constants, and grid carbon rates.</p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Assumption-Based</span>
              <ProvenanceBadge type="assumption-based" />
            </div>
            <p className="text-[11px] text-slate-500">Derived from published industry heuristics (e.g. constant TDP during training, 1.15 cloud PUE factor).</p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Recorded</span>
              <ProvenanceBadge type="recorded" />
            </div>
            <p className="text-[11px] text-slate-500">Empirical historical grid time-series captured from regional ISO balancing authorities.</p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Synthetic</span>
              <ProvenanceBadge type="synthetic" />
            </div>
            <p className="text-[11px] text-slate-500">Programmatically generated benchmark traces with Gaussian perturbations used for sensitivity analysis.</p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-800">Live</span>
              <ProvenanceBadge type="live" />
            </div>
            <p className="text-[11px] text-slate-500">Active streaming telemetry authenticated through live grid APIs (e.g. CAISO OASIS, WattTime).</p>
          </div>
        </div>

        <div className="text-xs text-slate-600 space-y-2 border-t border-slate-100 pt-3">
          <p className="font-bold text-slate-800">Known Limitations & Scope:</p>
          <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-500">
            <li>Power modeling assumes fixed nominal wattage across the duration of a job rather than dynamic cycle-accurate GPU telemetry.</li>
            <li>Carbon forecasting currently assumes independent Gaussian error distribution without non-linear weather regime switches.</li>
            <li>SLA scheduling currently models batch deferral without preemption or checkpoint-restore migration overhead.</li>
          </ul>
        </div>
      </div>

      {/* 7. Academic Citations */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <FileText className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-bold text-slate-900">7. Academic & Industry Literature (§15)</h2>
        </div>

        <div className="space-y-3 text-xs">
          <div className="p-3 rounded-lg border border-slate-100 bg-slate-50 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900">Carbon-Aware Computing for Datacenters</span>
              <a
                href="https://arxiv.org/abs/2106.11750"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-emerald-700 hover:underline flex items-center gap-1 font-mono"
              >
                arXiv:2106.11750 <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-slate-600 text-[11px]">
              Radovanović, A., et al. (Google Research). Mathematical and operational foundations for shifting non-urgent datacenter compute across hours and geographic locations to track variable solar and wind energy.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-slate-100 bg-slate-50 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900">Let&apos;s Wait Awhile: Soft Real-Time Workload Shifting</span>
              <a
                href="https://doi.org/10.1145/3464298.3493399"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-emerald-700 hover:underline flex items-center gap-1 font-mono"
              >
                doi:10.1145/3464298.3493399 <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-slate-600 text-[11px]">
              Wiesner, P., et al. ACM e-Energy 2021. Demonstrates the impact of delay tolerances and deadline-slack allowances on avoiding fossil-peaking generation.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-slate-100 bg-slate-50 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900">CarbonScaler: Elastic Cloud Workload Shifting</span>
              <a
                href="https://doi.org/10.1145/3626788"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-emerald-700 hover:underline flex items-center gap-1 font-mono"
              >
                doi:10.1145/3626788 <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-slate-600 text-[11px]">
              ASPLOS 2024. Explores multi-tenant capacity contention and prevents negative rebound effects under uncertain carbon forecasts.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-slate-100 bg-slate-50 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900">Clover: Practical Carbon-Aware AI Workload Scheduling</span>
              <a
                href="https://doi.org/10.1145/3581784.3607034"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-emerald-700 hover:underline flex items-center gap-1 font-mono"
              >
                doi:10.1145/3581784.3607034 <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-slate-600 text-[11px]">
              EuroSys 2023. Addresses heterogeneous GPU accelerators, job deferral heuristics, and cluster throughput guarantees.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-slate-100 bg-slate-50 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900">Sprout: Adaptive Carbon-Aware LLM Inference Routing</span>
              <a
                href="https://aclanthology.org/2024.emnlp-main.1215"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-emerald-700 hover:underline flex items-center gap-1 font-mono"
              >
                aclanthology.org/2024.emnlp-main.1215 <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-slate-600 text-[11px]">
              EMNLP 2024. Inspires GreenGate: routes language queries between compact and large model tiers according to semantic complexity and instantaneous grid intensity.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-slate-100 bg-slate-50 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900">Carbon Aware SDK</span>
              <a
                href="https://github.com/Green-Software-Foundation/carbon-aware-sdk"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-emerald-700 hover:underline flex items-center gap-1 font-mono"
              >
                Green Software Foundation <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-slate-600 text-[11px]">
              Standardized API definitions and interfaces for consuming marginal emissions rate forecasts from WattTime, Electricity Maps, and ISO telemetry.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
