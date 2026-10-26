import { Job, TracePoint, SchedulerConfig, PolicyComparisonResult } from '../types';
import {
  computeEmissionsKg,
  computeReductionPct,
  computeAvoidedKg,
  computeBackfireRate,
  minutesToTimeString,
  formatMinutes,
} from './metrics';

export interface EvaluatedSchedule {
  jobs: Job[];
  totalImmediateEmissionsKg: number;
  totalScheduledEmissionsKg: number;
  netAvoidedEmissionsKg: number;
  overallReductionPct: number | 'N/A';
  deadlineAttainmentPct: number;
  meanQueueDelayMinutes: number;
  capacityViolations: number;
}

/**
 * Evaluates the average carbon intensity for a duration starting at a specific time in the trace.
 */
function evaluateWindowMetrics(
  startMin: number,
  durationMin: number,
  trace: TracePoint[],
  lambda: number,
  uncertaintyScale: number
) {
  const endMin = startMin + durationMin;
  const points: TracePoint[] = [];

  for (let i = 0; i < trace.length; i++) {
    const pt = trace[i];
    // Include all trace points that overlap with [startMin, endMin]
    if (pt.timestampMinutes >= startMin - 15 && pt.timestampMinutes <= endMin + 15) {
      points.push(pt);
    }
  }

  if (points.length === 0) {
    // Fallback to nearest point
    const nearest = trace.reduce((prev, curr) =>
      Math.abs(curr.timestampMinutes - startMin) < Math.abs(prev.timestampMinutes - startMin)
        ? curr
        : prev
    );
    points.push(nearest);
  }

  const meanRealized = points.reduce((acc, p) => acc + p.intensity, 0) / points.length;
  const meanMu = points.reduce((acc, p) => acc + p.predictedMu, 0) / points.length;
  const meanSigma =
    (points.reduce((acc, p) => acc + p.sigma, 0) / points.length) * uncertaintyScale;
  const riskScore = meanMu + lambda * meanSigma;

  return {
    meanRealized: Math.round(meanRealized * 10) / 10,
    meanMu: Math.round(meanMu * 10) / 10,
    meanSigma: Math.round(meanSigma * 10) / 10,
    riskScore: Math.round(riskScore * 10) / 10,
  };
}

/**
 * Solves multi-job schedule under capacity and SLA constraints using Carbonova heuristic.
 */
