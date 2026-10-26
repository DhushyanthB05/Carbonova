import React, { useState } from 'react';
import {
  Cpu,
  Zap,
  Sparkles,
  ArrowRight,
  Shield,
  Layers,
  Clock,
  Send,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  DollarSign
} from 'lucide-react';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import { MetricCard } from '../components/common/MetricCard';
import { GreenGateInference } from '../types';
import { runGreenGateInference } from '../services/api';

const PRESET_QUERIES = [
  {
    label: 'Email Summary (Simple)',
    query: 'Summarize this 3-sentence email notification regarding meeting rescheduling.',
    complexity: 'low',
  },
  {
    label: 'Entity Extraction (Simple)',
    query: 'Extract the transaction date, merchant name, and total amount from this receipt snippet.',
    complexity: 'low',
  },
  {
    label: 'Distributed Architecture (Complex)',
    query: 'Architect a distributed fault-tolerant Raft consensus protocol handling Byzantine failures with Raft log compaction.',
    complexity: 'high',
  },
  {
    label: 'Mathematical Proof (Complex)',
    query: 'Provide a formal mathematical proof that the square root of 2 is irrational using proof by contradiction.',
    complexity: 'high',
  },
];

export const GreenGate: React.FC = () => {
  const [queryInput, setQueryInput] = useState(
    'Summarize this 3-sentence email notification regarding meeting rescheduling.'
  );
  const [qualityFloor, setQualityFloor] = useState(0.85);
  const [isRouting, setIsRouting] = useState(false);
  const [recentRequests, setRecentRequests] = useState<GreenGateInference[]>([
    {
      id: 'REQ-4102',
      timestamp: '14:22:10',
      query: 'Summarize this 3-sentence email notification...',
      routingDecision: 'Tier-1 Small (Fast)',
      modelName: 'Mistral-7B-Instruct',
      routingReason: 'Query resolved within quality floor by Tier-1 small model',
      qualityScore: 0.88,
      qualityFloorPassed: true,
      latencyMs: 140,
      escalated: false,
      energyKwh: 0.008,
      carbonGrams: 0.74,
      savingsVsLargePct: 82.4,
    },
    {
      id: 'REQ-4101',
      timestamp: '14:20:45',
      query: 'Architect a distributed fault-tolerant Raft consensus...',
      routingDecision: 'Tier-2 Large (Deep)',
      modelName: 'Llama-3-70B-Instruct',
      routingReason: 'Query complexity exceeds Tier-1 semantic ceiling',
      qualityScore: 0.95,
      qualityFloorPassed: true,
      latencyMs: 490,
      escalated: false,
      energyKwh: 0.045,
      carbonGrams: 4.2,
      savingsVsLargePct: 0,
    },
  ]);

  const activeInference = recentRequests[0];

  const handleRouteQuery = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!queryInput.trim() || isRouting) return;

    setIsRouting(true);
    try {
      const res = await runGreenGateInference(queryInput, qualityFloor);
      setRecentRequests((prev) => [res, ...prev.slice(0, 9)]);
    } catch (err) {
      console.error('GreenGate routing failed:', err);
    } finally {
      setIsRouting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-slate-900">GreenGate AI Inference Router</h1>
            <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 text-[10px] font-bold uppercase tracking-wider">
              Extension Module
            </span>
            <ProvenanceBadge type="tool-estimated" />
          </div>
          <p className="text-xs text-slate-500">
            Semantic query router cascading workloads to Tier-1 Small (7B) vs. Tier-2 Large (70B) LLMs to slash inference emissions
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-semibold">
            <Zap className="w-3.5 h-3.5 text-emerald-600" />
            <span>Avg. -68% Inference Emissions</span>
          </div>
        </div>
      </div>

      {/* High-level KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Fleet Carbon Avoided"
          value="68.2%"
          unit="vs all-Tier 2"
          icon={<Sparkles className="w-4 h-4" />}
          change="+82% on small queries"
          isPositive={true}
          tooltipText="Net reduction in operational inference carbon achieved by routing simple and moderate queries to energy-efficient 7B models."
          provenanceType="tool-estimated"
        />

        <MetricCard
          title="Tier-1 Small Routing Ratio"
          value="74%"
          unit="of queries"
          icon={<Layers className="w-4 h-4" />}
          tooltipText="Proportion of incoming traffic successfully handled by Tier-1 small language models without cascading."
          provenanceType="measured"
        />

        <MetricCard
          title="Quality Retention"
          value="98.7%"
          unit="benchmark score"
          icon={<Shield className="w-4 h-4" />}
          isPositive={true}
          tooltipText="Relative task accuracy and benchmark score maintained compared to routing 100% of queries to Tier-2 70B."
          provenanceType="measured"
        />

        <MetricCard
          title="Average Latency"
          value="210"
          unit="ms"
          icon={<Clock className="w-4 h-4" />}
          change="-56% speedup"
          isPositive={true}
          tooltipText="Mean end-to-end response time across blended traffic."
          provenanceType="measured"
        />
      </div>

      {/* Interactive Testing & Router Config */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Prompt Input & Presets */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-emerald-600" />
              <h2 className="text-sm font-bold text-slate-900">Interactive Prompt Test Bench</h2>
            </div>
            <span className="text-xs text-slate-400">Evaluate semantic routing decisions live</span>
          </div>

          {/* Quick Presets */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Example Prompts:</span>
            <div className="flex flex-wrap gap-2">
              {PRESET_QUERIES.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setQueryInput(p.query)}
                  className="px-2.5 py-1 rounded-md border border-slate-200 text-xs text-slate-700 bg-slate-50 hover:bg-slate-100 transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Input form */}
          <form onSubmit={handleRouteQuery} className="flex flex-col gap-3">
            <textarea
              rows={3}
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder="Enter an LLM prompt to evaluate model tier routing..."
              className="w-full p-3 text-xs text-slate-800 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-emerald-500 font-mono"
            />

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-600 font-medium">Quality Floor Threshold:</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={0.7}
                    max={0.95}
                    step={0.05}
                    value={qualityFloor}
                    onChange={(e) => setQualityFloor(parseFloat(e.target.value))}
                    className="accent-emerald-600 cursor-pointer w-24"
                  />
                  <span className="text-xs font-mono font-bold text-slate-800">
                    {(qualityFloor * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <button
                type="submit"
                disabled={isRouting}
                className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold shadow-xs hover:bg-emerald-700 transition-colors disabled:opacity-50"
              >
                {isRouting ? (
                  <span>Routing...</span>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Route Query</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Active Result Card */}
          {activeInference && (
            <div className="mt-2 p-4 rounded-xl border border-slate-200 bg-slate-50/60 flex flex-col gap-3">
              <div className="flex items-center justify-between pb-2 border-b border-slate-200/60">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-900">Latest Decision:</span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                      activeInference.routingDecision.includes('Tier-1')
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-purple-100 text-purple-800'
                    }`}
                  >
                    {activeInference.routingDecision}
                  </span>
                </div>
                <span className="text-xs font-mono text-slate-500">{activeInference.modelName}</span>
              </div>

              <p className="text-xs text-slate-600">{activeInference.routingReason}</p>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs">
                <div className="p-2 rounded-md bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Latency</span>
                  <span className="font-mono font-bold text-slate-800">{activeInference.latencyMs} ms</span>
                </div>
                <div className="p-2 rounded-md bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Energy</span>
                  <span className="font-mono font-bold text-slate-800">
                    {(activeInference.energyKwh * 1000).toFixed(1)} Wh
                  </span>
                </div>
                <div className="p-2 rounded-md bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Emissions</span>
                  <span className="font-mono font-bold text-slate-800">{activeInference.carbonGrams} gCO₂e</span>
                </div>
                <div className="p-2 rounded-md bg-white border border-slate-200">
                  <span className="text-[10px] text-slate-400 block">Avoided vs Tier-2</span>
                  <span className="font-mono font-bold text-emerald-700">
                    {activeInference.savingsVsLargePct > 0 ? `-${activeInference.savingsVsLargePct}%` : 'Baseline'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Col: Tier Specifications & Topology */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
          <div className="pb-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900">Inference Tier Specifications</h3>
            <p className="text-xs text-slate-500">Power, model weights, and dispatch ceilings</p>
          </div>

          {/* Tier-1 */}
          <div className="p-3.5 rounded-lg border border-emerald-200 bg-emerald-50/40 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-950">Tier-1: Small Language Model</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">50W TDP</span>
            </div>
            <p className="text-[11px] text-emerald-800">
              e.g. Mistral-7B, Llama-3-8B. Dispatched for classification, summarization, entity extraction, and structured JSON parsing.
            </p>
            <div className="flex justify-between text-[11px] font-mono text-emerald-900 pt-1 border-t border-emerald-200/60">
              <span>Avg. Latency: ~140ms</span>
              <span>~0.008 kWh</span>
            </div>
          </div>

          {/* Tier-2 */}
          <div className="p-3.5 rounded-lg border border-purple-200 bg-purple-50/40 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-purple-950">Tier-2: Frontier Foundation Model</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 font-bold">400W TDP</span>
            </div>
            <p className="text-[11px] text-purple-800">
              e.g. Llama-3-70B, Mixtral-8x22B. Dispatched for multi-step reasoning, mathematical theorem proving, and code synthesis.
            </p>
            <div className="flex justify-between text-[11px] font-mono text-purple-900 pt-1 border-t border-purple-200/60">
              <span>Avg. Latency: ~480ms</span>
              <span>~0.045 kWh</span>
            </div>
          </div>

          {/* Quality Floor Guard */}
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-start gap-2">
            <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <p className="text-[11px] leading-relaxed">
              <strong>Quality Floor Guard:</strong> If a Tier-1 model expresses low logit confidence or fails output schema checks, the query automatically escalates to Tier-2.
            </p>
          </div>
        </div>
      </div>

      {/* Recent Requests Audit Log */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Recent Inference Invocations ({recentRequests.length})</h3>
            <p className="text-xs text-slate-500">Live semantic routing log with latency and carbon measurements</p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 font-semibold">
                <th className="py-2.5 px-3">Request ID</th>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Query Snippet</th>
                <th className="py-2.5 px-3">Routed Tier</th>
                <th className="py-2.5 px-3">Model</th>
                <th className="py-2.5 px-3">Latency</th>
                <th className="py-2.5 px-3">Quality Score</th>
                <th className="py-2.5 px-3">Avoided vs Tier-2</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentRequests.map((req) => (
                <tr key={req.id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="py-2.5 px-3 font-mono font-bold text-slate-800">{req.id}</td>
                  <td className="py-2.5 px-3 text-slate-500 font-mono">{req.timestamp}</td>
                  <td className="py-2.5 px-3 max-w-xs truncate text-slate-700" title={req.query}>
                    {req.query}
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        req.routingDecision.includes('Tier-1')
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-purple-50 text-purple-700'
                      }`}
                    >
                      {req.routingDecision.split(' ')[0]}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-600 font-mono text-[11px]">{req.modelName}</td>
                  <td className="py-2.5 px-3 font-mono text-slate-700">{req.latencyMs} ms</td>
                  <td className="py-2.5 px-3 font-mono text-slate-700">{(req.qualityScore * 100).toFixed(0)}%</td>
                  <td className="py-2.5 px-3 font-mono font-bold">
                    <span className={req.savingsVsLargePct > 0 ? 'text-emerald-700' : 'text-slate-400'}>
                      {req.savingsVsLargePct > 0 ? `-${req.savingsVsLargePct.toFixed(1)}%` : '0.0%'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
