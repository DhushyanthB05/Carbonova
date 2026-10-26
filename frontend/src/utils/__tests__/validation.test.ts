import { describe, it, expect } from 'vitest';
import { validateJobSubmission, JobInput } from '../validation';
import { Job } from '../../types';

describe('Job Submission Validation', () => {
  const existingJobs: Job[] = [
    {
      id: 'JOB-101',
      name: 'Existing Training Job',
      type: 'training',
      arrivalTime: '08:00',
      arrivalMinutes: 480,
      deadline: '16:00',
      deadlineMinutes: 960,
      durationMinutes: 120,
      energyKwh: 50,
      priority: 'normal',
      deferrable: true,
      resourceRequirement: 4,
      status: 'Scheduled',
    },
  ];

  const validJobInput: JobInput = {
    id: 'JOB-102',
    name: 'Fine-Tuning Llama',
    arrivalTime: '10:00',
    deadlineTime: '15:00',
    durationMinutes: 120,
    energyKwh: 40,
    resourceRequirement: 2,
  };

  it('validates a completely feasible and unique job input', () => {
    const result = validateJobSubmission(validJobInput, existingJobs);
    expect(result.isValid).toBe(true);
    expect(result.errors).toEqual({});
    expect(result.isTimingFeasible).toBe(true);
    expect(result.slackMinutes).toBe(180); // 15:00 (900m) - (10:00 (600m) + 120m) = 180m
    expect(result.isDuplicateId).toBe(false);
  });

  it('rejects an infeasible deadline where arrival + duration > deadline', () => {
    const infeasibleInput: JobInput = {
      ...validJobInput,
      arrivalTime: '14:00',
      deadlineTime: '15:00',
      durationMinutes: 120, // Requires 2h, only 1h window available
    };
    const result = validateJobSubmission(infeasibleInput, existingJobs);
    expect(result.isValid).toBe(false);
    expect(result.isTimingFeasible).toBe(false);
    expect(result.slackMinutes).toBe(0);
    expect(result.errors.timing).toBeDefined();
  });

  it('accepts a zero-slack tight deadline where arrival + duration === deadline', () => {
    const tightInput: JobInput = {
      ...validJobInput,
      arrivalTime: '10:00',
      deadlineTime: '12:00',
      durationMinutes: 120,
    };
    const result = validateJobSubmission(tightInput, existingJobs);
    expect(result.isValid).toBe(true);
    expect(result.isTimingFeasible).toBe(true);
    expect(result.slackMinutes).toBe(0);
  });

  it('detects duplicate Job IDs case-insensitively', () => {
    const duplicateInput: JobInput = {
      ...validJobInput,
      id: 'job-101', // existing is 'JOB-101'
    };
    const result = validateJobSubmission(duplicateInput, existingJobs);
    expect(result.isValid).toBe(false);
    expect(result.isDuplicateId).toBe(true);
    expect(result.errors.id).toContain('already exists');
  });

  it('rejects job IDs with fewer than 3 characters', () => {
    const shortIdInput: JobInput = {
      ...validJobInput,
      id: 'AB',
    };
    const result = validateJobSubmission(shortIdInput, existingJobs);
    expect(result.isValid).toBe(false);
    expect(result.isIdValid).toBe(false);
    expect(result.errors.id).toBeDefined();
  });

  it('rejects empty workload names', () => {
    const emptyNameInput: JobInput = {
      ...validJobInput,
      name: '   ',
    };
    const result = validateJobSubmission(emptyNameInput, existingJobs);
    expect(result.isValid).toBe(false);
    expect(result.errors.name).toBeDefined();
  });

  it('rejects non-positive and excessive durations', () => {
    const zeroDuration = validateJobSubmission({ ...validJobInput, durationMinutes: 0 }, existingJobs);
    expect(zeroDuration.isValid).toBe(false);
    expect(zeroDuration.isDurationValid).toBe(false);

    const negativeDuration = validateJobSubmission({ ...validJobInput, durationMinutes: -30 }, existingJobs);
    expect(negativeDuration.isValid).toBe(false);
    expect(negativeDuration.isDurationValid).toBe(false);

    const over24hDuration = validateJobSubmission({ ...validJobInput, durationMinutes: 1441 }, existingJobs);
    expect(over24hDuration.isValid).toBe(false);
    expect(over24hDuration.isDurationValid).toBe(false);
  });

  it('rejects non-positive energy consumption', () => {
    const zeroEnergy = validateJobSubmission({ ...validJobInput, energyKwh: 0 }, existingJobs);
    expect(zeroEnergy.isValid).toBe(false);
    expect(zeroEnergy.isEnergyValid).toBe(false);

    const negativeEnergy = validateJobSubmission({ ...validJobInput, energyKwh: -15 }, existingJobs);
    expect(negativeEnergy.isValid).toBe(false);
    expect(negativeEnergy.isEnergyValid).toBe(false);
  });

  it('rejects non-positive resource allocations', () => {
    const zeroResource = validateJobSubmission({ ...validJobInput, resourceRequirement: 0 }, existingJobs);
    expect(zeroResource.isValid).toBe(false);
    expect(zeroResource.isResourceValid).toBe(false);

    const fractionalResource = validateJobSubmission({ ...validJobInput, resourceRequirement: 1.5 }, existingJobs);
    expect(fractionalResource.isValid).toBe(false);
    expect(fractionalResource.isResourceValid).toBe(false);
  });
});
