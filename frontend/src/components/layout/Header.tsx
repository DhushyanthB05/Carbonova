import React from 'react';
import { RefreshCw, Server, ShieldCheck, Zap } from 'lucide-react';
import { SystemStatus } from '../../types';

interface HeaderProps {
  title: string;
  subtitle?: string;
  systemStatus: SystemStatus;
  isRefreshing?: boolean;
  onRefresh?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  systemStatus,
  isRefreshing = false,
  onRefresh,
}) => {
  return (
    <header className="sticky top-0 z-30 h-16 bg-white/90 backdrop-blur-md border-b border-slate-200 px-6 flex items-center justify-between">
      {/* Page Title & Context */}
      <div className="flex flex-col min-w-0">
        <h1 className="text-base font-bold text-slate-900 leading-tight truncate">{title}</h1>
        {subtitle && (
          <p className="text-xs text-slate-500 leading-tight truncate hidden sm:block">
            {subtitle}
          </p>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Provenance / Demo Data Pill */}
        {!systemStatus.isOnline && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-200 shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            <span>Demo Data (Simulation)</span>
          </div>
        )}

        {/* Backend Connection Status */}
        <div
          className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border shadow-2xs ${
            systemStatus.isOnline
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-slate-50 text-slate-600 border-slate-200'
          }`}
          title={`Backend status: ${systemStatus.mode} (${systemStatus.core})`}
        >
          <Server className="w-3.5 h-3.5 text-slate-400" />
          <span className="hidden md:inline font-mono text-[11px]">{systemStatus.mode}</span>
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              systemStatus.isOnline ? 'bg-emerald-600' : 'bg-slate-400'
            }`}
          />
        </div>

        {/* Refresh Action */}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors shadow-2xs disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            title="Refresh telemetry stream"
            aria-label="Refresh telemetry stream"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-emerald-600' : ''}`} />
          </button>
        )}
      </div>
    </header>
  );
};
