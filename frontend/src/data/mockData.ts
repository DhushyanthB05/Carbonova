import { Job, TracePoint, TraceMetadata, SystemStatus, SchedulerConfig } from '../types';

export const MOCK_TRACE_METADATA: TraceMetadata = {
  region: 'CAISO-Z2 (California Regional Grid)',
  period: '2026-10-26 00:00 – 23:59 UTC',
  sourceType: 'recorded',
  resolutionMin: 15,
  units: 'gCO₂e/kWh',
  timezone: 'UTC (displayed in PST / UTC-8)',
};

export const MOCK_SYSTEM_STATUS: SystemStatus = {
  isOnline: false,
  backendUrl: 'http://localhost:8000',
  mode: 'Demo Mode (Simulation)',
  core: 'FastAPI Offline / Pure TS Simulator Engine',
  version: 'v2.4.0',
  lastUpdated: 'Just now',
};

export const initialSchedulerConfig: SchedulerConfig = {
  lambda: 1.0,
  minImprovementPct: 5,
  ordering: 'earliest_arrival',
  slotIntervalMin: 15,
  capacityLimit: 16,
  forecastErrorScale: 1.0,
  seed: 42,
};

// 24-Hour 15-minute / 30-minute interval empirical CAISO curve
export const MOCK_GRID_TRACE_24H: TracePoint[] = [
  { time: '00:00', timestampMinutes: 0, intensity: 280, predictedMu: 285, sigma: 18, solarPct: 0, windPct: 40, gasPct: 45, hydroPct: 15 },
  { time: '01:30', timestampMinutes: 90, intensity: 270, predictedMu: 268, sigma: 16, solarPct: 0, windPct: 44, gasPct: 42, hydroPct: 14 },
  { time: '03:00', timestampMinutes: 180, intensity: 250, predictedMu: 248, sigma: 15, solarPct: 0, windPct: 50, gasPct: 36, hydroPct: 14 },
  { time: '04:30', timestampMinutes: 270, intensity: 235, predictedMu: 238, sigma: 17, solarPct: 0, windPct: 55, gasPct: 32, hydroPct: 13 },
  { time: '06:00', timestampMinutes: 360, intensity: 295, predictedMu: 290, sigma: 22, solarPct: 4, windPct: 40, gasPct: 45, hydroPct: 11 },
  { time: '07:30', timestampMinutes: 450, intensity: 275, predictedMu: 270, sigma: 20, solarPct: 15, windPct: 35, gasPct: 40, hydroPct: 10 },
  { time: '09:00', timestampMinutes: 540, intensity: 210, predictedMu: 205, sigma: 16, solarPct: 45, windPct: 25, gasPct: 24, hydroPct: 6 },
  { time: '10:30', timestampMinutes: 630, intensity: 160, predictedMu: 155, sigma: 14, solarPct: 62, windPct: 18, gasPct: 15, hydroPct: 5 },
  { time: '11:45', timestampMinutes: 705, intensity: 130, predictedMu: 128, sigma: 13, solarPct: 70, windPct: 16, gasPct: 10, hydroPct: 4 },
  { time: '12:30', timestampMinutes: 750, intensity: 98, predictedMu: 102, sigma: 12, solarPct: 78, windPct: 12, gasPct: 7, hydroPct: 3 },
  { time: '13:30', timestampMinutes: 810, intensity: 84, predictedMu: 85, sigma: 12, solarPct: 84, windPct: 9, gasPct: 4, hydroPct: 3 },
  { time: '14:30', timestampMinutes: 870, intensity: 88, predictedMu: 90, sigma: 13, solarPct: 82, windPct: 10, gasPct: 5, hydroPct: 3 },
  { time: '15:45', timestampMinutes: 945, intensity: 105, predictedMu: 102, sigma: 14, solarPct: 74, windPct: 12, gasPct: 10, hydroPct: 4 },
  { time: '17:00', timestampMinutes: 1020, intensity: 145, predictedMu: 140, sigma: 16, solarPct: 52, windPct: 18, gasPct: 24, hydroPct: 6 },
  { time: '18:30', timestampMinutes: 1110, intensity: 225, predictedMu: 220, sigma: 20, solarPct: 18, windPct: 28, gasPct: 44, hydroPct: 10 },
  { time: '20:00', timestampMinutes: 1200, intensity: 280, predictedMu: 282, sigma: 24, solarPct: 0, windPct: 30, gasPct: 58, hydroPct: 12 },
  { time: '21:30', timestampMinutes: 1290, intensity: 265, predictedMu: 260, sigma: 19, solarPct: 0, windPct: 36, gasPct: 52, hydroPct: 12 },
  { time: '23:00', timestampMinutes: 1380, intensity: 245, predictedMu: 248, sigma: 17, solarPct: 0, windPct: 40, gasPct: 48, hydroPct: 12 },
  { time: '23:59', timestampMinutes: 1439, intensity: 240, predictedMu: 242, sigma: 16, solarPct: 0, windPct: 42, gasPct: 46, hydroPct: 12 },
];

