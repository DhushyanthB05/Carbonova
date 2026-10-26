import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { PolicyComparisonResult } from '../../types';

interface PolicyComparisonChartProps {
  data: PolicyComparisonResult[];
}

export const PolicyComparisonChart: React.FC<PolicyComparisonChartProps> = ({ data = [] }) => {
  const chartData = (data || []).map((p) => ({
    name: (p.policyName || '').split(' ')[0],
    fullName: p.policyName || '',
    predictedSavings: p.predictedSavingsKg || 0,
    realizedSavings: p.realizedSavingsKg || 0,
    totalEmissions: p.totalRealizedEmissionsKg || 0,
    color: p.color || '#16A34A',
  }));

  if (chartData.length === 0) {
    return (
      <div className="h-[280px] w-full flex items-center justify-center text-slate-400 text-xs">
        No benchmark policy results available to compare.
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs text-slate-500 pb-2 border-b border-slate-100">
        <div>
          <span className="font-bold text-slate-900">Predicted vs. Realized Emissions Avoided (kgCO₂e)</span>
          <p className="text-[11px] text-slate-500">
            Higher realized bar indicates superior net carbon avoidance
          </p>
        </div>
        <span className="font-mono text-[11px] text-slate-400">Baseline = FIFO (0 kg savings)</span>
      </div>

      <div className="h-[280px] w-full pt-2 min-h-[220px]">
        <ResponsiveContainer width="100%" height="100%" minHeight={220}>
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
            <XAxis
              dataKey="name"
              axisLine={{ stroke: '#E2E8F0' }}
              tickLine={false}
              tick={{ fontSize: 11, fill: '#64748B' }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: '#64748B' }}
              unit=" kg"
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || payload.length === 0) return null;
                const d = payload[0].payload;
                return (
                  <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-lg text-xs flex flex-col gap-1.5 min-w-[200px]">
                    <span className="font-bold text-slate-900 border-b border-slate-100 pb-1">
                      {d.fullName}
                    </span>
                    <div className="flex justify-between text-slate-600">
                      <span>Realized Avoided:</span>
                      <span className="font-mono font-bold text-emerald-700">
                        {d.realizedSavings.toFixed(1)} kgCO₂e
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Predicted Avoided:</span>
                      <span className="font-mono font-bold text-slate-700">
                        {d.predictedSavings.toFixed(1)} kgCO₂e
                      </span>
                    </div>
                    <div className="flex justify-between text-slate-500 pt-1 border-t border-slate-100 text-[10px]">
                      <span>Total Realized Emissions:</span>
                      <span className="font-mono font-bold">{d.totalEmissions.toFixed(1)} kg</span>
                    </div>
                  </div>
                );
              }}
            />
            <Legend
              verticalAlign="top"
              align="right"
              iconType="circle"
              wrapperStyle={{ fontSize: 11, paddingBottom: 10 }}
            />
            <Bar
              dataKey="predictedSavings"
              name="Predicted Avoided (kg)"
              fill="#A7F3D0"
              radius={[4, 4, 0, 0]}
            />
            <Bar
              dataKey="realizedSavings"
              name="Realized Avoided (kg)"
              fill="#16A34A"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
