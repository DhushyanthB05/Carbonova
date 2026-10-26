import React, { useState, useEffect, useMemo } from 'react';
import {
  Sliders,
  AlertTriangle,
  Sparkles,
  TreePine,
  Fuel,
} from 'lucide-react';
import { PolicyComparisonChart } from '../components/charts/PolicyComparisonChart';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import { PolicyComparisonResult, TracePoint } from '../types';
import { getCarbonTrace } from '../services/api';
import { mockJobs, initialSchedulerConfig, mockTrace } from '../data/mockData';
import { runPolicyBenchmark } from '../utils/scheduler';

type ScenarioType = 'variable' | 'flat' | 'noisy' | 'tight' | 'contention' | 'no_delay';

const SCENARIO_DESCRIPTIONS: Record<ScenarioType, { title: string; desc: string; callout?: string }> = {
  variable: {
    title: 'Standard Diurnal / Solar-Wind',
    desc: 'Representative CAISO grid trace featuring significant midday solar generation dip and evening fossil ramp.',
  },
  flat: {
    title: 'Flat Carbon Curve (Zero Variance)',
    desc: 'Constant 200 gCO₂e/kWh grid intensity with zero temporal variance.',
    callout: 'Honesty verification: Under flat carbon intensity, all policies correctly show 0.0 kg avoided emissions. The scheduler will never fabricate savings when no grid variance exists.',
  },
  noisy: {
    title: 'High Forecast Uncertainty',
    desc: 'Elevated forecast error variance (2.5x standard deviation).',
    callout: 'Uncertainty test: Demonstrates why naive green scheduling suffers from carbon backfire, whereas Carbonova’s risk-penalized score protects against adverse realization spikes.',
  },
  tight: {
    title: 'Tight Deadlines (Low Slack)',
    desc: 'Workload deadlines are compressed to just 30 minutes past job completion time.',
    callout: 'SLA integrity: Validates that deadline constraints override carbon deferral to prevent missed job deadlines.',
  },
  contention: {
    title: 'High Resource Contention',
    desc: 'Severe GPU cluster capacity limit (4 GPUs maximum parallel capacity).',
    callout: 'Capacity test: Tests greedy stacking prevention and queue prioritization under constrained hardware resources.',
  },
  no_delay: {
    title: 'Zero Delay Allowed (Critical Only)',
    desc: 'All workloads marked non-deferrable (all zero queue delay).',
    callout: 'Backfire edge-case: Because no jobs are postponed, Backfire Rate returns N/A (not 0.0%), adhering to statistical definition.',
  },
};

