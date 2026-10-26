import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { TracePoint, TraceMetadata } from '../../types';
import { Activity } from 'lucide-react';

interface CarbonIntensityChartProps {
  trace: TracePoint[];
  metadata?: TraceMetadata | null;
  selectedTime?: string;
  dispatchWindow?: { start: string; end: string };
  height?: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
  sourceType?: string;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({
  active,
  payload,
  label,
  sourceType = 'recorded',
}) => {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-lg text-xs flex flex-col gap-1.5 min-w-[200px]">
      <div className="flex items-center justify-between pb-1.5 border-b border-slate-100">
        <span className="font-bold text-slate-900 font-mono">{label} PST</span>
        <span className="text-[10px] font-medium text-slate-400 capitalize">{sourceType}</span>
      </div>

      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center justify-between gap-3 py-0.5">
          <div className="flex items-center gap-1.5">
            <span
              className="w-2.5 h-2.5 rounded-sm shrink-0"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-slate-600 font-medium">{entry.name}:</span>
          </div>
          <span className="font-mono font-bold text-slate-900">
            {entry.value} <span className="text-[10px] text-slate-500 font-normal">gCO₂e/kWh</span>
          </span>
        </div>
      ))}
    </div>
  );
};

export const CarbonIntensityChart: React.FC<CarbonIntensityChartProps> = ({
  trace,
  metadata,
  selectedTime,
  dispatchWindow,
  height = 300,
}) => {
  const safeTrace = trace || [];

  if (safeTrace.length === 0) {
    return (
      <div
        style={{ height: `${height}px` }}
        className="w-full flex flex-col items-center justify-center bg-slate-50/50 rounded-xl border border-dashed border-slate-200 text-slate-400 text-xs gap-2"
      >
        <Activity className="w-5 h-5 animate-pulse text-emerald-500" />
        <span>Loading or awaiting grid carbon telemetry trace...</span>
      </div>
    );
  }

  const chartData = safeTrace.map((p) => {
    const mu = p.predictedMu ?? p.forecastMean ?? p.intensity ?? 0;
    const sigma = p.sigma ?? p.forecastSigma ?? 0;
    const intensity = p.intensity ?? p.realizedIntensity ?? mu;
    return {
      time: p.time,
      realized: intensity,
      forecast: mu,
      upperBound: mu + sigma,
      lowerBound: Math.max(0, mu - sigma),
      solarPct: p.solarPct || 0,
      windPct: p.windPct || 0,
    };
  });

  const regionLabel = metadata?.region || 'CAISO-Z2 (California Regional Grid)';
  const unitsLabel = metadata?.units || 'gCO₂e/kWh';
  const sourceTypeLabel = metadata?.sourceType || 'recorded';

  return (
    <div className="w-full flex flex-col gap-2">
      {/* Legend & Meta bar */}
      <div className="flex flex-wrap items-center justify-between text-xs text-slate-500 pb-2 border-b border-slate-100">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-xs bg-emerald-600" />
            <span className="font-medium text-slate-700">Realized Intensity</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-xs bg-emerald-300" />
            <span className="font-medium text-slate-700">Forecast Mean (μ̂)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-xs bg-emerald-100 border border-emerald-300" />
            <span className="font-medium text-slate-700">Uncertainty Band (±σ̂)</span>
          </div>
        </div>

        <div className="font-mono text-[11px] text-slate-400">
          {regionLabel} · {unitsLabel}
        </div>
      </div>

      {/* Chart Canvas */}
      <div style={{ height: `${height}px` }} className="w-full pt-2 min-h-[220px]">
        <ResponsiveContainer width="100%" height="100%" minHeight={220}>
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <defs>
              <linearGradient id="realizedGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#16A34A" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#16A34A" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="bandGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#86EFAC" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#86EFAC" stopOpacity={0.05} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />

            <XAxis
              dataKey="time"
              axisLine={{ stroke: '#E2E8F0' }}
              tickLine={false}
              tick={{ fontSize: 11, fill: '#64748B' }}
              interval="preserveStartEnd"
            />

            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: '#64748B' }}
              domain={[0, 'auto']}
              unit=""
            />

            <Tooltip
              content={<CustomTooltip sourceType={sourceTypeLabel} />}
              cursor={{ stroke: '#CBD5E1', strokeWidth: 1, strokeDasharray: '3 3' }}
            />

            {/* Time Machine Playback Time marker */}
            {selectedTime && (
              <ReferenceLine
                x={selectedTime}
                stroke="#DC2626"
                strokeWidth={2}
                label={{
                  value: `Playback: ${selectedTime}`,
                  position: 'top',
                  fill: '#DC2626',
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />
            )}

            {/* Scheduled Dispatch window reference */}
            {dispatchWindow && (
              <ReferenceLine
                x={dispatchWindow.start}
                stroke="#16A34A"
                strokeDasharray="4 4"
                strokeWidth={2}
                label={{
                  value: 'Dispatch Start',
                  position: 'insideTopLeft',
                  fill: '#16A34A',
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />
            )}

            {/* Uncertainty Band Upper Bound */}
            <Area
              type="monotone"
              dataKey="upperBound"
              name="Upper Bound (μ̂ + σ̂)"
              stroke="#86EFAC"
              strokeDasharray="3 3"
              fill="url(#bandGradient)"
            />

            {/* Realized Curve */}
            <Area
              type="monotone"
              dataKey="realized"
              name="Realized Intensity"
              stroke="#16A34A"
              strokeWidth={2.5}
              fill="url(#realizedGradient)"
            />

            {/* Forecast Mean Line */}
            <Area
              type="monotone"
              dataKey="forecast"
              name="Forecast Mean (μ̂)"
              stroke="#65A30D"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              fill="none"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
