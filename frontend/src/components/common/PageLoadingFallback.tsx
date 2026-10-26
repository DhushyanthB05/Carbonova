import React from 'react';

export const PageLoadingFallback: React.FC = () => {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center min-h-[360px] w-full p-8 text-center animate-in fade-in duration-200"
    >
      <div className="relative flex items-center justify-center w-12 h-12 mb-3">
        <div className="w-10 h-10 rounded-full border-2 border-emerald-100 border-t-emerald-600 animate-spin" />
        <div className="absolute w-2 h-2 rounded-full bg-emerald-600" />
      </div>
      <p className="text-xs font-semibold text-slate-800 tracking-wide">
        Loading Carbonova Module
      </p>
      <p className="text-[11px] text-slate-400 mt-1">
        Initializing view components and telemetry...
      </p>
    </div>
  );
};

export default PageLoadingFallback;
