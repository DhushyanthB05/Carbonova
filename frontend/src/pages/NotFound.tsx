import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FileQuestion, Home, ArrowLeft, LayoutDashboard, PlusCircle, CalendarCheck, GitCompare, History, BookOpen } from 'lucide-react';

export const NotFound: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-[500px] flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-8 max-w-lg w-full shadow-xs flex flex-col items-center text-center">
        {/* 404 Icon & Badge */}
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-100 text-emerald-700 flex items-center justify-center mb-4">
          <FileQuestion className="w-8 h-8" />
        </div>

        <span className="text-[11px] font-bold uppercase tracking-widest text-emerald-800 bg-emerald-100/70 px-3 py-1 rounded-full mb-3">
          Error 404 · Page Not Found
        </span>

        <h2 className="text-xl font-bold text-slate-900 mb-2">
          Route Does Not Exist
        </h2>

        <p className="text-xs text-slate-500 mb-6 max-w-sm leading-relaxed">
          The requested path could not be located on the Carbonova platform. Check the URL for typographical errors or select one of the valid modules below.
        </p>

        {/* Primary actions */}
        <div className="flex flex-wrap items-center justify-center gap-3 w-full mb-8">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <Home className="w-3.5 h-3.5" />
            <span>Go to Overview</span>
          </button>

          <button
            type="button"
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-slate-400" />
            <span>Go Back</span>
          </button>
        </div>

        {/* Quick Nav Links */}
        <div className="w-full pt-6 border-t border-slate-100 text-left">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-3">
            Quick Navigation
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 text-slate-700 text-left transition-colors"
            >
              <LayoutDashboard className="w-3.5 h-3.5 text-emerald-600" />
              <span>Overview</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/submit-job')}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 text-slate-700 text-left transition-colors"
            >
              <PlusCircle className="w-3.5 h-3.5 text-emerald-600" />
              <span>Submit Job</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/schedule-results')}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 text-slate-700 text-left transition-colors"
            >
              <CalendarCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Schedule Results</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/policy-comparison')}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 text-slate-700 text-left transition-colors"
            >
              <GitCompare className="w-3.5 h-3.5 text-emerald-600" />
              <span>Policy Benchmarks</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/carbon-time-machine')}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 text-slate-700 text-left transition-colors"
            >
              <History className="w-3.5 h-3.5 text-emerald-600" />
              <span>Time Machine</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/methodology')}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 text-slate-700 text-left transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5 text-emerald-600" />
              <span>Methodology</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
