import { describe, it, expect } from 'vitest';
import {
  computeEmissionsKg,
  computeAvoidedKg,
  computeReductionPct,
  computeBackfireRate,
  computeNormalizedSavingsPer1000,
  timeStringToMinutes,
  minutesToTimeString,
  formatMinutes,
} from '../metrics';

describe('Metrics Utilities', () => {
  describe('computeEmissionsKg', () => {
    it('calculates operational emissions: kWh * gCO2e/kWh / 1000', () => {
      // 10 kWh at 250 gCO2e/kWh = 2500 gCO2e = 2.5 kgCO2e
      const emissions = computeEmissionsKg(10, 250);
      expect(emissions).toBe(2.5);
    });

    it('returns 0 for non-positive kWh or intensity', () => {
      expect(computeEmissionsKg(0, 250)).toBe(0);
      expect(computeEmissionsKg(10, 0)).toBe(0);
      expect(computeEmissionsKg(-5, 200)).toBe(0);
    });
  });

  describe('computeAvoidedKg', () => {
    it('calculates net avoided emissions', () => {
      // Baseline 10.5 kg, Scheduled 7.2 kg -> 3.3 kg avoided
      expect(computeAvoidedKg(10.5, 7.2)).toBe(3.3);
    });

    it('returns 0 when scheduled emissions exceed baseline', () => {
      expect(computeAvoidedKg(5.0, 6.2)).toBe(0);
    });
  });

  describe('computeReductionPct', () => {
    it('calculates emissions reduction percentage accurately', () => {
      // Baseline 100 kg, Scheduled 70 kg -> 30% reduction
      expect(computeReductionPct(100, 70)).toBe(30);
    });

    it('returns N/A when baseline emissions are zero or negative', () => {
      expect(computeReductionPct(0, 50)).toBe('N/A');
      expect(computeReductionPct(-10, 50)).toBe('N/A');
    });

    it('returns 0 when policy emissions equal baseline, and negative when exceeding', () => {
      expect(computeReductionPct(100, 100)).toBe(0);
      expect(computeReductionPct(100, 120)).toBe(-20);
    });
  });

  describe('computeBackfireRate', () => {
    it('returns N/A when no jobs are delayed (statistical edge case)', () => {
      // Denominator is 0 -> MUST return 'N/A', never 0%
      expect(computeBackfireRate([])).toBe('N/A');
    });

    it('returns 0% when jobs are delayed but none backfired', () => {
      const delayed = [
        { realizedEmissions: 1.2, immediateEmissions: 2.0 },
        { realizedEmissions: 0.8, immediateEmissions: 1.5 },
      ];
      expect(computeBackfireRate(delayed)).toBe(0);
    });

    it('computes correct backfire percentage when realization exceeds immediate', () => {
      const delayed = [
        { realizedEmissions: 2.5, immediateEmissions: 1.8 }, // Backfired!
        { realizedEmissions: 1.0, immediateEmissions: 2.0 }, // Succeeded
      ];
      // 1 out of 2 = 50%
      expect(computeBackfireRate(delayed)).toBe(50);
    });
  });

  describe('computeNormalizedSavingsPer1000', () => {
    it('scales avoided emissions to 1,000 jobs', () => {
      // Evaluated 10 jobs, saved 20 kg (2 kg/job) -> 2,000 kg per 1,000 jobs
      expect(computeNormalizedSavingsPer1000(50, 30, 10)).toBe(2000);
    });

    it('returns N/A when evaluated count is zero or no savings occurred', () => {
      expect(computeNormalizedSavingsPer1000(50, 30, 0)).toBe('N/A');
      expect(computeNormalizedSavingsPer1000(30, 50, 10)).toBe('N/A');
    });
  });

  describe('Time conversion utilities', () => {
    it('converts HH:MM to minutes correctly', () => {
      expect(timeStringToMinutes('00:00')).toBe(0);
      expect(timeStringToMinutes('08:30')).toBe(510);
      expect(timeStringToMinutes('14:45')).toBe(885);
      expect(timeStringToMinutes('23:59')).toBe(1439);
    });

    it('converts minutes to HH:MM string format', () => {
      expect(minutesToTimeString(0)).toBe('00:00');
      expect(minutesToTimeString(510)).toBe('08:30');
      expect(minutesToTimeString(885)).toBe('14:45');
    });

    it('formats minutes into human-readable duration', () => {
      expect(formatMinutes(45)).toBe('45m');
      expect(formatMinutes(120)).toBe('2h');
      expect(formatMinutes(150)).toBe('2h 30m');
    });
  });
});
