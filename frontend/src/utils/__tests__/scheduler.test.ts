import { describe, it, expect } from 'vitest';
import { solveJobsSchedule, runPolicyBenchmark } from '../scheduler';
import { mockJobs, initialSchedulerConfig, MOCK_GRID_TRACE_24H } from '../../data/mockData';

describe('Scheduler Algorithms', () => {
  it('schedules jobs within deadlines and feasible windows', () => {
    const result = solveJobsSchedule(mockJobs, MOCK_GRID_TRACE_24H, initialSchedulerConfig);
    const scheduled = result.jobs;

    expect(scheduled.length).toBe(mockJobs.length);
    scheduled.forEach((job) => {
      const startMin = job.scheduledStartMinutes ?? job.arrivalMinutes;
      const finishMin = startMin + job.durationMinutes;

      // Cannot start before arrival
      expect(startMin).toBeGreaterThanOrEqual(job.arrivalMinutes);

      // Must complete by deadline
      expect(finishMin).toBeLessThanOrEqual(job.deadlineMinutes);

      // Must have explanation
      expect(job.explanation).toBeDefined();
    });
  });

  it('guarantees 0% savings and 0 kg avoided under Flat Carbon Curve', () => {
    // Master prompt requirement: Flat curve with zero variance MUST NOT manufacture savings
    const benchmarkResults = runPolicyBenchmark(
      mockJobs,
      MOCK_GRID_TRACE_24H,
      initialSchedulerConfig,
      'flat'
    );

    expect(benchmarkResults.length).toBe(4);

    benchmarkResults.forEach((policy) => {
      // In a flat curve, shifting does not avoid emissions
      expect(policy.realizedSavingsKg).toBe(0);
      expect(policy.emissionsReductionPct).toBe(0);
    });
  });

  it('returns N/A for backfire rate when no jobs are delayed', () => {
    // When no jobs are delayed, denominator is 0 -> backfire rate MUST be 'N/A'
    const benchmarkResults = runPolicyBenchmark(
      mockJobs,
      MOCK_GRID_TRACE_24H,
      initialSchedulerConfig,
      'no_delay'
    );

    const carbonova = benchmarkResults.find((p) => p.policyId === 'carbonova');
    expect(carbonova).toBeDefined();
    expect(carbonova?.delayedJobsCount).toBe(0);
    expect(carbonova?.backfireRatePct).toBe('N/A');
  });

  it('labels Perfect-Forecast Oracle as reference limit without claiming perfection', () => {
    const benchmarkResults = runPolicyBenchmark(
      mockJobs,
      MOCK_GRID_TRACE_24H,
      initialSchedulerConfig,
      'variable'
    );

    const oracle = benchmarkResults.find((p) => p.policyId === 'oracle');
    expect(oracle).toBeDefined();
    expect(oracle?.badge).toBe('Reference Limit');
    expect(oracle?.description).toContain('Theoretical');
  });
});