export const INITIAL_DEMO_JOBS: Job[] = [
  {
    id: 'JOB-9421',
    name: 'ResNet-50 Vision Pre-training',
    type: 'training',
    arrivalTime: '11:00',
    arrivalMinutes: 660,
    deadline: '22:00',
    deadlineMinutes: 1320,
    durationMinutes: 210, // 3h 30m
    energyKwh: 250,
    priority: 'normal',
    deferrable: true,
    resourceRequirement: 8,
    resourceLabel: '8x NVIDIA H100 SXM5',
    status: 'Scheduled',
  },
  {
    id: 'JOB-9422',
    name: 'Llama-3-70B LoRA Alignment',
    type: 'fine_tuning',
    arrivalTime: '11:30',
    arrivalMinutes: 690,
    deadline: '17:30',
    deadlineMinutes: 1050,
    durationMinutes: 180, // 3h
    energyKwh: 190,
    priority: 'high',
    deferrable: true,
    resourceRequirement: 8,
    resourceLabel: '8x NVIDIA H100 SXM5',
    status: 'Scheduled',
  },
  {
    id: 'JOB-9423',
    name: 'Real-time Fraud Classifier Update',
    type: 'batch_inference',
    arrivalTime: '12:00',
    arrivalMinutes: 720,
    deadline: '13:00',
    deadlineMinutes: 780,
    durationMinutes: 45,
    energyKwh: 40,
    priority: 'critical',
    deferrable: false, // Non-deferrable urgent workload
    resourceRequirement: 4,
    resourceLabel: '4x NVIDIA A100 (80GB)',
    status: 'Scheduled',
  },
  {
    id: 'JOB-9424',
    name: 'Multimodal Video Embedding Index',
    type: 'batch_inference',
    arrivalTime: '08:00',
    arrivalMinutes: 480,
    deadline: '23:00',
    deadlineMinutes: 1380,
    durationMinutes: 240, // 4h
    energyKwh: 320,
    priority: 'low',
    deferrable: true,
    resourceRequirement: 4,
    resourceLabel: '4x NVIDIA L40S',
    status: 'Scheduled',
  },
  {
    id: 'JOB-9425',
    name: 'Diffusion Denoising Validation',
    type: 'batch_inference',
    arrivalTime: '09:30',
    arrivalMinutes: 570,
    deadline: '16:00',
    deadlineMinutes: 960,
    durationMinutes: 90, // 1h 30m
    energyKwh: 75,
    priority: 'normal',
    deferrable: true,
    resourceRequirement: 4,
    resourceLabel: '4x NVIDIA A100 (80GB)',
    status: 'Scheduled',
  },
  {
    id: 'JOB-9426',
    name: 'Clinical Bert Fine-tuning (EHR)',
    type: 'fine_tuning',
    arrivalTime: '10:00',
    arrivalMinutes: 600,
    deadline: '20:00',
    deadlineMinutes: 1200,
    durationMinutes: 150, // 2h 30m
    energyKwh: 140,
    priority: 'normal',
    deferrable: true,
    resourceRequirement: 8,
    resourceLabel: '8x NVIDIA H100 SXM5',
    status: 'Scheduled',
  },
];

// Aliases for component convenience
export const mockJobs: Job[] = INITIAL_DEMO_JOBS;
export const mockTrace: TracePoint[] = MOCK_GRID_TRACE_24H;
export const mockTraceMetadata: TraceMetadata = MOCK_TRACE_METADATA;
export const mockSystemStatus: SystemStatus = MOCK_SYSTEM_STATUS;