export const PolicyComparison: React.FC = () => {
  const [trace, setTrace] = useState<TracePoint[]>(mockTrace);
  const [scenario, setScenario] = useState<ScenarioType>('variable');
  const [fleetSize, setFleetSize] = useState<number>(1000);
  const [benchmarks, setBenchmarks] = useState<PolicyComparisonResult[]>(() =>
    runPolicyBenchmark(mockJobs, mockTrace, initialSchedulerConfig, 'variable')
  );
  const [isLoading, setIsLoading] = useState(false);

  // Load trace
  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const { trace: loadedTrace } = await getCarbonTrace();
        const safeTrace = loadedTrace && loadedTrace.length > 0 ? loadedTrace : mockTrace;
        setTrace(safeTrace);
        const results = runPolicyBenchmark(mockJobs, safeTrace, initialSchedulerConfig, scenario);
        setBenchmarks(results);
      } catch (err) {
        console.warn('Failed to benchmark policies, using fallback:', err);
        setTrace(mockTrace);
        const results = runPolicyBenchmark(mockJobs, mockTrace, initialSchedulerConfig, scenario);
        setBenchmarks(results);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [scenario]);

  const handleScenarioChange = (newScenario: ScenarioType) => {
    setScenario(newScenario);
  };

  // Policy results lookup
  const fifo = benchmarks.find((b) => b.policyId === 'fifo');
  const naive = benchmarks.find((b) => b.policyId === 'naive_green');
  const carbonova = benchmarks.find((b) => b.policyId === 'carbonova');
  const oracle = benchmarks.find((b) => b.policyId === 'oracle');

  // Normalized Impact
  const normalizedSavingsKg = useMemo(() => {
    if (!fifo || !carbonova) return 0;
    const batchSavings = Math.max(0, fifo.totalRealizedEmissionsKg - carbonova.totalRealizedEmissionsKg);
    if (batchSavings === 0) return 0;
    return Math.round((batchSavings / (mockJobs.length || 1)) * fleetSize);
  }, [fifo, carbonova, fleetSize]);

  const safeNormalizedSavings = isNaN(normalizedSavingsKg) ? 0 : normalizedSavingsKg;
  const gallonsGasolineAvoided = Math.round(safeNormalizedSavings / 8.887);
  const treeMonthsSequestered = Math.round(safeNormalizedSavings / 0.06);

  return (
    <div className="flex flex-col gap-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-slate-900">Policy Benchmarks & Sensitivity Analysis</h1>
            <ProvenanceBadge type="synthetic" />
          </div>
          <p className="text-xs text-slate-500">
            Rigorous evaluation of Carbonova against standard FIFO baseline, naive greedy shifting, and perfect-forecast oracle
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Batch size:</span>
          <span className="px-2.5 py-1 rounded-md bg-slate-100 text-slate-800 text-xs font-mono font-semibold">
            {mockJobs.length} workloads
          </span>
        </div>
      </div>

      {/* Scenario Selector Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-600" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">Sensitivity Analysis Scenarios</h2>
          </div>
          <span className="text-[11px] text-slate-400">Stress-test scheduler resilience</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {(Object.keys(SCENARIO_DESCRIPTIONS) as ScenarioType[]).map((key) => {
            const isSelected = scenario === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => handleScenarioChange(key)}
                className={`flex flex-col items-start p-2.5 rounded-lg border text-left transition-all ${
                  isSelected
                    ? 'border-emerald-600 bg-emerald-50/50 shadow-xs ring-1 ring-emerald-600'
                    : 'border-slate-200 bg-white hover:bg-slate-50/80 text-slate-700'
                }`}
              >
                <span className={`text-xs font-bold leading-tight ${isSelected ? 'text-emerald-900' : 'text-slate-800'}`}>
                  {SCENARIO_DESCRIPTIONS[key].title.split(' (')[0]}
                </span>
                <span className="text-[10px] text-slate-500 mt-1 line-clamp-2">
                  {SCENARIO_DESCRIPTIONS[key].desc}
                </span>
              </button>
            );
          })}
        </div>

        {/* Dynamic Scenario Callout */}
        {SCENARIO_DESCRIPTIONS[scenario].callout && (
          <div className="mt-1 p-3 rounded-lg bg-amber-50/80 border border-amber-200 text-xs text-amber-900 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <p className="leading-relaxed">{SCENARIO_DESCRIPTIONS[scenario].callout}</p>
          </div>
        )}
      </div>

      {/* 4 Policy Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* FIFO Baseline */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Baseline</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-semibold">Immediate</span>
            </div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Standard FIFO</h3>
            <p className="text-[11px] text-slate-500 mb-3">Dispatches jobs as soon as hardware is available, ignoring carbon.</p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex flex-col gap-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Total Realized:</span>
              <span className="font-bold text-slate-900 font-mono">{fifo?.totalRealizedEmissionsKg.toFixed(1) || '0.0'} kg</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">SLA Attainment:</span>
              <span className="font-semibold text-slate-800">{fifo?.deadlineSuccessPct || 100}%</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Mean Wait:</span>
              <span className="font-semibold text-slate-800">{fifo?.meanWaitHours || 0}h</span>
            </div>
          </div>
        </div>

        {/* Naive Green */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-600">Uncertainty Blind</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 font-semibold">λ = 0</span>
            </div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Naive Green</h3>
            <p className="text-[11px] text-slate-500 mb-3">Delays to lowest forecast point, blind to prediction uncertainty.</p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex flex-col gap-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Reduction vs FIFO:</span>
              <span className="font-bold text-slate-900 font-mono">
                {typeof naive?.emissionsReductionPct === 'number' ? `${naive.emissionsReductionPct}%` : 'N/A'}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Backfire Rate:</span>
              <span className={`font-semibold ${typeof naive?.backfireRatePct === 'number' && naive.backfireRatePct > 0 ? 'text-red-600 font-bold' : 'text-slate-800'}`}>
                {typeof naive?.backfireRatePct === 'number' ? `${naive.backfireRatePct}%` : 'N/A'}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">SLA Attainment:</span>
              <span className="font-semibold text-slate-800">{naive?.deadlineSuccessPct || 100}%</span>
            </div>
          </div>
        </div>

        {/* Carbonova / GreenSchedule */}
        <div className="bg-white rounded-xl border-2 border-emerald-500 p-4 shadow-xs flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-emerald-600 text-white text-[9px] font-bold px-2 py-0.5 rounded-bl-md uppercase">
            Proposed
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">Robust & Safe</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 font-semibold">λ = 1.0</span>
            </div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Carbonova</h3>
            <p className="text-[11px] text-slate-500 mb-3">Penalizes forecast variance to avoid backfire and enforces hard SLAs.</p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex flex-col gap-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Reduction vs FIFO:</span>
              <span className="font-bold text-emerald-700 font-mono">
                {typeof carbonova?.emissionsReductionPct === 'number' ? `${carbonova.emissionsReductionPct}%` : 'N/A'}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Avoided Emissions:</span>
              <span className="font-bold text-emerald-700 font-mono">{carbonova?.realizedSavingsKg.toFixed(1) || '0.0'} kg</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Backfire Rate:</span>
              <span className="font-semibold text-slate-800">
                {typeof carbonova?.backfireRatePct === 'number' ? `${carbonova.backfireRatePct}%` : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Perfect-Forecast Oracle */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Reference Limit</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold">Theoretical</span>
            </div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Perfect-Forecast Oracle</h3>
            <p className="text-[11px] text-slate-500 mb-3">Theoretical benchmark with zero uncertainty and perfect hindsight.</p>
          </div>
          <div className="pt-3 border-t border-slate-100 flex flex-col gap-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Max Possible Reduction:</span>
              <span className="font-bold text-slate-800 font-mono">
                {typeof oracle?.emissionsReductionPct === 'number' ? `${oracle.emissionsReductionPct}%` : 'N/A'}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Carbonova Gap:</span>
              <span className="font-mono text-slate-600">{carbonova?.oracleGapKg.toFixed(1) || '0.0'} kg</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">SLA Attainment:</span>
              <span className="font-semibold text-slate-800">{oracle?.deadlineSuccessPct || 100}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Comparison Chart */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
        <PolicyComparisonChart data={benchmarks} />
      </div>

      {/* Benchmark Matrix Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Comprehensive Benchmark Matrix</h3>
            <p className="text-xs text-slate-500">Direct head-to-head metrics evaluated across the active scenario</p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 font-semibold">
                <th className="py-2.5 px-3">Policy Name</th>
                <th className="py-2.5 px-3">Realized Total</th>
                <th className="py-2.5 px-3">Reduction vs FIFO</th>
                <th className="py-2.5 px-3">Avoided (Realized)</th>
                <th className="py-2.5 px-3">Backfire Rate</th>
                <th className="py-2.5 px-3">Mean Delay</th>
                <th className="py-2.5 px-3">SLA Success</th>
                <th className="py-2.5 px-3">Oracle Gap</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {benchmarks.map((row) => {
                const isCarbonova = row.policyId === 'carbonova';
                return (
                  <tr
                    key={row.policyId}
                    className={`transition-colors ${isCarbonova ? 'bg-emerald-50/30 font-medium' : 'hover:bg-slate-50/50'}`}
                  >
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: row.color }} />
                        <span className="font-bold text-slate-900">{row.policyName}</span>
                        <span className="text-[10px] text-slate-400">({row.badge})</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-800">{row.totalRealizedEmissionsKg.toFixed(1)} kg</td>
                    <td className="py-2.5 px-3 font-mono font-bold">
                      <span className={typeof row.emissionsReductionPct === 'number' && row.emissionsReductionPct > 0 ? 'text-emerald-700' : 'text-slate-600'}>
                        {typeof row.emissionsReductionPct === 'number' ? `${row.emissionsReductionPct}%` : 'N/A'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-700">{row.realizedSavingsKg.toFixed(1)} kg</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={
                          typeof row.backfireRatePct === 'number' && row.backfireRatePct > 0
                            ? 'text-red-600 font-bold bg-red-50 px-1.5 py-0.5 rounded-sm'
                            : 'text-slate-600'
                        }
                      >
                        {typeof row.backfireRatePct === 'number' ? `${row.backfireRatePct}%` : 'N/A'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-700">{row.meanWaitHours}h</td>
                    <td className="py-2.5 px-3">
                      <span className={row.deadlineSuccessPct === 100 ? 'text-emerald-700 font-semibold' : 'text-amber-700'}>
                        {row.deadlineSuccessPct}%
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-500">
                      {row.policyId === 'oracle' ? '— (Reference)' : `${row.oracleGapKg.toFixed(1)} kg`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Normalized Fleet Impact Calculator */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-600" />
              <h3 className="text-sm font-bold text-slate-900">Fleet Scaling & EPA Equivalencies Calculator</h3>
            </div>
            <p className="text-xs text-slate-500">
              Project avoided carbon across larger production clusters using normalized batch savings
            </p>
          </div>

          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-500 font-medium mr-1">Fleet size:</span>
            {[100, 1000, 10000, 50000].map((size) => (
              <button
                key={size}
                type="button"
                onClick={() => setFleetSize(size)}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
                  fleetSize === size ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {size.toLocaleString()}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg bg-emerald-50/60 border border-emerald-100 flex flex-col justify-between">
            <span className="text-xs font-bold text-emerald-900">Avoided Fleet Emissions</span>
            <div className="my-2">
              <div className="text-2xl font-bold font-mono text-emerald-800">
                {safeNormalizedSavings.toLocaleString()} <span className="text-sm font-sans font-semibold">kgCO₂e</span>
              </div>
              <span className="text-[11px] text-emerald-700">Scaled to {fleetSize.toLocaleString()} comparable workloads</span>
            </div>
            <div className="text-[10px] text-emerald-600 font-mono">
              = (Baseline - Carbonova) / {mockJobs.length} × {fleetSize}
            </div>
          </div>

          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex flex-col justify-between">
            <div className="flex items-center gap-2 text-slate-700">
              <TreePine className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-bold">Urban Tree-Months</span>
            </div>
            <div className="my-2">
              <div className="text-2xl font-bold font-mono text-slate-900">
                {treeMonthsSequestered.toLocaleString()}
              </div>
              <span className="text-[11px] text-slate-500">Seedling sequestration equivalent</span>
            </div>
            <span className="text-[10px] text-slate-400">EPA factor: ~0.06 kgCO₂e/tree-month</span>
          </div>

          <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex flex-col justify-between">
            <div className="flex items-center gap-2 text-slate-700">
              <Fuel className="w-4 h-4 text-amber-600" />
              <span className="text-xs font-bold">Gallons Gasoline Consumed</span>
            </div>
            <div className="my-2">
              <div className="text-2xl font-bold font-mono text-slate-900">
                {gallonsGasolineAvoided.toLocaleString()}
              </div>
              <span className="text-[11px] text-slate-500">Unburned fuel equivalent</span>
            </div>
            <span className="text-[10px] text-slate-400">EPA factor: ~8.887 kgCO₂e/gallon gasoline</span>
          </div>
        </div>
      </div>
    </div>
  );
};
