import React from 'react';
import { Sliders, HelpCircle, Shield, RefreshCw } from 'lucide-react';
import { SchedulerConfig } from '../../types';

interface SchedulerConfigPanelProps {
  config: SchedulerConfig;
  onChange: (newConfig: SchedulerConfig) => void;
  onRun?: () => void;
  isSolving?: boolean;
}

export const SchedulerConfigPanel: React.FC<SchedulerConfigPanelProps> = ({
  config,
  onChange,
  onRun,
  isSolving = false,
}) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col gap-5">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-emerald-50 text-emerald-700 rounded-lg">
            <Sliders className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">GreenSchedule Solver Parameters</h3>
            <p className="text-xs text-slate-500">
              Configure heuristic risk penalty, SLA buffers, and dispatch priorities
            </p>
          </div>
        </div>

        {onRun && (
          <button
            type="button"
            onClick={onRun}
            disabled={isSolving}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold shadow-xs hover:bg-emerald-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSolving ? 'animate-spin' : ''}`} />
            <span>{isSolving ? 'Solving...' : 'Run Scheduler'}</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 text-xs">
        {/* Risk Aversion Lambda (λ) */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <label htmlFor="lambda-input" className="font-semibold text-slate-700">
                Risk Aversion Penalty (λ)
              </label>
              <div
                title="risk_score(s) = predicted_intensity(s) + λ × predicted_uncertainty(s). This is a heuristic score, not a guaranteed upper bound on realized emissions."
                className="cursor-help text-slate-400 hover:text-slate-600"
              >
                <HelpCircle className="w-3.5 h-3.5" />
              </div>
            </div>
            <span className="font-mono font-bold text-emerald-700 text-sm">
              λ = {config.lambda.toFixed(1)}
            </span>
          </div>
          <input
            id="lambda-input"
            type="range"
            min="0.0"
            max="3.0"
            step="0.1"
            value={config.lambda}
            onChange={(e) => onChange({ ...config, lambda: parseFloat(e.target.value) })}
            className="w-full accent-emerald-600 cursor-pointer"
          />
          <span className="text-[10px] text-slate-400">
            Higher values penalize high-uncertainty slots. λ = 0 reduces to greedy naive-green.
          </span>
        </div>

        {/* Minimum-improvement margin */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="min-improvement" className="font-semibold text-slate-700">
              Min. Improvement Margin
            </label>
            <span className="font-mono font-bold text-slate-800">
              {config.minImprovementPct}% CO₂e
            </span>
          </div>
          <input
            id="min-improvement"
            type="range"
            min="0"
            max="30"
            step="5"
            value={config.minImprovementPct}
            onChange={(e) => onChange({ ...config, minImprovementPct: parseInt(e.target.value, 10) })}
            className="w-full accent-emerald-600 cursor-pointer"
          />
          <span className="text-[10px] text-slate-400">
            Minimum % emissions savings required before a flexible job is delayed.
          </span>
        </div>

        {/* Job Ordering */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="ordering-select" className="font-semibold text-slate-700">
            Job Dispatch Ordering
          </label>
          <select
            id="ordering-select"
            value={config.ordering}
            onChange={(e) =>
              onChange({ ...config, ordering: e.target.value as 'earliest_arrival' | 'least_slack' })
            }
            className="p-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-800 text-xs font-medium focus:ring-2 focus:ring-emerald-500"
          >
            <option value="earliest_arrival">Earliest-Arrival-First (FIFO Priority)</option>
            <option value="least_slack">Least-Deadline-Slack-First (SLA Urgency)</option>
          </select>
          <span className="text-[10px] text-slate-400">
            Evaluation queue sorting order prior to slot allocation.
          </span>
        </div>

        {/* Resource Capacity Cap */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="capacity-cap" className="font-semibold text-slate-700">
              Resource Capacity Limit
            </label>
            <span className="font-mono font-bold text-slate-800">
              {config.capacityLimit} GPUs
            </span>
          </div>
          <input
            id="capacity-cap"
            type="number"
            min="2"
            max="64"
            step="2"
            value={config.capacityLimit}
            onChange={(e) =>
              onChange({ ...config, capacityLimit: Math.max(2, parseInt(e.target.value, 10)) })
            }
            className="p-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-800 font-mono text-xs focus:ring-2 focus:ring-emerald-500"
          />
          <span className="text-[10px] text-slate-400">
            Maximum concurrent accelerator nodes dispatched in any discrete interval.
          </span>
        </div>

        {/* Forecast-Error Scale (Simulation Control) */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <label htmlFor="forecast-scale" className="font-semibold text-slate-700">
                Forecast-Error Scale
              </label>
              <span className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase bg-amber-100 text-amber-800">
                Simulation Control
              </span>
            </div>
            <span className="font-mono font-bold text-amber-700">
              {config.forecastErrorScale.toFixed(1)}×
            </span>
          </div>
          <input
            id="forecast-scale"
            type="range"
            min="0.5"
            max="3.0"
            step="0.1"
            value={config.forecastErrorScale}
            onChange={(e) =>
              onChange({ ...config, forecastErrorScale: parseFloat(e.target.value) })
            }
            className="w-full accent-amber-600 cursor-pointer"
          />
          <span className="text-[10px] text-slate-400">
            Simulates forecast variance. Labeled as simulation control, not real confidence measurement.
          </span>
        </div>

        {/* Temporal Slot Resolution */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="slot-res" className="font-semibold text-slate-700">
            Slot Temporal Resolution
          </label>
          <input
            id="slot-res"
            type="text"
            readOnly
            value="15 Minutes (Fixed by CAISO-Z2 trace)"
            className="p-2 rounded-lg border border-slate-200 bg-slate-100 text-slate-500 font-mono text-xs cursor-not-allowed"
          />
          <span className="text-[10px] text-slate-400">
            Respects the source trace actual temporal resolution without interpolation artifacts.
          </span>
        </div>
      </div>
    </div>
  );
};
