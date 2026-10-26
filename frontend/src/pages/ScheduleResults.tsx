import React, { useState, useEffect, useMemo } from 'react';
import {
  Download,
  Search,
  Calendar,
  Sparkles,
  CheckCircle2,
  Clock,
  FileSpreadsheet,
  FileCode,
  Layers,
  ChevronDown
} from 'lucide-react';
import { GanttTimeline } from '../components/charts/GanttTimeline';
import { SchedulerConfigPanel } from '../components/scheduler/SchedulerConfigPanel';
import { MetricCard } from '../components/common/MetricCard';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import { Job, SchedulerConfig, TracePoint, TraceMetadata } from '../types';
import { getCarbonTrace } from '../services/api';
import { mockJobs, initialSchedulerConfig, mockTrace, mockTraceMetadata } from '../data/mockData';
import { solveJobsSchedule } from '../utils/scheduler';
import {
  computeEmissionsKg,
  computeAvoidedKg,
  computeReductionPct,
  formatMinutes
} from '../utils/metrics';

export const ScheduleResults: React.FC = () => {
  const [trace, setTrace] = useState<TracePoint[]>(mockTrace);
  const [traceMeta, setTraceMeta] = useState<TraceMetadata>(mockTraceMetadata);
  const [jobs, setJobs] = useState<Job[]>(mockJobs);
  const [config, setConfig] = useState<SchedulerConfig>(initialSchedulerConfig);
  const [isSolving, setIsSolving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'delayed' | 'immediate'>('all');
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [lastSolvedAt, setLastSolvedAt] = useState<string>('Initial demo solution');

  // Load trace on mount and solve initial
  useEffect(() => {
    async function loadData() {
      try {
        const { trace: loadedTrace, metadata } = await getCarbonTrace();
        const safeTrace = loadedTrace && loadedTrace.length > 0 ? loadedTrace : mockTrace;
        setTrace(safeTrace);
        setTraceMeta(metadata || mockTraceMetadata);
        const solved = solveJobsSchedule(mockJobs, safeTrace, initialSchedulerConfig);
        setJobs(solved.jobs || mockJobs);
        setLastSolvedAt(new Date().toLocaleTimeString());
      } catch (err) {
        console.warn('Failed to load schedule trace, using fallback:', err);
        setTrace(mockTrace);
        setTraceMeta(mockTraceMetadata);
        const solved = solveJobsSchedule(mockJobs, mockTrace, initialSchedulerConfig);
        setJobs(solved.jobs || mockJobs);
        setLastSolvedAt(new Date().toLocaleTimeString());
      }
    }
    loadData();
  }, []);

  const handleRunScheduler = () => {
    setIsSolving(true);
    setTimeout(() => {
      try {
        const safeTrace = trace && trace.length > 0 ? trace : mockTrace;
        const solved = solveJobsSchedule(jobs, safeTrace, config);
        setJobs(solved.jobs || jobs);
        setLastSolvedAt(new Date().toLocaleTimeString());
      } catch (err) {
        console.error('Scheduler resolution failed:', err);
      } finally {
        setIsSolving(false);
      }
    }, 350);
  };

  const handleConfigChange = (newConfig: SchedulerConfig) => {
    setConfig(newConfig);
  };

  // Filtered jobs for display
  const filteredJobs = useMemo(() => {
    return (jobs || []).filter((j) => {
      const matchesSearch =
        (j.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (j.id || '').toLowerCase().includes(searchQuery.toLowerCase());
      if (!matchesSearch) return false;

      const arrival = j.arrivalMinutes ?? j.arrivalMin ?? 0;
      const scheduledStart = j.scheduledStartMinutes ?? j.scheduledStartMin ?? arrival;
      const delayed = scheduledStart > arrival;

      if (statusFilter === 'delayed') return delayed;
      if (statusFilter === 'immediate') return !delayed;
      return true;
    });
  }, [jobs, searchQuery, statusFilter]);

  // Derived Metrics
  const summaryMetrics = useMemo(() => {
    let fifoTotalKg = 0;
    let realizedTotalKg = 0;
    let totalWaitMin = 0;
    let slaMet = 0;
    let delayedCount = 0;

    const currentJobs = jobs || [];
    const currentTrace = trace || [];

    currentJobs.forEach((j) => {
      const arrival = j.arrivalMinutes ?? j.arrivalMin ?? 0;
      const scheduledStart = j.scheduledStartMinutes ?? j.scheduledStartMin ?? arrival;
      const duration = j.durationMinutes ?? j.durationMin ?? 60;
      const deadline = j.deadlineMinutes ?? j.deadlineMin ?? 1440;
      const energyKwh = j.energyKwh ?? ((j.powerWatts ?? 1000) / 1000) * (duration / 60);

      // Realized scheduled intensity
      const scheduledPt = currentTrace.find((t) => (t.timestampMinutes ?? t.timeMinutes ?? 0) >= scheduledStart);
      const scheduledIntensity = scheduledPt?.intensity ?? scheduledPt?.realizedIntensity ?? scheduledPt?.predictedMu ?? 250;
      const scheduledEmissions = computeEmissionsKg(energyKwh, scheduledIntensity);
      realizedTotalKg += scheduledEmissions;

      // FIFO (immediate dispatch) intensity
      const fifoPt = currentTrace.find((t) => (t.timestampMinutes ?? t.timeMinutes ?? 0) >= arrival);
      const fifoIntensity = fifoPt?.intensity ?? fifoPt?.realizedIntensity ?? fifoPt?.predictedMu ?? 250;
      const fifoEmissions = computeEmissionsKg(energyKwh, fifoIntensity);
      fifoTotalKg += fifoEmissions;

      // Waiting time
      const wait = Math.max(0, scheduledStart - arrival);
      totalWaitMin += wait;
      if (wait > 0) delayedCount++;

      // SLA
      const finishMin = scheduledStart + duration;
      if (finishMin <= deadline) slaMet++;
    });

    const avoidedKg = Math.max(0, fifoTotalKg - realizedTotalKg);
    const reductionPct = computeReductionPct(fifoTotalKg, realizedTotalKg);
    const avgWaitMin = currentJobs.length > 0 ? Math.round(totalWaitMin / currentJobs.length) : 0;
    const slaPercent = currentJobs.length > 0 ? Math.round((slaMet / currentJobs.length) * 100) : 100;

    return {
      avoidedKg,
      reductionPct,
      realizedTotalKg,
      avgWaitMin,
      slaPercent,
      delayedCount,
      totalJobs: currentJobs.length,
    };
  }, [jobs, trace]);

  // Export handlers
  const handleExportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(jobs, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `carbonova-schedule-${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    setExportMenuOpen(false);
  };

  const handleExportCSV = () => {
    const headers = ['ID', 'Name', 'Arrival', 'ScheduledStart', 'Deadline', 'DurationMin', 'GPUs', 'EnergyKwh', 'Rationale'];
    const rows = (jobs || []).map((j) => {
      const arr = j.arrivalMinutes ?? j.arrivalMin ?? 0;
      const start = j.scheduledStartMinutes ?? j.scheduledStartMin ?? arr;
      const dead = j.deadlineMinutes ?? j.deadlineMin ?? 1440;
      const dur = j.durationMinutes ?? j.durationMin ?? 60;
      const gpus = j.resourceRequirement ?? j.gpus ?? 4;
      const energy = j.energyKwh ?? 100;
      const rationale = j.explanation ?? j.delayRationale ?? 'Dispatched on arrival';
      return [
        j.id,
        `"${j.name}"`,
        formatMinutes(arr),
        formatMinutes(start),
        formatMinutes(dead),
        dur,
        gpus,
        energy,
        `"${rationale}"`,
      ];
    });
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', encodeURI(csvContent));
    downloadAnchor.setAttribute('download', `carbonova-schedule-${Date.now()}.csv`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    setExportMenuOpen(false);
  };

  const reductionText =
    typeof summaryMetrics.reductionPct === 'number'
      ? `${summaryMetrics.reductionPct.toFixed(1)}% savings`
      : 'N/A';

  const isPositiveSavings =
    typeof summaryMetrics.reductionPct === 'number' && summaryMetrics.reductionPct > 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Top Banner / Heading */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-slate-900">Workload Schedule Results</h1>
            <ProvenanceBadge type="tool_estimated" />
          </div>
          <p className="text-xs text-slate-500">
            Heuristic dispatch plan computed using risk-penalized forecast bounds ({traceMeta?.region || 'CAISO-Z2'})
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <span className="text-[11px] text-slate-400 block">Last Recomputed</span>
            <span className="text-xs font-semibold text-slate-700">{lastSolvedAt}</span>
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={() => setExportMenuOpen(!exportMenuOpen)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-xs transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              <span>Export Schedule</span>
              <ChevronDown className="w-3 h-3 text-slate-400" />
            </button>

            {exportMenuOpen && (
              <div className="absolute right-0 mt-1 w-44 bg-white border border-slate-200 rounded-lg shadow-lg z-20 py-1 text-xs">
                <button
                  type="button"
                  onClick={handleExportJSON}
                  className="flex items-center gap-2 w-full px-3 py-2 text-slate-700 hover:bg-slate-50 text-left"
                >
                  <FileCode className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Export as JSON</span>
                </button>
                <button
                  type="button"
                  onClick={handleExportCSV}
                  className="flex items-center gap-2 w-full px-3 py-2 text-slate-700 hover:bg-slate-50 text-left"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Export as CSV</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Avoided Emissions"
          value={summaryMetrics.avoidedKg.toFixed(2)}
          unit="kgCO₂e"
          icon={<Sparkles className="w-4 h-4" />}
          change={reductionText}
          isPositive={isPositiveSavings}
          tooltipText="Emissions avoided by shifting workloads to low-carbon windows compared to baseline FIFO dispatch."
          provenanceType="tool_estimated"
        />

        <MetricCard
          title="Realized Emissions"
          value={summaryMetrics.realizedTotalKg.toFixed(2)}
          unit="kgCO₂e"
          icon={<Layers className="w-4 h-4" />}
          tooltipText="Total realized carbon emitted across all scheduled batch workloads."
          provenanceType="measured"
        />

        <MetricCard
          title="Average Waiting Time"
          value={summaryMetrics.avgWaitMin}
          unit="minutes"
          icon={<Clock className="w-4 h-4" />}
          tooltipText="Mean postponement duration across jobs intentionally deferred for greener energy windows."
          provenanceType="tool_estimated"
        />

        <MetricCard
          title="SLA Attainment"
          value={`${summaryMetrics.slaPercent}%`}
          unit={`${summaryMetrics.totalJobs} jobs`}
          icon={<CheckCircle2 className="w-4 h-4" />}
          isPositive={summaryMetrics.slaPercent === 100}
          tooltipText="Percentage of submitted jobs whose scheduled completion falls before their configured deadline."
          provenanceType="measured"
        />
      </div>

      {/* Gantt Timeline View */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-bold text-slate-900">Interactive Dispatch Gantt & Heat Strip</h2>
          </div>
          <span className="text-xs text-slate-500 font-medium">Click any job bar to inspect dispatch rationale</span>
        </div>

        <GanttTimeline
          jobs={filteredJobs}
          trace={trace}
          capacityLimit={config.capacityLimit}
        />
      </div>

      {/* Scheduler Configuration & Sliders */}
      <div className="flex flex-col gap-3">
        <SchedulerConfigPanel
          config={config}
          onChange={handleConfigChange}
          onRun={handleRunScheduler}
          isSolving={isSolving}
        />
      </div>

      {/* Filter and Table List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Scheduled Jobs Registry ({filteredJobs.length})</h3>
            <p className="text-xs text-slate-500">
              Detailed dispatch times, carbon window assignments, and heuristic justification
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Search */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search job name or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* Filter */}
            <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg text-xs font-semibold text-slate-600">
              <button
                type="button"
                onClick={() => setStatusFilter('all')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  statusFilter === 'all' ? 'bg-white text-slate-900 shadow-xs' : 'hover:text-slate-900'
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter('delayed')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  statusFilter === 'delayed' ? 'bg-white text-slate-900 shadow-xs' : 'hover:text-slate-900'
                }`}
              >
                Carbon Shifted ({summaryMetrics.delayedCount})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter('immediate')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  statusFilter === 'immediate' ? 'bg-white text-slate-900 shadow-xs' : 'hover:text-slate-900'
                }`}
              >
                Immediate ({summaryMetrics.totalJobs - summaryMetrics.delayedCount})
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 font-semibold">
                <th className="py-2.5 px-3">Job ID & Name</th>
                <th className="py-2.5 px-3">Arrival</th>
                <th className="py-2.5 px-3">Scheduled Start</th>
                <th className="py-2.5 px-3">Duration</th>
                <th className="py-2.5 px-3">Deadline</th>
                <th className="py-2.5 px-3">Waiting Time</th>
                <th className="py-2.5 px-3">Resources</th>
                <th className="py-2.5 px-3">Dispatch Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredJobs.map((job) => {
                const arr = job.arrivalMinutes ?? job.arrivalMin ?? 0;
                const start = job.scheduledStartMinutes ?? job.scheduledStartMin ?? arr;
                const dead = job.deadlineMinutes ?? job.deadlineMin ?? 1440;
                const dur = job.durationMinutes ?? job.durationMin ?? 60;
                const gpus = job.resourceRequirement ?? job.gpus ?? 4;
                const energy = job.energyKwh ?? 100;
                const rationale = job.explanation ?? job.delayRationale ?? 'Dispatched immediately on arrival';
                const waitMin = Math.max(0, start - arr);
                const isDelayed = waitMin > 0;

                return (
                  <tr key={job.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-900">{job.name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{job.id}</div>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-600">{formatMinutes(arr)}</td>
                    <td className="py-2.5 px-3 font-mono">
                      <span className={isDelayed ? 'font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-sm' : 'text-slate-700'}>
                        {formatMinutes(start)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">{dur} min</td>
                    <td className="py-2.5 px-3 font-mono text-slate-600">{formatMinutes(dead)}</td>
                    <td className="py-2.5 px-3">
                      {isDelayed ? (
                        <span className="text-emerald-700 font-semibold">+{waitMin} min</span>
                      ) : (
                        <span className="text-slate-400">0 min (immediate)</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">
                      {gpus} GPU{gpus > 1 ? 's' : ''} ({energy} kWh)
                    </td>
                    <td className="py-2.5 px-3 max-w-xs text-slate-600 truncate" title={rationale}>
                      {rationale}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
