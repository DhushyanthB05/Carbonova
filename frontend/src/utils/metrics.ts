/**
 * Carbonova Core Metrics and Formatter Functions
 */

/**
 * Computes emissions in kgCO2e from energy (kWh) and carbon intensity (gCO2e/kWh).
 * Formula: (kWh * gCO2e/kWh) / 1000 = kgCO2e
 */
export function computeEmissionsKg(kwh: number, intensity_g_per_kwh: number): number {
  if (kwh <= 0 || intensity_g_per_kwh <= 0) return 0;
  const kg = (kwh * intensity_g_per_kwh) / 1000;
  return Math.round(kg * 100) / 100;
}

/**
 * Computes percentage reduction from a baseline.
 * Returns 'N/A' if baseline is non-positive or undefined.
 */
export function computeReductionPct(baselineKg: number, policyKg: number): number | 'N/A' {
  if (baselineKg <= 0 || isNaN(baselineKg) || isNaN(policyKg)) return 'N/A';
  const reduction = ((baselineKg - policyKg) / baselineKg) * 100;
  return Math.round(reduction * 10) / 10;
}

/**
 * Computes net avoided carbon in kgCO2e.
 */
export function computeAvoidedKg(baselineKg: number, policyKg: number): number {
  if (baselineKg <= policyKg) return 0;
  return Math.round((baselineKg - policyKg) * 100) / 100;
}

/**
 * Computes backfire rate:
 * Percentage of delayed jobs whose realized emissions exceeded their immediate-run counterfactual.
 * CRITICAL RULE: If no jobs were delayed, return 'N/A' (never 0%).
 */
export function computeBackfireRate(
  delayedJobs: Array<{ realizedEmissions: number; immediateEmissions: number }>
): number | 'N/A' {
  if (!delayedJobs || delayedJobs.length === 0) {
    return 'N/A';
  }
  const backfireCount = delayedJobs.filter(
    (j) => j.realizedEmissions > j.immediateEmissions
  ).length;

  return Math.round((backfireCount / delayedJobs.length) * 1000) / 10;
}

/**
 * Normalized impact calculator per 1,000 comparable jobs:
 * Savings per 1,000 jobs = (baseline emissions - policy emissions) / jobs evaluated * 1,000
 */
export function computeNormalizedSavingsPer1000(
  baselineKg: number,
  policyKg: number,
  evaluatedCount: number
): number | 'N/A' {
  if (evaluatedCount <= 0 || baselineKg <= policyKg) return 'N/A';
  const savings = ((baselineKg - policyKg) / evaluatedCount) * 1000;
  return Math.round(savings);
}

/**
 * Converts HH:MM string to minutes from 00:00.
 */
export function timeStringToMinutes(timeStr: string): number {
  if (!timeStr) return 0;
  const match = timeStr.match(/(\d{1,2}):(\d{2})/);
  if (!match) return 0;
  return parseInt(match[1], 10) * 60 + parseInt(match[2], 10);
}

/**
 * Converts minutes from 00:00 to HH:MM formatted string.
 */
export function minutesToTimeString(minutes: number): string {
  const norm = ((minutes % 1440) + 1440) % 1440;
  const h = Math.floor(norm / 60);
  const m = Math.round(norm % 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

/**
 * Formats minutes into human-readable duration, e.g. "3h 30m".
 */
export function formatMinutes(minutes: number): string {
  if (minutes < 0) return '0m';
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}
