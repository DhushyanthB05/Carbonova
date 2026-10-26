import React from 'react';
import { LucideIcon } from 'lucide-react';
import { ProvenanceType } from '../../types';
import { ProvenanceBadge } from './ProvenanceBadge';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  explanatoryLabel?: string;
  icon: LucideIcon | React.ComponentType<{ className?: string }> | React.ReactNode;
  comparison?: {
    text: string;
    positive?: boolean;
    baselineName?: string;
  } | null;
  change?: string;
  isPositive?: boolean;
  tooltip?: string;
  tooltipText?: string;
  highlight?: boolean;
  provenanceType?: ProvenanceType;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  explanatoryLabel,
  icon,
  comparison,
  change,
  isPositive,
  tooltip,
  tooltipText,
  highlight = false,
  provenanceType,
}) => {
  const finalTooltip = tooltip || tooltipText || '';
  const finalComparison = comparison || (change ? { text: change, positive: isPositive } : null);

  const renderIcon = () => {
    if (!icon) return null;
    if (React.isValidElement(icon)) {
      return icon;
    }
    if (typeof icon === 'function' || (typeof icon === 'object' && icon !== null)) {
      const IconComponent = icon as React.ComponentType<{ className?: string }>;
      return <IconComponent className="w-4 h-4" />;
    }
    return null;
  };

  return (
    <div
      className={`bg-white rounded-xl p-5 border transition-all duration-150 flex flex-col justify-between ${
        highlight
          ? 'border-emerald-300 ring-1 ring-emerald-100 shadow-sm'
          : 'border-slate-200 shadow-xs hover:border-slate-300'
      }`}
      title={finalTooltip}
    >
      <div>
        {/* Header */}
        <div className="flex items-center justify-between text-slate-500 mb-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-600">
              {title}
            </span>
            {provenanceType && <ProvenanceBadge type={provenanceType} />}
          </div>
          <div
            className={`p-1.5 rounded-lg ${
              highlight ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-50 text-slate-400'
            }`}
          >
            {renderIcon()}
          </div>
        </div>

        {/* Value & Unit */}
        <div className="flex items-baseline gap-1.5 my-1">
          <span
            className={`text-2xl font-bold tracking-tight font-sans ${
              highlight ? 'text-emerald-700' : 'text-slate-900'
            }`}
          >
            {value}
          </span>
          {unit && <span className="text-xs text-slate-500 font-medium">{unit}</span>}
        </div>

        {/* Subline */}
        {explanatoryLabel && (
          <p className="text-[11px] text-slate-500 leading-normal line-clamp-1">
            {explanatoryLabel}
          </p>
        )}
      </div>

      {/* Comparison against baseline */}
      <div className="pt-3 mt-3 border-t border-slate-100 flex items-center justify-between text-[11px]">
        {finalComparison ? (
          <div className="flex items-center gap-1.5">
            <span
              className={`font-semibold ${
                finalComparison.positive
                  ? 'text-emerald-600'
                  : finalComparison.positive === false
                  ? 'text-amber-600'
                  : 'text-slate-600'
              }`}
            >
              {finalComparison.text}
            </span>
            {finalComparison.baselineName && (
              <span className="text-slate-400">vs {finalComparison.baselineName}</span>
            )}
          </div>
        ) : (
          <span className="text-slate-400 italic">No comparison available</span>
        )}
      </div>
    </div>
  );
};