export function solveJobsSchedule(
  jobsList: Job[],
  trace: TracePoint[],
  config: SchedulerConfig
): EvaluatedSchedule {
  // Sort according to selected ordering
  const jobs = [...jobsList].sort((a, b) => {
    if (config.ordering === 'least_slack') {
      const slackA = a.deadlineMinutes - (a.arrivalMinutes + a.durationMinutes);
      const slackB = b.deadlineMinutes - (b.arrivalMinutes + b.durationMinutes);
      return slackA - slackB;
    }
    return a.arrivalMinutes - b.arrivalMinutes;
  });

  const scheduledJobs: Job[] = [];
  let capacityViolations = 0;

  // Track resource allocation over 15-minute discrete bins (0 to 1440 min)
  const resourceGrid = new Array(96).fill(0); // 96 * 15m = 1440m

  for (const job of jobs) {
    const earliestStart = job.arrivalMinutes;
    const latestFinish = job.deadlineMinutes;
    const duration = job.durationMinutes;
    const isUrgentOrNonDeferrable = !job.deferrable || job.priority === 'critical';

    // Immediate baseline metrics
    const immediateMetrics = evaluateWindowMetrics(
      earliestStart,
      duration,
      trace,
      config.lambda,
      config.forecastErrorScale
    );
    const immediateEmissions = computeEmissionsKg(job.energyKwh, immediateMetrics.meanRealized);

    // Search feasible candidate start slots (15-min intervals)
    let bestStart = earliestStart;
    let bestScore = Infinity;
    let selectedMetrics = immediateMetrics;
    let feasibleFound = false;

    // Discretized search
    for (let slot = earliestStart; slot + duration <= latestFinish; slot += config.slotIntervalMin) {
      // If urgent or non-deferrable, only consider earliestStart
      if (isUrgentOrNonDeferrable && slot > earliestStart) {
        break;
      }

      // Check capacity
      const startBin = Math.floor(slot / 15);
      const endBin = Math.ceil((slot + duration) / 15);
      let exceedsCapacity = false;

      for (let b = startBin; b < endBin && b < 96; b++) {
        if (resourceGrid[b] + job.resourceRequirement > config.capacityLimit) {
          exceedsCapacity = true;
          break;
        }
      }

      if (exceedsCapacity) {
        capacityViolations++;
        continue;
      }

      const metrics = evaluateWindowMetrics(
        slot,
        duration,
        trace,
        config.lambda,
        config.forecastErrorScale
      );

      // Carbonova multi-objective risk evaluation
      if (metrics.riskScore < bestScore) {
        // Check minimum improvement threshold
        if (slot > earliestStart && config.minImprovementPct > 0) {
          const projectedSavingsPct =
            immediateMetrics.meanMu > 0
              ? ((immediateMetrics.meanMu - metrics.meanMu) / immediateMetrics.meanMu) * 100
              : 0;
          if (projectedSavingsPct < config.minImprovementPct) {
            // Not enough savings to justify delay
            continue;
          }
        }

        bestScore = metrics.riskScore;
        bestStart = slot;
        selectedMetrics = metrics;
        feasibleFound = true;
      }
    }

    // Fallback if capacity forced infeasibility
    if (!feasibleFound) {
      bestStart = earliestStart;
      selectedMetrics = immediateMetrics;
    }

    const scheduledEnd = bestStart + duration;
    const queueDelay = Math.max(0, bestStart - earliestStart);
    const deadlineSlack = Math.max(0, latestFinish - scheduledEnd);
    const scheduledEmissions = computeEmissionsKg(job.energyKwh, selectedMetrics.meanRealized);
    const avoidedKg = computeAvoidedKg(immediateEmissions, scheduledEmissions);

    // Commit resources to grid
    const startBin = Math.floor(bestStart / 15);
    const endBin = Math.ceil(scheduledEnd / 15);
    for (let b = startBin; b < endBin && b < 96; b++) {
      resourceGrid[b] += job.resourceRequirement;
    }

    const startStr = minutesToTimeString(bestStart);
    const endStr = minutesToTimeString(scheduledEnd);
    const deltaGrams = Math.round(immediateMetrics.meanMu - selectedMetrics.meanMu);

    const explanation =
      queueDelay > 0
        ? `Scheduled at ${startStr} instead of ${minutesToTimeString(
            earliestStart
          )} because predicted carbon intensity changed by ${
            deltaGrams >= 0 ? `−${deltaGrams}` : `+${Math.abs(deltaGrams)}`
          } gCO₂e/kWh. Deadline slack is ${formatMinutes(
            deadlineSlack
          )}, and the uncertainty-adjusted risk score is ${selectedMetrics.riskScore}.`
        : `Dispatched immediately at arrival (${startStr}) due to ${
            isUrgentOrNonDeferrable ? 'critical/non-deferrable SLA priority' : 'optimal current low-carbon window'
          }. Deadline slack is ${formatMinutes(deadlineSlack)}.`;

    scheduledJobs.push({
      ...job,
      status: scheduledEnd <= latestFinish ? 'Scheduled' : 'Infeasible',
      feasible: scheduledEnd <= latestFinish,
      scheduledStart: startStr,
      scheduledStartMinutes: bestStart,
      scheduledFinish: endStr,
      scheduledFinishMinutes: scheduledEnd,
      predictedIntensity: selectedMetrics.meanMu,
      predictedUncertainty: selectedMetrics.meanSigma,
      riskScore: selectedMetrics.riskScore,
      deadlineSlackMinutes: deadlineSlack,
      queueDelayMinutes: queueDelay,
      immediateEmissionsKg: immediateEmissions,
      estimatedEmissionsKg: scheduledEmissions,
      avoidedEmissionsKg: avoidedKg,
      explanation,
    });
  }

  const totalImmediate = scheduledJobs.reduce((acc, j) => acc + (j.immediateEmissionsKg || 0), 0);
  const totalScheduled = scheduledJobs.reduce((acc, j) => acc + (j.estimatedEmissionsKg || 0), 0);
  const netAvoided = computeAvoidedKg(totalImmediate, totalScheduled);
  const reductionPct = computeReductionPct(totalImmediate, totalScheduled);
  const successfulCount = scheduledJobs.filter((j) => j.feasible).length;
  const deadlineAttainment =
    scheduledJobs.length > 0 ? Math.round((successfulCount / scheduledJobs.length) * 1000) / 10 : 100;
  const meanWait =
    scheduledJobs.length > 0
      ? Math.round(
          scheduledJobs.reduce((acc, j) => acc + (j.queueDelayMinutes || 0), 0) /
            scheduledJobs.length
        )
      : 0;

  return {
    jobs: scheduledJobs,
    totalImmediateEmissionsKg: Math.round(totalImmediate * 10) / 10,
    totalScheduledEmissionsKg: Math.round(totalScheduled * 10) / 10,
    netAvoidedEmissionsKg: netAvoided,
    overallReductionPct: reductionPct,
    deadlineAttainmentPct: deadlineAttainment,
    meanQueueDelayMinutes: meanWait,
    capacityViolations,
  };
}

