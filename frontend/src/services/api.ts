import {
  Job,
  TracePoint,
  TraceMetadata,
  SchedulerConfig,
  PolicyComparisonResult,
  SystemStatus,
  GreenGateInference,
} from '../types';
import {
  MOCK_GRID_TRACE_24H,
  MOCK_TRACE_METADATA,
  INITIAL_DEMO_JOBS,
  MOCK_SYSTEM_STATUS,
} from '../data/mockData';
import { solveJobsSchedule, runPolicyBenchmark } from '../utils/scheduler';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// In-memory store for simulation when backend is offline
let localJobs: Job[] = [...INITIAL_DEMO_JOBS];
let localTrace: TracePoint[] = [...MOCK_GRID_TRACE_24H];

/**
 * Checks backend health and availability.
 * GET /api/health
 */
export async function getSystemHealth(): Promise<SystemStatus> {
  if (API_BASE_URL) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/health`, { method: 'GET' });
      if (res.ok) {
        const data = await res.json();
        return {
          isOnline: true,
          backendUrl: API_BASE_URL,
          mode: 'Live API',
          core: data.core || 'FastAPI Carbonova Backend',
          version: data.version || 'v2.4.0',
          lastUpdated: new Date().toLocaleTimeString(),
        };
      }
    } catch (err) {
      console.warn('Backend API offline, operating in simulation mode:', err);
    }
  }

  return {
    ...MOCK_SYSTEM_STATUS,
    isOnline: false,
    mode: 'Demo Mode (Simulation)',
    lastUpdated: new Date().toLocaleTimeString(),
  };
}

/**
 * Retrieves regional carbon intensity time-series trace and metadata.
 * GET /api/carbon
 */
export async function getCarbonTrace(
  region = 'CAISO-Z2'
): Promise<{ trace: TracePoint[]; metadata: TraceMetadata }> {
  if (API_BASE_URL) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/carbon?region=${encodeURIComponent(region)}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.trace && Array.isArray(data.trace)) {
          return {
            trace: data.trace,
            metadata: data.metadata || MOCK_TRACE_METADATA,
          };
        }
      }
    } catch (err) {
      console.warn('Grid API fetch failed, using recorded telemetry fallback:', err);
    }
  }

  // Simulated minor network latency for realistic feel
  await new Promise((r) => setTimeout(r, 60));
  return {
    trace: localTrace,
    metadata: MOCK_TRACE_METADATA,
  };
}

/**
 * Submits and validates a computational job.
 * POST /api/jobs
 */
export async function submitJob(jobPayload: Omit<Job, 'status'>): Promise<Job> {
  if (API_BASE_URL) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jobPayload),
      });
      if (res.ok) {
        return res.json();
      }
    } catch (err) {
      console.warn('Remote job submission failed, using local queue:', err);
    }
  }

  await new Promise((r) => setTimeout(r, 100));

  const newJob: Job = {
    ...jobPayload,
    status: 'Scheduled',
  };

  // Add or replace in local list
  const idx = localJobs.findIndex((j) => j.id.toUpperCase() === newJob.id.toUpperCase());
  if (idx >= 0) {
    localJobs[idx] = newJob;
  } else {
    localJobs.push(newJob);
  }

  return newJob;
}

/**
 * Removes a job from the queue.
 */
export async function removeJob(jobId: string): Promise<boolean> {
  localJobs = localJobs.filter((j) => j.id !== jobId);
  return true;
}

/**
 * Runs scheduler with custom hyperparameter settings.
 * POST /api/schedule/run
 */
export async function runScheduler(
  config: SchedulerConfig,
  jobsToSchedule?: Job[]
) {
  const jobs = jobsToSchedule || localJobs;

  if (API_BASE_URL) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/schedule/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config, jobs }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.jobs) {
          return data;
        }
      }
    } catch (err) {
      console.warn('Remote scheduler invocation failed, using local solver fallback:', err);
    }
  }

  await new Promise((r) => setTimeout(r, 120));
  const evaluated = solveJobsSchedule(jobs, localTrace, config);
  localJobs = evaluated.jobs;
  return evaluated;
}

/**
 * Retrieves benchmark comparison across policies and sensitivity scenarios.
 * GET /api/schedule/results
 */
export async function getPolicyBenchmarks(
  config: SchedulerConfig,
  scenario: 'variable' | 'flat' | 'noisy' | 'tight' | 'contention' | 'no_delay' = 'variable'
): Promise<PolicyComparisonResult[]> {
  if (API_BASE_URL) {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/schedule/results?scenario=${encodeURIComponent(scenario)}`
      );
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          return data;
        }
      }
    } catch (err) {
      console.warn('Remote benchmark failed, using local benchmark fallback:', err);
    }
  }

  await new Promise((r) => setTimeout(r, 80));
  return runPolicyBenchmark(localJobs, localTrace, config, scenario);
}

/**
 * Optional GreenGate query routing module.
 * POST /api/inference
 */
export async function runGreenGateInference(
  query: string,
  qualityFloor = 0.85
): Promise<GreenGateInference> {
  await new Promise((r) => setTimeout(r, 200));

  // Determine complexity
  const isComplex = query.length > 80 || query.includes('code') || query.includes('explain');
  const routingDecision = isComplex ? 'Tier-2 Large (Deep)' : 'Tier-1 Small (Fast)';
  const modelName = isComplex ? 'Llama-3-70B-Instruct' : 'Mistral-7B-Instruct';
  const qualityScore = isComplex ? 0.94 : 0.88;
  const escalated = !isComplex && qualityScore < qualityFloor;

  return {
    id: `REQ-${Math.floor(1000 + Math.random() * 9000)}`,
    timestamp: new Date().toLocaleTimeString(),
    query,
    routingDecision,
    modelName: escalated ? 'Escalated to Llama-3-70B' : modelName,
    routingReason: isComplex
      ? 'Query complexity exceeds Tier-1 semantic ceiling'
      : 'Query resolved within quality floor by Tier-1 small model',
    qualityScore,
    qualityFloorPassed: qualityScore >= qualityFloor,
    latencyMs: isComplex ? 480 : 140,
    escalated,
    energyKwh: isComplex ? 0.045 : 0.008,
    carbonGrams: isComplex ? 4.2 : 0.74,
    savingsVsLargePct: isComplex ? 0 : 82.4,
  };
}

/**
 * Resets local demo state to reproducible default.
 */
export function resetDemoState(): void {
  localJobs = [...INITIAL_DEMO_JOBS];
  localTrace = [...MOCK_GRID_TRACE_24H];
}
