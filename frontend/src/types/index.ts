export type JobType = 'training' | 'fine_tuning' | 'batch_inference';
export type JobPriority = 'low' | 'normal' | 'high' | 'critical';
export type JobStatus = 'Scheduled' | 'Running' | 'Completed' | 'Failed' | 'Infeasible';

export interface Job {
  id: string;
  name: string;
  type: JobType;
  arrivalTime: string; // "11:00"
  arrivalMinutes: number; // minutes from 00:00
  arrivalMin?: number;
  deadline: string; // "22:00"
  deadlineMinutes: number;
  deadlineMin?: number;
  durationMinutes: number;
  durationMin?: number;
  energyKwh: number;
  powerWatts?: number;
  priority: JobPriority;
  deferrable: boolean;
  resourceRequirement: number; // e.g. 4 GPUs
  gpus?: number;
  resourceLabel?: string;
  status: JobStatus;

  // Scheduling output fields
  scheduledStart?: string;
  scheduledStartMinutes?: number;
  scheduledStartMin?: number;
  scheduledFinish?: string;
  scheduledFinishMinutes?: number;
  predictedIntensity?: number;
  predictedUncertainty?: number;
  riskScore?: number;
  deadlineSlackMinutes?: number;
  queueDelayMinutes?: number;
  estimatedEmissionsKg?: number;
  immediateEmissionsKg?: number;
  avoidedEmissionsKg?: number;
  explanation?: string;
  delayRationale?: string;
  feasible?: boolean;
}

export interface TracePoint {
  time: string; // "11:00"
  timestampMinutes: number;
  timeMinutes?: number;
  intensity: number; // Realized gCO2e/kWh
  realizedIntensity?: number;
  predictedMu: number; // Forecast mean
  forecastMean?: number;
  sigma: number; // Forecast uncertainty std dev
  forecastSigma?: number;
  solarPct: number;
  windPct: number;
  gasPct: number;
  hydroPct: number;
}

export type ProvenanceType =
  | 'measured'
  | 'tool_estimated'
  | 'tool-estimated'
  | 'assumption_based'
  | 'assumption-based'
  | 'recorded'
  | 'synthetic'
  | 'live';

export interface TraceMetadata {
  region: string;
  period: string;
  sourceType: 'recorded' | 'synthetic' | 'live';
  resolutionMin: number;
  units: string;
  timezone: string;
}

export interface SchedulerConfig {
  lambda: number; // Risk aversion (heuristic score weight: mu + lambda * sigma)
  riskWeightLambda?: number;
  minImprovementPct: number; // Min % savings required before delaying
  ordering: 'earliest_arrival' | 'least_slack';
  slotIntervalMin: number;
  capacityLimit: number; // Maximum concurrent GPU nodes
  maxGpuCapacity?: number;
  forecastErrorScale: number; // Simulation control
  seed: number;
}

export interface PolicyComparisonResult {
  policyId: 'fifo' | 'naive_green' | 'carbonova' | 'oracle';
  policyName: string;
  badge: string;
  color: string;
  description: string;
  totalRealizedEmissionsKg: number;
  emissionsReductionPct: number | 'N/A';
  deadlineSuccessPct: number;
  infeasibleJobsCount: number;
  meanWaitHours: number;
  backfireRatePct: number | 'N/A';
  predictedSavingsKg: number;
  realizedSavingsKg: number;
  oracleGapKg: number;
  delayedJobsCount: number;
  backfiredJobsCount: number;
}

export interface SystemStatus {
  isOnline: boolean;
  backendUrl: string;
  mode: 'Live API' | 'Demo Mode (Simulation)';
  core: string;
  version: string;
  lastUpdated: string;
}

export interface GreenGateInference {
  id: string;
  timestamp: string;
  query: string;
  routingDecision: 'Tier-1 Small (Fast)' | 'Tier-2 Large (Deep)';
  modelName: string;
  routingReason: string;
  qualityScore: number;
  qualityFloorPassed: boolean;
  latencyMs: number;
  escalated: boolean;
  energyKwh: number;
  carbonGrams: number;
  savingsVsLargePct: number;
}
