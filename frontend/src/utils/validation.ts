import { Job } from '../types';
import { timeStringToMinutes } from './metrics';

export interface JobInput {
  id: string;
  name: string;
  arrivalTime: string;
  deadlineTime: string;
  durationMinutes: number;
  energyKwh: number;
  resourceRequirement: number;
}

export interface ValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
  slackMinutes: number;
  isTimingFeasible: boolean;
  isDuplicateId: boolean;
  isDurationValid: boolean;
  isEnergyValid: boolean;
  isResourceValid: boolean;
  isIdValid: boolean;
}

/**
 * Validates a job submission against scheduling constraints and data integrity rules.
 */
export function validateJobSubmission(
  input: JobInput,
  existingJobs: Job[] = []
): ValidationResult {
  const errors: Record<string, string> = {};

  const trimmedId = input.id.trim();
  const trimmedName = input.name.trim();

  // ID validation
  const isDuplicateId = existingJobs.some(
    (j) => j.id.trim().toUpperCase() === trimmedId.toUpperCase()
  );
  const isIdValid = trimmedId.length >= 3 && !isDuplicateId;

  if (trimmedId.length < 3) {
    errors.id = 'Job identifier must be at least 3 characters.';
  } else if (isDuplicateId) {
    errors.id = `Job ID "${trimmedId}" already exists in the queue.`;
  }

  // Name validation
  if (trimmedName.length === 0) {
    errors.name = 'Workload name is required.';
  }

  // Time & Feasibility
  const arrivalMin = timeStringToMinutes(input.arrivalTime);
  const deadlineMin = timeStringToMinutes(input.deadlineTime);
  const isTimingFeasible = deadlineMin >= arrivalMin + input.durationMinutes;
  const slackMinutes = Math.max(0, deadlineMin - (arrivalMin + input.durationMinutes));

  if (!isTimingFeasible) {
    errors.timing = `Deadline (${input.deadlineTime}) must allow at least ${input.durationMinutes} minutes after arrival (${input.arrivalTime}).`;
  }

  // Duration
  const isDurationValid = input.durationMinutes > 0 && input.durationMinutes <= 1440;
  if (!isDurationValid) {
    errors.duration = 'Duration must be between 1 minute and 1440 minutes (24 hours).';
  }

  // Energy
  const isEnergyValid = input.energyKwh > 0;
  if (!isEnergyValid) {
    errors.energy = 'Estimated energy consumption must be greater than 0 kWh.';
  }

  // Resource / GPUs
  const isResourceValid = input.resourceRequirement > 0 && Number.isInteger(input.resourceRequirement);
  if (!isResourceValid) {
    errors.resource = 'Resource requirement must be at least 1 compute node/GPU.';
  }

  const isValid =
    isIdValid &&
    trimmedName.length > 0 &&
    isTimingFeasible &&
    isDurationValid &&
    isEnergyValid &&
    isResourceValid;

  return {
    isValid,
    errors,
    slackMinutes,
    isTimingFeasible,
    isDuplicateId,
    isDurationValid,
    isEnergyValid,
    isResourceValid,
    isIdValid,
  };
}
