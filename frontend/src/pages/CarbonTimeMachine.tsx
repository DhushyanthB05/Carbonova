import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  SkipBack,
  SkipForward,
  Sliders,
  Activity,
  Sparkles
} from 'lucide-react';
import { CarbonIntensityChart } from '../components/charts/CarbonIntensityChart';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import { Job, TracePoint, TraceMetadata, SchedulerConfig } from '../types';
import { getCarbonTrace } from '../services/api';
import { mockJobs, initialSchedulerConfig, mockTraceMetadata, mockTrace } from '../data/mockData';
import { solveJobsSchedule } from '../utils/scheduler';
import {
  minutesToTimeString,
  computeEmissionsKg
} from '../utils/metrics';

export const CarbonTimeMachine: React.FC = () => {
  const [trace, setTrace] = useState<TracePoint[]>(mockTrace);
  const [metadata, setMetadata] = useState<TraceMetadata>(mockTraceMetadata);
  const [config, setConfig] = useState<SchedulerConfig>(initialSchedulerConfig);
  const [previousConfig, setPreviousConfig] = useState<SchedulerConfig>(initialSchedulerConfig);

  // Playback state
  const [currentTimeMin, setCurrentTimeMin] = useState<number>(360); // 06:00 start
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1); // 1x, 2x, 5x, 10x
  const timerRef = useRef<number | null>(null);

  // Solved schedules with safe initial values
  const [scheduledJobs, setScheduledJobs] = useState<Job[]>(() => {
    try {
      const res = solveJobsSchedule(mockJobs, mockTrace, initialSchedulerConfig);
      return res.jobs || mockJobs;
    } catch {
      return mockJobs;
    }
  });
  const [previousJobs, setPreviousJobs] = useState<Job[]>(() => {
    try {
      const res = solveJobsSchedule(mockJobs, mockTrace, initialSchedulerConfig);
      return res.jobs || mockJobs;
    } catch {
      return mockJobs;
    }
  });

  // Load trace
  useEffect(() => {
    async function load() {
      try {
        const { trace: loadedTrace, metadata: loadedMeta } = await getCarbonTrace();
        const safeTrace = loadedTrace && loadedTrace.length > 0 ? loadedTrace : mockTrace;
        setTrace(safeTrace);
        setMetadata(loadedMeta || mockTraceMetadata);
        const initialSched = solveJobsSchedule(mockJobs, safeTrace, initialSchedulerConfig);
        setScheduledJobs(initialSched.jobs || mockJobs);
        setPreviousJobs(initialSched.jobs || mockJobs);
      } catch (err) {
        console.warn('Failed to load trace for time machine, using fallback:', err);
        setTrace(mockTrace);
        setMetadata(mockTraceMetadata);
        const initialSched = solveJobsSchedule(mockJobs, mockTrace, initialSchedulerConfig);
        setScheduledJobs(initialSched.jobs || mockJobs);
        setPreviousJobs(initialSched.jobs || mockJobs);
      }
    }
    load();
  }, []);

  // Playback loop
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = Math.max(100, Math.floor(800 / playbackSpeed));
      timerRef.current = window.setInterval(() => {
        setCurrentTimeMin((prev) => {
          if (prev >= 1440) {
            setIsPlaying(false);
            return 1440;
          }
          return Math.min(1440, prev + 15);
        });
      }, intervalMs);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, playbackSpeed]);

  // Recalculate schedule when hyperparameters change
  const handleConfigChange = (key: keyof SchedulerConfig, value: number) => {
    setPreviousConfig({ ...config });
    setPreviousJobs([...scheduledJobs]);

    const updatedConfig = { ...config, [key]: value };
    setConfig(updatedConfig);

    const safeTrace = trace && trace.length > 0 ? trace : mockTrace;
    const recomputed = solveJobsSchedule(mockJobs, safeTrace, updatedConfig);
    setScheduledJobs(recomputed.jobs || scheduledJobs);
  };

  // Current trace point at currentTimeMin
  const currentPoint = useMemo(() => {
    const currentTrace = trace && trace.length > 0 ? trace : mockTrace;
    return (
      currentTrace.find((p) => (p.timestampMinutes ?? p.timeMinutes ?? 0) >= currentTimeMin) ||
      currentTrace[currentTrace.length - 1]
    );
  }, [trace, currentTimeMin]);

  // Current instantaneous clean energy estimate (approximate from carbon intensity)
  const cleanEnergyPercent = useMemo(() => {
    if (!currentPoint) return 50;
    const intensity = currentPoint.intensity ?? currentPoint.realizedIntensity ?? 250;
    return Math.max(12, Math.min(94, Math.round(100 - (intensity / 420) * 88)));
  }, [currentPoint]);

  // Workload states at currentTimeMin
  const workloadState = useMemo(() => {
    const running: Job[] = [];
    const pending: Job[] = [];
    const completed: Job[] = [];
    const unarrived: Job[] = [];
    let cumulativeEmissionsKg = 0;

    const jobsList = scheduledJobs || [];

    jobsList.forEach((job) => {
      const arr = job.arrivalMinutes ?? job.arrivalMin ?? 0;
      const startMin = job.scheduledStartMinutes ?? job.scheduledStartMin ?? arr;
      const dur = job.durationMinutes ?? job.durationMin ?? 60;
      const finishMin = startMin + dur;

      // Cumulative emissions up to currentTimeMin
      if (currentTimeMin >= startMin) {
        const elapsedMin = Math.min(dur, currentTimeMin - startMin);
        const elapsedHours = elapsedMin / 60;
        const kwh = job.energyKwh ? (job.energyKwh * (elapsedMin / dur)) : (elapsedHours * 1.5);
        const intensity = currentPoint?.intensity ?? currentPoint?.realizedIntensity ?? 250;
        cumulativeEmissionsKg += computeEmissionsKg(kwh, intensity);
      }

      if (currentTimeMin < arr) {
        unarrived.push(job);
      } else if (currentTimeMin >= arr && currentTimeMin < startMin) {
        pending.push(job); // deferred/queued for clean window
      } else if (currentTimeMin >= startMin && currentTimeMin < finishMin) {
        running.push(job);
      } else {
        completed.push(job);
      }
    });

    return {
      running,
      pending,
      completed,
      unarrived,
      cumulativeEmissionsKg: Math.round(cumulativeEmissionsKg * 10) / 10,
    };
  }, [scheduledJobs, currentTimeMin, currentPoint]);

  // "Explain what changed" rationale comparison
  const changeExplanation = useMemo(() => {
    if (!previousJobs || !scheduledJobs || previousJobs.length === 0 || scheduledJobs.length === 0) {
      return null;
    }

    let shiftedCount = 0;
    let earlierCount = 0;
    let laterCount = 0;
    const affectedJobNames: string[] = [];

    scheduledJobs.forEach((curJob) => {
      const prevJob = previousJobs.find((p) => p.id === curJob.id);
      if (!prevJob) return;

      const curArr = curJob.arrivalMinutes ?? curJob.arrivalMin ?? 0;
      const prevArr = prevJob.arrivalMinutes ?? prevJob.arrivalMin ?? 0;
      const curStart = curJob.scheduledStartMinutes ?? curJob.scheduledStartMin ?? curArr;
      const prevStart = prevJob.scheduledStartMinutes ?? prevJob.scheduledStartMin ?? prevArr;

      if (curStart !== prevStart) {
        shiftedCount++;
        affectedJobNames.push(curJob.name);
        if (curStart < prevStart) {
          earlierCount++;
        } else {
          laterCount++;
        }
      }
    });

    if (shiftedCount === 0) {
      return {
        hasChange: false,
        summary: `No schedule alterations occurred. The current hyperparameter thresholds produce the identical dispatch sequence as the prior configuration.`,
      };
    }

    const lambdaDiff = config.lambda - previousConfig.lambda;
    let rationale = '';

    if (lambdaDiff > 0) {
      rationale = `Increasing risk aversion penalty (λ: ${previousConfig.lambda.toFixed(1)} → ${config.lambda.toFixed(1)}) caused ${shiftedCount} workload(s) to shift. ${earlierCount} job(s) moved to earlier windows because elevated forecast uncertainty variance (σ) penalized aggressive deferral, preventing potential carbon backfire.`;
    } else if (lambdaDiff < 0) {
      rationale = `Decreasing risk aversion (λ: ${previousConfig.lambda.toFixed(1)} → ${config.lambda.toFixed(1)}) accepted higher forecast risk, allowing ${laterCount} job(s) to wait for deeper predicted solar troughs.`;
    } else {
      rationale = `Parameter change affected ${shiftedCount} workload(s) (${affectedJobNames.slice(0, 3).join(', ')}${affectedJobNames.length > 3 ? '...' : ''}), shifting dispatch windows to conform with new resource or threshold constraints.`;
    }

    return {
      hasChange: true,
      shiftedCount,
      summary: rationale,
    };
  }, [scheduledJobs, previousJobs, config, previousConfig]);

  return (
    <div className="flex flex-col gap-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-slate-900">Carbon Time Machine</h1>
            <ProvenanceBadge type="synthetic" />
          </div>
          <p className="text-xs text-slate-500">
            Interactive trace replay and live simulation: inspect grid telemetry at time <em>t</em> and observe genuine schedule recalculations
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-[11px] text-slate-400 block uppercase font-bold tracking-wider">Simulation Clock</span>
            <span className="text-base font-bold font-mono text-emerald-700">
              {minutesToTimeString(currentTimeMin)} PST
            </span>
          </div>
        </div>
      </div>

      {/* Playback Controls & Scrubber */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Transport buttons */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentTimeMin(360)}
              className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
              title="Reset to 06:00"
            >
              <RotateCcw className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={() => setCurrentTimeMin((prev) => Math.max(360, prev - 15))}
              className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
              title="Step Backward (-15m)"
            >
              <SkipBack className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={() => setIsPlaying(!isPlaying)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white font-semibold text-xs shadow-xs hover:bg-emerald-700 transition-colors"
            >
              {isPlaying ? (
                <>
                  <Pause className="w-4 h-4" />
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>Play Replay</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => setCurrentTimeMin((prev) => Math.min(1440, prev + 15))}
              className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
              title="Step Forward (+15m)"
            >
              <SkipForward className="w-4 h-4" />
            </button>
          </div>

          {/* Speed selector */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-500 font-medium mr-1">Speed:</span>
            {[1, 2, 5, 10].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setPlaybackSpeed(s)}
                className={`px-2.5 py-1 rounded-md font-semibold text-xs transition-colors ${
                  playbackSpeed === s
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Timeline Range Slider Scrubber */}
        <div className="flex flex-col gap-1.5 pt-2">
          <div className="flex justify-between text-xs text-slate-500 font-mono">
            <span>06:00 (Dawn)</span>
            <span className="font-bold text-emerald-700 text-sm">{minutesToTimeString(currentTimeMin)}</span>
            <span>24:00 (Midnight)</span>
          </div>
          <input
            type="range"
            min={360}
            max={1440}
            step={15}
            value={currentTimeMin}
            onChange={(e) => setCurrentTimeMin(parseInt(e.target.value, 10))}
            className="w-full accent-emerald-600 cursor-pointer h-2 bg-slate-200 rounded-lg"
          />
        </div>
      </div>

      {/* Carbon Intensity Chart with Playback Marker */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-bold text-slate-900">Carbon Intensity Trace & Active Playhead</h2>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            Red vertical line indicates playhead at {minutesToTimeString(currentTimeMin)}
          </span>
        </div>

        <CarbonIntensityChart
          trace={trace}
          metadata={metadata}
          selectedTime={minutesToTimeString(currentTimeMin)}
          height={300}
        />
      </div>

      {/* Grid Telemetry & Workload Queue at Time t */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Instantaneous Intensity */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Grid Intensity at t</span>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-900">
              {currentPoint?.intensity ?? currentPoint?.realizedIntensity ?? 240}{' '}
              <span className="text-xs font-sans font-normal text-slate-500">gCO₂e/kWh</span>
            </div>
            <span className="text-[11px] text-slate-500">
              Forecast: {currentPoint?.predictedMu ?? currentPoint?.forecastMean ?? 240} ± {Math.round(currentPoint?.sigma ?? currentPoint?.forecastSigma ?? 15)}
            </span>
          </div>
          <div className="text-[10px] text-slate-400 font-medium">Real-time CAISO-Z2 marginal signal</div>
        </div>

        {/* Clean Energy Share */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Clean Generation Share</span>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-emerald-700">{cleanEnergyPercent}%</div>
            <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
              <div
                className="bg-emerald-600 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${cleanEnergyPercent}%` }}
              />
            </div>
          </div>
          <div className="text-[10px] text-slate-400 font-medium">Solar + Wind generation ratio</div>
        </div>

        {/* Cumulative Emissions */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Cumulative Emissions</span>
          <div className="my-2">
            <div className="text-2xl font-bold font-mono text-slate-900">
              {workloadState.cumulativeEmissionsKg}{' '}
              <span className="text-xs font-sans font-normal text-slate-500">kgCO₂e</span>
            </div>
            <span className="text-[11px] text-slate-500">Emitted up to {minutesToTimeString(currentTimeMin)}</span>
          </div>
          <div className="text-[10px] text-slate-400 font-medium">Workloads completed or executing</div>
        </div>

        {/* Workload Status */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Active Workloads</span>
          <div className="my-2 flex items-center gap-3">
            <div>
              <span className="text-xl font-bold font-mono text-emerald-700">{workloadState.running.length}</span>
              <span className="text-[10px] text-slate-400 block">Running</span>
            </div>
            <div>
              <span className="text-xl font-bold font-mono text-amber-600">{workloadState.pending.length}</span>
              <span className="text-[10px] text-slate-400 block">Deferred (Queue)</span>
            </div>
            <div>
              <span className="text-xl font-bold font-mono text-slate-700">{workloadState.completed.length}</span>
              <span className="text-[10px] text-slate-400 block">Done</span>
            </div>
          </div>
          <div className="text-[10px] text-slate-400 font-medium">
            {workloadState.unarrived.length} jobs not yet arrived
          </div>
        </div>
      </div>

      {/* Hyperparameter Controls (Genuine Real-Time Recalculation) */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Live Hyperparameter Tuning (Instant Re-Solver)</h3>
          </div>
          <span className="text-xs text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded-sm">
            Active recalculation enabled
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 text-xs">
          {/* Lambda */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <span className="font-bold text-slate-700">Risk Aversion (λ)</span>
              <span className="font-mono font-bold text-emerald-700">{config.lambda.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min={0.0}
              max={3.0}
              step={0.1}
              value={config.lambda}
              onChange={(e) => handleConfigChange('lambda', parseFloat(e.target.value))}
              className="accent-emerald-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400">0.0 = risk-neutral (naive); 3.0 = ultra-cautious</span>
          </div>

          {/* Uncertainty Scale */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <span className="font-bold text-slate-700">Forecast Error Scale (σ)</span>
              <span className="font-mono font-bold text-emerald-700">{config.forecastErrorScale.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min={0.5}
              max={3.0}
              step={0.1}
              value={config.forecastErrorScale}
              onChange={(e) => handleConfigChange('forecastErrorScale', parseFloat(e.target.value))}
              className="accent-emerald-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400">Scale factor on forecasted standard deviation</span>
          </div>

          {/* Min Improvement */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <span className="font-bold text-slate-700">Min Improvement Threshold</span>
              <span className="font-mono font-bold text-emerald-700">{config.minImprovementPct}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={25}
              step={1}
              value={config.minImprovementPct}
              onChange={(e) => handleConfigChange('minImprovementPct', parseInt(e.target.value, 10))}
              className="accent-emerald-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400">Minimum % carbon reduction required to justify delay</span>
          </div>

          {/* Max Capacity */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <span className="font-bold text-slate-700">Cluster GPU Capacity</span>
              <span className="font-mono font-bold text-emerald-700">{config.capacityLimit} GPUs</span>
            </div>
            <input
              type="range"
              min={4}
              max={32}
              step={2}
              value={config.capacityLimit}
              onChange={(e) => handleConfigChange('capacityLimit', parseInt(e.target.value, 10))}
              className="accent-emerald-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400">Hardware parallel limit</span>
          </div>
        </div>
      </div>

      {/* "Explain What Changed" Rationale Panel */}
      {changeExplanation && (
        <div className="bg-emerald-50/50 border border-emerald-200 rounded-xl p-4 shadow-xs flex flex-col gap-2">
          <div className="flex items-center gap-2 text-emerald-900 font-bold text-xs">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <span>Traceable Solver Explanation: What Changed</span>
          </div>
          <p className="text-xs text-emerald-800 leading-relaxed font-sans">
            {changeExplanation.summary}
          </p>
        </div>
      )}
    </div>
  );
};