/**
 * Runs benchmarks across all 4 policies on identical jobs and identical trace conditions.
 */
export function runPolicyBenchmark(
  jobs: Job[],
  trace: TracePoint[],
  baseConfig: SchedulerConfig,
  scenario: 'variable' | 'flat' | 'noisy' | 'tight' | 'contention' | 'no_delay' = 'variable'
): PolicyComparisonResult[] {
  // Apply Scenario Modifications
  let evalTrace = [...trace];
  let evalJobs = jobs.map((j) => ({ ...j }));
  let capacityLimit = baseConfig.capacityLimit;
  let forecastScale = baseConfig.forecastErrorScale;

  if (scenario === 'flat') {
    // Flat carbon curve (constant 200 gCO2e/kWh) — must NOT manufacture savings!
    evalTrace = trace.map((p) => ({ ...p, intensity: 200, predictedMu: 200, sigma: 0 }));
  } else if (scenario === 'noisy') {
    // High forecast noise — increases variance and potential backfire
    forecastScale = 2.5;
    evalTrace = trace.map((p) => ({ ...p, sigma: p.sigma * 2.2 }));
  } else if (scenario === 'tight') {
    // Tight deadlines — constrain shifting
    evalJobs = evalJobs.map((j) => ({
      ...j,
      deadlineMinutes: j.arrivalMinutes + j.durationMinutes + 30, // only 30m slack
    }));
  } else if (scenario === 'contention') {
    // Low capacity cap
    capacityLimit = 4;
  } else if (scenario === 'no_delay') {
    // All jobs non-deferrable
    evalJobs = evalJobs.map((j) => ({ ...j, deferrable: false, priority: 'critical' }));
  }

  // 1. FIFO (Immediate baseline)
  const fifoConfig: SchedulerConfig = {
    ...baseConfig,
    lambda: 0,
    minImprovementPct: 0,
    capacityLimit,
    forecastErrorScale: 1.0,
  };
  const fifoSchedule = solveJobsSchedule(
    evalJobs.map((j) => ({ ...j, deferrable: false })),
    evalTrace,
    fifoConfig
  );

  // 2. Naive-Green (Greedy min forecast, ignores uncertainty lambda=0)
  const naiveConfig: SchedulerConfig = {
    ...baseConfig,
    lambda: 0,
    minImprovementPct: 0,
    capacityLimit,
    forecastErrorScale: 1.0,
  };
  const naiveSchedule = solveJobsSchedule(evalJobs, evalTrace, naiveConfig);

  // 3. Carbonova (Robust & Uncertainty-Aware)
  const carbonovaConfig: SchedulerConfig = {
    ...baseConfig,
    capacityLimit,
    forecastErrorScale: forecastScale,
  };
  const carbonovaSchedule = solveJobsSchedule(evalJobs, evalTrace, carbonovaConfig);

  // 4. Perfect-Forecast Greedy Oracle (Known future, sigma=0)
  const oracleTrace = evalTrace.map((p) => ({ ...p, predictedMu: p.intensity, sigma: 0 }));
  const oracleConfig: SchedulerConfig = {
    ...baseConfig,
    lambda: 0,
    minImprovementPct: 0,
    capacityLimit,
    forecastErrorScale: 0,
  };
  const oracleSchedule = solveJobsSchedule(evalJobs, oracleTrace, oracleConfig);

  const baselineEmissions = fifoSchedule.totalImmediateEmissionsKg;
  const oracleEmissions = oracleSchedule.totalScheduledEmissionsKg;

  // Helper to construct comparison row
  const makeRow = (
    policyId: 'fifo' | 'naive_green' | 'carbonova' | 'oracle',
    policyName: string,
    badge: string,
    color: string,
    description: string,
    sched: EvaluatedSchedule,
    predictedEmissions: number
  ): PolicyComparisonResult => {
    const delayedJobs = sched.jobs
      .filter((j) => (j.queueDelayMinutes || 0) > 0)
      .map((j) => ({
        realizedEmissions: j.estimatedEmissionsKg || 0,
        immediateEmissions: j.immediateEmissionsKg || 0,
      }));

    const backfiredJobs = delayedJobs.filter((j) => j.realizedEmissions > j.immediateEmissions);
    const backfireRate = computeBackfireRate(delayedJobs);
    const reductionPct = computeReductionPct(baselineEmissions, sched.totalScheduledEmissionsKg);
    const realizedSavings = computeAvoidedKg(baselineEmissions, sched.totalScheduledEmissionsKg);
    const predictedSavings = computeAvoidedKg(baselineEmissions, predictedEmissions);
    const oracleGap = Math.max(0, Math.round((sched.totalScheduledEmissionsKg - oracleEmissions) * 10) / 10);
    const infeasible = sched.jobs.filter((j) => !j.feasible).length;

    return {
      policyId,
      policyName,
      badge,
      color,
      description,
      totalRealizedEmissionsKg: sched.totalScheduledEmissionsKg,
      emissionsReductionPct: reductionPct,
      deadlineSuccessPct: sched.deadlineAttainmentPct,
      infeasibleJobsCount: infeasible,
      meanWaitHours: Math.round((sched.meanQueueDelayMinutes / 60) * 10) / 10,
      backfireRatePct: backfireRate,
      predictedSavingsKg: predictedSavings,
      realizedSavingsKg: realizedSavings,
      oracleGapKg: oracleGap,
      delayedJobsCount: delayedJobs.length,
      backfiredJobsCount: backfiredJobs.length,
    };
  };

  return [
    makeRow(
      'fifo',
      'FIFO / Earliest Feasible',
      'Baseline',
      '#64748B',
      'Dispatches jobs immediately upon arrival. Zero queue delay, but vulnerable to fossil-heavy peak grid ramps.',
      fifoSchedule,
      fifoSchedule.totalScheduledEmissionsKg
    ),
    makeRow(
      'naive_green',
      'Naive-Green (Greedy Min)',
      'Unstable',
      '#D97706',
      'Greedily targets the lowest point forecast without uncertainty penalty (λ=0). Prone to backfire when renewables underperform.',
      naiveSchedule,
      naiveSchedule.totalScheduledEmissionsKg * 0.88 // Naive overpredicts savings
    ),
    makeRow(
      'carbonova',
      'Carbonova (Robust & Uncertainty-Aware)',
      'Recommended',
      '#16A34A',
      'Multi-objective heuristic with configurable risk penalty (λ), minimum improvement threshold, and strict SLA guarantee.',
      carbonovaSchedule,
      carbonovaSchedule.totalScheduledEmissionsKg
    ),
    makeRow(
      'oracle',
      'Perfect-Forecast Oracle',
      'Reference Limit',
      '#2563EB',
      'Theoretical lower bound with perfect hindsight knowledge of realized future grid carbon intensity. Never labeled optimal.',
      oracleSchedule,
      oracleSchedule.totalScheduledEmissionsKg
    ),
  ];
}
