import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PlusCircle,
  Trash2,
  RotateCcw,
  Play,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Clock,
  Zap,
  Cpu,
  Layers,
} from 'lucide-react';
import { Job, JobType, JobPriority } from '../types';
import { submitJob, removeJob, runScheduler, resetDemoState } from '../services/api';
import { INITIAL_DEMO_JOBS } from '../data/mockData';
import {
  timeStringToMinutes,
  computeEmissionsKg,
  computeAvoidedKg,
  computeReductionPct,
  formatMinutes,
} from '../utils/metrics';
import { validateJobSubmission } from '../utils/validation';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { StatusBadge } from '../components/common/StatusBadge';

export const JobSubmission: React.FC = () => {
  const navigate = useNavigate();

  // Job List State
  const [jobs, setJobs] = useState<Job[]>(INITIAL_DEMO_JOBS);

  // Form Field State
  const [jobId, setJobId] = useState('JOB-9426');
  const [jobName, setJobName] = useState('BERT Embedding Fine-Tuning');
  const [jobType, setJobType] = useState<JobType>('fine_tuning');
  const [arrivalTime, setArrivalTime] = useState('11:15');
  const [deadlineTime, setDeadlineTime] = useState('21:00');
  const [durationMinutes, setDurationMinutes] = useState(150); // 2h 30m
  const [energyKwh, setEnergyKwh] = useState(120);
  const [priority, setPriority] = useState<JobPriority>('normal');
  const [deferrable, setDeferrable] = useState(true);
  const [resourceRequirement, setResourceRequirement] = useState(8);
  const [resourceLabel, setResourceLabel] = useState('8x NVIDIA H100 SXM5');

  // Interactive feedback state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSolving, setIsSolving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Delete modal state
  const [deleteTargetJobId, setDeleteTargetJobId] = useState<string | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  // Real-time validations using centralized validation rule-set
  const validation = validateJobSubmission(
    {
      id: jobId,
      name: jobName,
      arrivalTime,
      deadlineTime,
      durationMinutes,
      energyKwh,
      resourceRequirement,
    },
    jobs
  );

  const {
    isValid: isFormValid,
    slackMinutes,
    isTimingFeasible,
    isDuplicateId,
    isDurationValid,
    isEnergyValid,
    isResourceValid,
    isIdValid,
  } = validation;

  const arrivalMin = timeStringToMinutes(arrivalTime);
  const deadlineMin = timeStringToMinutes(deadlineTime);

  // Real-time estimate
  const baselineKg = computeEmissionsKg(energyKwh, 218); // CAISO daytime baseline
  const greenKg = computeEmissionsKg(energyKwh, 93); // CAISO solar peak
  const avoidedKg = computeAvoidedKg(baselineKg, greenKg);
  const reductionPct = computeReductionPct(baselineKg, greenKg);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (isDuplicateId) {
      setErrorMessage(`Job ID "${jobId}" already exists. Assign a unique job identifier.`);
      return;
    }
    if (!isTimingFeasible) {
      setErrorMessage(
        `Deadline (${deadlineTime}) must be at least ${formatMinutes(
          durationMinutes
        )} after arrival (${arrivalTime}).`
      );
      return;
    }

    try {
      setIsSubmitting(true);
      const newJobPayload = {
        id: jobId.trim(),
        name: jobName.trim(),
        type: jobType,
        arrivalTime,
        arrivalMinutes: arrivalMin,
        deadline: deadlineTime,
        deadlineMinutes: deadlineMin,
        durationMinutes,
        energyKwh,
        priority,
        deferrable,
        resourceRequirement,
        resourceLabel: resourceLabel.trim() || `${resourceRequirement} Accelerator Nodes`,
      };

      const added = await submitJob(newJobPayload);
      setJobs((prev) => [...prev.filter((j) => j.id !== added.id), added]);
      setSuccessMessage(`Job #${added.id} (${added.name}) submitted successfully!`);

      // Increment default ID for next entry
      setJobId(`JOB-${Math.floor(9427 + Math.random() * 50)}`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Job submission failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemove = async (id: string) => {
    await removeJob(id);
    setJobs((prev) => prev.filter((j) => j.id !== id));
    setDeleteTargetJobId(null);
  };

  const handleReset = () => {
    resetDemoState();
    setJobs(INITIAL_DEMO_JOBS);
    setShowResetConfirm(false);
  };

  const handleRunScheduler = async () => {
    try {
      setIsSolving(true);
      const solved = await runScheduler(
        {
          lambda: 1.0,
          minImprovementPct: 10,
          ordering: 'earliest_arrival',
          slotIntervalMin: 15,
          capacityLimit: 16,
          forecastErrorScale: 1.0,
          seed: 42,
        },
        jobs
      );
      setJobs(solved.jobs);
      navigate('/schedule-results');
    } finally {
      setIsSolving(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-200">
      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteTargetJobId)}
        title="Remove Workload from Queue?"
        description={`Are you sure you want to remove job #${deleteTargetJobId}? This will remove it from scheduling evaluation.`}
        confirmLabel="Remove Job"
        cancelLabel="Cancel"
        isDestructive
        onConfirm={() => deleteTargetJobId && handleRemove(deleteTargetJobId)}
        onCancel={() => setDeleteTargetJobId(null)}
      />

      {/* Reset Confirmation Modal */}
      <ConfirmModal
        isOpen={showResetConfirm}
        title="Reset Workload Queue to Default?"
        description="This will restore the reproducible initial set of 4 demo jobs and clear any custom submissions."
        confirmLabel="Reset Queue"
        cancelLabel="Keep Current Jobs"
        onConfirm={handleReset}
        onCancel={() => setShowResetConfirm(false)}
      />

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Workload Intake & Job Management
          </h2>
          <p className="text-xs text-slate-500">
            Submit computational jobs, validate temporal and resource feasibility, and run the GreenSchedule solver.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => setShowResetConfirm(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 text-xs font-semibold shadow-2xs transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Demo Jobs</span>
          </button>
          <button
            type="button"
            onClick={handleRunScheduler}
            disabled={isSolving || jobs.length === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${isSolving ? 'animate-spin' : ''}`} />
            <span>{isSolving ? 'Solving Schedule...' : 'Run GreenSchedule Solver'}</span>
          </button>
        </div>
      </div>

      {/* Success / Error Alerts */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            <span className="font-medium">{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-red-600 hover:text-red-900 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-medium">{successMessage}</span>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-700 hover:text-emerald-900 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* 2-Column Section: Form (7 cols) + Feasibility & Live Estimate (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form (7 cols) */}
        <form
          onSubmit={handleSubmit}
          className="lg:col-span-7 bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col gap-4"
        >
          <div className="pb-2 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900">Add Computational Job</h3>
            <span className="text-[10px] text-slate-400 font-mono">* Required fields</span>
          </div>

          {/* Row 1: ID & Name */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="job-id" className="text-xs font-semibold text-slate-700">
                Job Identifier *
              </label>
              <input
                id="job-id"
                type="text"
                required
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                className={`p-2.5 rounded-lg border text-xs font-mono bg-slate-50 text-slate-900 focus:outline-none focus:ring-2 ${
                  isDuplicateId ? 'border-red-500 focus:ring-red-400' : 'border-slate-200 focus:ring-emerald-500'
                }`}
                placeholder="e.g. JOB-9426"
              />
              {isDuplicateId && (
                <span className="text-[10px] text-red-600 font-medium">Job ID already exists in queue</span>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="job-name" className="text-xs font-semibold text-slate-700">
                Workload Name *
              </label>
              <input
                id="job-name"
                type="text"
                required
                value={jobName}
                onChange={(e) => setJobName(e.target.value)}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                placeholder="e.g. Mistral LoRA Fine-Tuning"
              />
            </div>
          </div>

          {/* Row 2: Type & Priority */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="job-type" className="text-xs font-semibold text-slate-700">
                Workload Type *
              </label>
              <select
                id="job-type"
                value={jobType}
                onChange={(e) => setJobType(e.target.value as JobType)}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs font-medium focus:ring-2 focus:ring-emerald-500"
              >
                <option value="training">Training (Foundational / Full Pre-train)</option>
                <option value="fine_tuning">Fine-Tuning (LoRA / SFT / Alignment)</option>
                <option value="batch_inference">Batch Inference (Embeddings / Offline Eval)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="job-priority" className="text-xs font-semibold text-slate-700">
                SLA Priority Level *
              </label>
              <select
                id="job-priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value as JobPriority)}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs font-medium focus:ring-2 focus:ring-emerald-500"
              >
                <option value="low">Low (Maximum Deferral for Greenest Window)</option>
                <option value="normal">Normal (Balanced Cost / Emissions / Wait)</option>
                <option value="high">High (Tight SLA Safety Buffer)</option>
                <option value="critical">Critical (Immediate Dispatch)</option>
              </select>
            </div>
          </div>

          {/* Row 3: Arrival & Deadline */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="arrival-time" className="text-xs font-semibold text-slate-700">
                Arrival Time (Earliest Start) *
              </label>
              <input
                id="arrival-time"
                type="time"
                required
                value={arrivalTime}
                onChange={(e) => setArrivalTime(e.target.value)}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="deadline-time" className="text-xs font-semibold text-slate-700">
                Hard SLA Deadline *
              </label>
              <input
                id="deadline-time"
                type="time"
                required
                value={deadlineTime}
                onChange={(e) => setDeadlineTime(e.target.value)}
                className={`p-2.5 rounded-lg border text-xs font-mono bg-slate-50 text-slate-900 focus:ring-2 ${
                  !isTimingFeasible ? 'border-red-500 focus:ring-red-400' : 'border-slate-200 focus:ring-emerald-500'
                }`}
              />
              {!isTimingFeasible && (
                <span className="text-[10px] text-red-600 font-medium">
                  Deadline must be at least {formatMinutes(durationMinutes)} after arrival
                </span>
              )}
            </div>
          </div>

          {/* Row 4: Duration & Energy */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center">
                <label htmlFor="duration-min" className="text-xs font-semibold text-slate-700">
                  Duration (Minutes) *
                </label>
                <span className="font-mono font-bold text-emerald-700 text-xs">
                  {formatMinutes(durationMinutes)}
                </span>
              </div>
              <input
                id="duration-min"
                type="number"
                min="15"
                max="1440"
                step="15"
                required
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Math.max(15, parseInt(e.target.value, 10)))}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center">
                <label htmlFor="energy-kwh" className="text-xs font-semibold text-slate-700">
                  Energy Consumption (kWh) *
                </label>
                <span className="font-mono font-bold text-slate-900 text-xs">{energyKwh} kWh</span>
              </div>
              <input
                id="energy-kwh"
                type="number"
                min="1"
                max="10000"
                required
                value={energyKwh}
                onChange={(e) => setEnergyKwh(Math.max(1, parseInt(e.target.value, 10)))}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          {/* Row 5: Hardware Resource */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="resource-req" className="text-xs font-semibold text-slate-700">
                Resource Requirement (Nodes/GPUs) *
              </label>
              <input
                id="resource-req"
                type="number"
                min="1"
                max="64"
                required
                value={resourceRequirement}
                onChange={(e) =>
                  setResourceRequirement(Math.max(1, parseInt(e.target.value, 10)))
                }
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs font-mono focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="resource-label" className="text-xs font-semibold text-slate-700">
                Hardware Model Label
              </label>
              <input
                id="resource-label"
                type="text"
                value={resourceLabel}
                onChange={(e) => setResourceLabel(e.target.value)}
                className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-900 text-xs focus:ring-2 focus:ring-emerald-500"
                placeholder="e.g. 8x NVIDIA H100 SXM5"
              />
            </div>
          </div>

          {/* Deferrable Toggle */}
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
            <div className="flex flex-col">
              <label htmlFor="deferrable-chk" className="text-xs font-bold text-slate-800 cursor-pointer">
                Allow Carbon-Aware Deferral
              </label>
              <span className="text-[11px] text-slate-500">
                Urgent and non-deferrable jobs will execute at earliest feasible slot.
              </span>
            </div>
            <input
              type="checkbox"
              id="deferrable-chk"
              checked={deferrable}
              onChange={(e) => setDeferrable(e.target.checked)}
              className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 cursor-pointer"
            />
          </div>

          {/* Submit Action */}
          <button
            type="submit"
            disabled={!isFormValid || isSubmitting}
            className={`w-full py-3 rounded-lg text-white font-semibold text-xs shadow-xs transition-all flex items-center justify-center gap-2 ${
              isFormValid && !isSubmitting
                ? 'bg-emerald-600 hover:bg-emerald-700 active:scale-[0.99]'
                : 'bg-slate-300 text-slate-500 cursor-not-allowed opacity-70'
            }`}
          >
            <PlusCircle className="w-4 h-4" />
            <span>{isSubmitting ? 'Validating and Submitting...' : 'Add Workload to Queue'}</span>
          </button>
        </form>

        {/* Right Panel: Feasibility Verification & Live Carbon Estimate (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between gap-5">
          <div className="flex flex-col gap-4">
            <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Pre-Flight Feasibility Check</h3>
                <p className="text-xs text-slate-500">Constraint verification before solver commit</p>
              </div>
              <span
                className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                  isTimingFeasible
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-red-100 text-red-800'
                }`}
              >
                {isTimingFeasible ? 'Feasible Window' : 'Infeasible SLA'}
              </span>
            </div>

            <div className="flex flex-col gap-2.5 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-600 font-medium">Timing Slack Margin</span>
                <span className="font-mono font-bold text-slate-900">
                  {isTimingFeasible ? `${formatMinutes(slackMinutes)} Slack` : 'Violated'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-600 font-medium">Resource Cap Status</span>
                <span className="font-mono font-bold text-emerald-700">
                  Allocatable ({resourceRequirement}/16 GPUs)
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-600 font-medium">Deferral Eligibility</span>
                <span className="font-bold text-slate-800">
                  {deferrable && priority !== 'critical' ? 'Eligible for Solar Valley' : 'Immediate Dispatch Only'}
                </span>
              </div>
            </div>

            {/* Estimated Carbon Impact */}
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex flex-col gap-2.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800">
                Estimated Carbon Impact
              </span>

              <div className="flex justify-between items-baseline text-xs">
                <span className="text-emerald-900/70 font-medium">Immediate Baseline (218g):</span>
                <span className="font-mono font-bold text-emerald-950">{baselineKg} kgCO₂e</span>
              </div>

              <div className="flex justify-between items-baseline text-xs">
                <span className="text-emerald-900/70 font-medium">Carbonova Valley (93g):</span>
                <span className="font-mono font-bold text-emerald-700 text-sm">{greenKg} kgCO₂e</span>
              </div>

              <div className="h-px bg-emerald-200 my-0.5" />

              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-emerald-900">Avoidable Emissions:</span>
                <span className="font-mono font-bold text-emerald-700 text-base">
                  −{avoidedKg} kg (−{reductionPct}%)
                </span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-500 text-center">
            Evaluated against CAISO-Z2 regional grid trace (15-min resolution)
          </div>
        </div>
      </div>

      {/* Submitted Jobs Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col gap-3">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Registered Workload Queue</h3>
            <p className="text-xs text-slate-500">
              {jobs.length} jobs currently staged for Carbonova scheduling evaluation
            </p>
          </div>
          <span className="font-mono text-xs text-slate-400">Total Energy: {jobs.reduce((acc, j) => acc + j.energyKwh, 0)} kWh</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs" aria-label="Registered Jobs Queue">
            <thead>
              <tr className="border-b border-slate-100 text-[10px] font-semibold uppercase text-slate-400">
                <th className="py-2.5">Job ID</th>
                <th className="py-2.5">Workload Name</th>
                <th className="py-2.5">Type</th>
                <th className="py-2.5">Arrival – Deadline</th>
                <th className="py-2.5">Duration</th>
                <th className="py-2.5">Energy</th>
                <th className="py-2.5">Priority</th>
                <th className="py-2.5">Deferrable</th>
                <th className="py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-slate-50 transition-colors">
                  <td className="py-3 font-bold text-emerald-700">#{job.id}</td>
                  <td className="py-3 font-sans font-medium text-slate-900">{job.name}</td>
                  <td className="py-3 capitalize text-slate-600">{job.type.replace('_', ' ')}</td>
                  <td className="py-3 text-slate-700">
                    {job.arrivalTime} – {job.deadline}
                  </td>
                  <td className="py-3 text-slate-700">{formatMinutes(job.durationMinutes)}</td>
                  <td className="py-3 text-slate-700">{job.energyKwh} kWh</td>
                  <td className="py-3 font-sans">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-600">
                      {job.priority}
                    </span>
                  </td>
                  <td className="py-3 font-sans">
                    {job.deferrable ? (
                      <span className="text-emerald-600 font-semibold">Yes</span>
                    ) : (
                      <span className="text-amber-600 font-semibold">No (Urgent)</span>
                    )}
                  </td>
                  <td className="py-3 text-right">
                    <button
                      type="button"
                      onClick={() => setDeleteTargetJobId(job.id)}
                      className="p-1 text-slate-400 hover:text-red-600 rounded transition-colors"
                      title="Remove workload"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
