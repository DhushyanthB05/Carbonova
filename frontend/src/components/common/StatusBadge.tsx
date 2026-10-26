import React from 'react';
import { JobStatus } from '../../types';

interface StatusBadgeProps {
  status: JobStatus;
  className?: string;
}

const STATUS_STYLES: Record<JobStatus, { bg: string; text: string; border: string }> = {
  Scheduled: {
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
  },
  Running: {
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
  },
  Completed: {
    bg: 'bg-slate-100',
    text: 'text-slate-700',
    border: 'border-slate-200',
  },
  Failed: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
  },
  Infeasible: {
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const style = STATUS_STYLES[status] || STATUS_STYLES.Scheduled;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      {status}
    </span>
  );
};
