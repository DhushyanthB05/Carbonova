import { describe, it, expect, beforeEach } from 'vitest';
import {
  getSystemHealth,
  getCarbonTrace,
  submitJob,
  removeJob,
  runScheduler,
  getPolicyBenchmarks,
  runGreenGateInference,
  resetDemoState,
} from '../api';
import { initialSchedulerConfig } from '../../data/mockData';

describe('API Service and Simulation Engine', () => {
  beforeEach(() => {
    resetDemoState();
  });

  it('reports transparent simulation mode when backend API is offline', async () => {
    const health = await getSystemHealth();
    expect(health.isOnline).toBe(false);
    expect(health.mode).toContain('Demo Mode (Simulation)');
    expect(health.lastUpdated).toBeDefined();
  });

  it('fetches carbon trace and metadata with realistic fallback telemetry', async () => {
    const { trace, metadata } = await getCarbonTrace('CAISO-Z2');
    expect(Array.isArray(trace)).toBe(true);
    expect(trace.length).toBeGreaterThan(0);
    expect(metadata.region).toContain('CAISO-Z2');
    expect(metadata.sourceType).toBe('recorded');
    expect(metadata.units).toBe('gCO₂e/kWh');
  });

  it('submits a new computational job and adds it to the queue', async () => {
    const newJob = await submitJob({
      id: 'JOB-TEST-99',
      name: 'Evaluation Benchmark Run',
      type: 'batch_inference',
      arrivalTime: '09:00',
      arrivalMinutes: 540,
      deadline: '17:00',
      deadlineMinutes: 1020,
      durationMinutes: 90,
      energyKwh: 35,
      priority: 'high',
      deferrable: true,
      resourceRequirement: 4,
      resourceLabel: '4x A100 GPU',
    });

    expect(newJob.id).toBe('JOB-TEST-99');
    expect(newJob.status).toBe('Scheduled');
  });

  it('removes a job from the active queue', async () => {
    const removed = await removeJob('JOB-101');
    expect(removed).toBe(true);
  });

  it('runs the GreenSchedule solver with risk-aware configuration', async () => {
    const result = await runScheduler(initialSchedulerConfig);
    expect(result).toBeDefined();
    expect(result.jobs.length).toBeGreaterThan(0);
    expect(result.netAvoidedEmissionsKg).toBeGreaterThanOrEqual(0);
    expect(typeof result.overallReductionPct).toBe('number');
  });

  it('retrieves policy benchmark comparisons for variable and flat scenarios', async () => {
    const benchmarksVariable = await getPolicyBenchmarks(initialSchedulerConfig, 'variable');
    expect(benchmarksVariable.length).toBe(4);

    const policies = benchmarksVariable.map((b) => b.policyId);
    expect(policies).toContain('fifo');
    expect(policies).toContain('naive_green');
    expect(policies).toContain('carbonova');
    expect(policies).toContain('oracle');

    const benchmarksFlat = await getPolicyBenchmarks(initialSchedulerConfig, 'flat');
    benchmarksFlat.forEach((p) => {
      expect(p.realizedSavingsKg).toBe(0);
      expect(p.emissionsReductionPct).toBe(0);
    });
  });

  it('routes queries correctly in GreenGate LLM router', async () => {
    // Simple query should be handled by Tier-1 small model
    const simple = await runGreenGateInference('What is carbon intensity?', 0.85);
    expect(simple.routingDecision).toBe('Tier-1 Small (Fast)');
    expect(simple.modelName).toBe('Mistral-7B-Instruct');
    expect(simple.qualityFloorPassed).toBe(true);
    expect(simple.savingsVsLargePct).toBeGreaterThan(0);

    // Complex query should be routed to Tier-2 large model
    const complex = await runGreenGateInference(
      'Write a Python program to explain how backfire occurs in carbon-aware grid scheduling and calculate carbon intensity variance.',
      0.85
    );
    expect(complex.routingDecision).toBe('Tier-2 Large (Deep)');
    expect(complex.modelName).toBe('Llama-3-70B-Instruct');
    expect(complex.qualityFloorPassed).toBe(true);
    expect(complex.savingsVsLargePct).toBe(0);
  });
});
