import React from 'react';
import { ProvenanceType } from '../../types';

interface ProvenanceBadgeProps {
  type: ProvenanceType;
  label?: string;
  className?: string;
}

const BADGE_CONFIG: Record<
  ProvenanceType,
  { label: string; tooltip: string; bg: string; text: string; border: string; dot: string }
> = {
  recorded: {
    label: 'Recorded Grid Carbon',
    tooltip: 'Empirical historical telemetry from official grid ISO monitors (e.g. CAISO OASIS).',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    dot: 'bg-emerald-500',
  },
  live: {
    label: 'Live Grid Feed',
    tooltip: 'Real-time telemetry stream from live grid API connection.',
    bg: 'bg-green-50',
    text: 'text-green-800',
    border: 'border-green-300',
    dot: 'bg-green-500',
  },
  synthetic: {
    label: 'Synthetic Benchmark',
    tooltip: 'Perturbed or synthetically generated curve for scientific sensitivity testing.',
    bg: 'bg-amber-50',
    text: 'text-amber-800',
    border: 'border-amber-200',
    dot: 'bg-amber-500',
  },
  measured: {
    label: 'Measured Energy',
    tooltip: 'Direct hardware telemetry captured via IPMI / NVML power instrumentation.',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
    dot: 'bg-blue-500',
  },
  tool_estimated: {
    label: 'Tool-Estimated Energy',
    tooltip: 'Derived from TDP profiles and benchmark models (e.g. MLPerf / CodeCarbon).',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
    dot: 'bg-indigo-500',
  },
  'tool-estimated': {
    label: 'Tool-Estimated Energy',
    tooltip: 'Derived from TDP profiles and benchmark models (e.g. MLPerf / CodeCarbon).',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
    dot: 'bg-indigo-500',
  },
  assumption_based: {
    label: 'Assumption-Based Model',
    tooltip: 'Heuristic parameters based on workload profile declarations.',
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    dot: 'bg-slate-400',
  },
  'assumption-based': {
    label: 'Assumption-Based Model',
    tooltip: 'Heuristic parameters based on workload profile declarations.',
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    dot: 'bg-slate-400',
  },
};

export const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({
  type,
  label,
  className = '',
}) => {
  const config = BADGE_CONFIG[type] || BADGE_CONFIG.assumption_based;

  return (
    <div
      title={config.tooltip}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border transition-all cursor-help select-none ${config.bg} ${config.text} ${config.border} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${config.dot}`} />
      <span>{label || config.label}</span>
    </div>
  );
};
