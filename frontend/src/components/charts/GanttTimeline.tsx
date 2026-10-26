import React, { useState, useEffect } from 'react';
import { Calendar, Shield } from 'lucide-react';
import { Job, TracePoint } from '../../types';
import { formatMinutes } from '../../utils/metrics';
import { StatusBadge } from '../common/StatusBadge';

interface GanttTimelineProps {
  jobs: Job[];
  trace: TracePoint[];
  capacityLimit?: number;
  onJobSelect?: (job: Job) => void;
}

export const GanttTimeline: React.FC<GanttTimelineProps> = ({
  jobs = [],
  trace = [],
  capacityLimit = 16,
  onJobSelect,
}) => {
  const [selectedJob, setSelectedJob] = useState<Job | null>(jobs[0] || null);

  useEffect(() => {
    if (jobs && jobs.length > 0) {
      if (!selectedJob || !jobs.some((j) => j.id === selectedJob.id)) {
        setSelectedJob(jobs[0]);
      }
    } else {
      setSelectedJob(null);
    }
  }, [jobs]);

  // Time grid from 06:00 (360m) to 24:00 (1440m) = 1080m (18 hours)
  const gridStartMin = 360;
  const gridEndMin = 1440;
  const totalGridMin = gridEndMin - gridStartMin;

  const getPositionPercent = (min: number) => {
    const clamped = Math.max(gridStartMin, Math.min(gridEndMin, min));
    return ((clamped - gridStartMin) / totalGridMin) * 100;
  };

  const getWidthPercent = (durationMin: number) => {
    return (durationMin / totalGridMin) * 100;
  };

  // Hour markers: 06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00, 24:00
  const hourMarkers = [360, 480, 600, 720, 840, 960, 1080, 1200, 1320, 1440];

  if (!jobs || jobs.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-xs flex flex-col items-center justify-center text-center">
        <Calendar className="w-8 h-8 text-slate-300 mb-2" />
        <h4 className="text-sm font-semibold text-slate-800">No Scheduled Jobs to Display</h4>
        <p className="text-xs text-slate-400 mt-1">Submit a job or adjust search filters to view execution timelines.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col gap-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Workload Dispatch Timeline (Gantt)</h3>
          <p className="text-xs text-slate-500">
            Resource reservation, arrival boundaries, scheduled windows, and hard SLA deadlines (Max {capacityLimit} GPUs)
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-xs bg-emerald-600" />
            <span className="text-slate-600 font-medium">Optimal Window</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full border border-red-500 bg-red-50" />
            <span className="text-slate-600 font-medium">Hard SLA Deadline</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-xs bg-slate-300" />
            <span className="text-slate-600 font-medium">Earliest Arrival</span>
          </div>
        </div>
      </div>

      {/* Main Gantt Canvas Container */}
      <div className="overflow-x-auto">
        <div className="min-w-[700px] flex flex-col gap-2">
          {/* Timeline Grid Header (Hour Markers) */}
          <div className="relative h-6 border-b border-slate-200 ml-48">
            {hourMarkers.map((min) => {
              const leftPercent = getPositionPercent(min);
              const hour = Math.floor(min / 60);
              const label = `${hour.toString().padStart(2, '0')}:00`;
              return (
                <div
                  key={min}
                  style={{ left: `${leftPercent}%` }}
                  className="absolute -translate-x-1/2 text-[10px] font-mono font-medium text-slate-400 select-none"
                >
                  {label}
                </div>
              );
            })}
          </div>

          {/* Marginal Carbon Heat Strip */}
          <div className="flex items-center gap-2 text-xs py-1">
            <span className="w-48 shrink-0 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Grid Intensity Heat Strip
            </span>
            <div className="relative h-4 rounded-md overflow-hidden flex bg-slate-100 flex-1">
              {trace
                .filter((p) => (p.timestampMinutes ?? p.timeMinutes ?? 0) >= gridStartMin && (p.timestampMinutes ?? p.timeMinutes ?? 0) < gridEndMin)
                .map((pt, _, arr) => {
                  const widthPct = 100 / (arr.length || 1);
                  const intensity = pt.intensity ?? pt.realizedIntensity ?? pt.predictedMu ?? 200;
                  // Low: <100 (green), Mid: 100-200 (yellow-green), High: >200 (amber/orange)
                  const bgColor =
                    intensity < 100
                      ? '#16A34A'
                      : intensity < 180
                      ? '#65A30D'
                      : intensity < 240
                      ? '#D97706'
                      : '#DC2626';

                  return (
                    <div
                      key={pt.time}
                      style={{ width: `${widthPct}%`, backgroundColor: bgColor }}
                      className="h-full hover:opacity-80 transition-opacity"
                      title={`${pt.time}: ${intensity} gCO₂e/kWh`}
                    />
                  );
                })}
            </div>
          </div>

          {/* Job Bars */}
          <div className="flex flex-col gap-2.5 pt-2">
            {jobs.map((job) => {
              const arrival = job.arrivalMinutes ?? job.arrivalMin ?? 0;
              const deadline = job.deadlineMinutes ?? job.deadlineMin ?? 1440;
              const start = job.scheduledStartMinutes ?? job.scheduledStartMin ?? arrival;
              const duration = job.durationMinutes ?? job.durationMin ?? 60;
              const gpus = job.resourceRequirement ?? job.gpus ?? 4;

              const arrivalLeft = getPositionPercent(arrival);
              const deadlineLeft = getPositionPercent(deadline);
              const startLeft = getPositionPercent(start);
              const durationWidth = getWidthPercent(duration);
              const isSelected = selectedJob?.id === job.id;

              return (
                <div
                  key={job.id}
                  onClick={() => {
                    setSelectedJob(job);
                    if (onJobSelect) onJobSelect(job);
                  }}
                  className={`relative h-11 rounded-lg border p-1 transition-all cursor-pointer flex items-center ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-400'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  {/* Job meta on left */}
                  <div className="w-48 shrink-0 flex flex-col justify-center px-2 z-10">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] font-bold font-mono text-slate-900 truncate">
                        #{job.id}
                      </span>
                      <StatusBadge status={job.status} />
                    </div>
                    <span className="text-[10px] text-slate-500 truncate" title={job.name}>
                      {job.name} ({gpus} GPUs)
                    </span>
                  </div>

                  {/* Interactive Gantt Bar Track */}
                  <div className="relative flex-1 h-full flex items-center">
                    {/* Arrival point indicator */}
                    <div
                      className="absolute w-px h-6 bg-slate-400 -translate-x-1/2 z-10"
                      style={{ left: `${arrivalLeft}%` }}
                      title={`Arrival: ${job.arrivalTime || formatMinutes(arrival)}`}
                    />

                    {/* Hard deadline marker */}
                    <div
                      className="absolute w-px h-6 bg-red-500 -translate-x-1/2 z-10"
                      style={{ left: `${deadlineLeft}%` }}
                      title={`Deadline: ${job.deadline || formatMinutes(deadline)}`}
                    >
                      <div className="w-2 h-2 rounded-full bg-red-500 -translate-x-1/2 -mt-1" />
                    </div>

                    {/* Queue Delay line if deferred */}
                    {(job.queueDelayMinutes || 0) > 0 && (
                      <div
                        className="absolute h-1 bg-dashed border-b border-dashed border-slate-300"
                        style={{
                          left: `${arrivalLeft}%`,
                          width: `${Math.max(0, startLeft - arrivalLeft)}%`,
                        }}
                      />
                    )}

                    {/* Scheduled Execution Window Block */}
                    <div
                      className={`absolute h-7 rounded-md flex items-center justify-between px-2 text-[10px] font-bold text-white shadow-xs transition-all ${
                        job.feasible === false
                          ? 'bg-red-500 hover:bg-red-600'
                          : 'bg-emerald-600 hover:bg-emerald-700'
                      }`}
                      style={{
                        left: `${startLeft}%`,
                        width: `${Math.max(4, durationWidth)}%`,
                      }}
                      title={`${job.name}: ${job.scheduledStart || formatMinutes(start)} – ${job.scheduledFinish || formatMinutes(start + duration)}`}
                    >
                      <span className="truncate">{job.scheduledStart || formatMinutes(start)}</span>
                      <span className="truncate hidden md:inline">{job.scheduledFinish || formatMinutes(start + duration)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Selected Job Detail Panel Drawer */}
      {selectedJob && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col gap-3.5 animate-in fade-in duration-150">
          <div className="flex items-start justify-between pb-2 border-b border-slate-200">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold font-mono text-emerald-700">
                  #{selectedJob.id}
                </span>
                <span className="text-xs font-bold text-slate-900">{selectedJob.name}</span>
                <StatusBadge status={selectedJob.status} />
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {selectedJob.resourceLabel || `${selectedJob.resourceRequirement || 4} Accelerator Nodes`} · {selectedJob.type}
              </p>
            </div>

            <div className="text-right">
              <span className="text-[11px] font-mono text-slate-500">
                Slack Margin: <strong>{formatMinutes(selectedJob.deadlineSlackMinutes || 0)}</strong>
              </span>
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex flex-col">
              <span className="text-[10px] text-slate-400 font-semibold uppercase">Scheduled Window</span>
              <span className="font-mono font-bold text-slate-900 mt-0.5">
                {selectedJob.scheduledStart || formatMinutes(selectedJob.scheduledStartMinutes || 0)} – {selectedJob.scheduledFinish || formatMinutes((selectedJob.scheduledStartMinutes || 0) + (selectedJob.durationMinutes || 0))}
              </span>
            </div>

            <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex flex-col">
              <span className="text-[10px] text-slate-400 font-semibold uppercase">Predicted Carbon</span>
              <span className="font-mono font-bold text-emerald-700 mt-0.5">
                {selectedJob.predictedIntensity || 93} gCO₂e/kWh
              </span>
            </div>

            <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex flex-col">
              <span className="text-[10px] text-slate-400 font-semibold uppercase">Queue Delay</span>
              <span className="font-mono font-bold text-slate-900 mt-0.5">
                {formatMinutes(selectedJob.queueDelayMinutes || 0)}
              </span>
            </div>

            <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex flex-col">
              <span className="text-[10px] text-slate-400 font-semibold uppercase">Emissions Avoided</span>
              <span className="font-mono font-bold text-emerald-600 mt-0.5">
                −{selectedJob.avoidedEmissionsKg || 0} kgCO₂e
              </span>
            </div>
          </div>

          {/* Traceable Solver Decision Explanation */}
          {(selectedJob.explanation || selectedJob.delayRationale) && (
            <div className="p-3 bg-white rounded-lg border border-slate-200 flex items-start gap-2.5 text-xs">
              <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <div className="flex flex-col">
                <span className="font-bold text-slate-900">Solver Decision Rationale:</span>
                <p className="text-slate-600 leading-relaxed mt-0.5">{selectedJob.explanation || selectedJob.delayRationale}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
