import React from 'react';

export const LoadingSkeleton: React.FC<{ className?: string }> = ({
  className = 'h-6 w-full',
}) => {
  return <div className={`animate-pulse bg-slate-100 rounded-lg ${className}`} />;
};

export const DashboardSkeleton: React.FC = () => {
  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full p-6 animate-pulse">
      <div className="h-10 w-64 bg-slate-100 rounded-lg" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 bg-slate-100 rounded-xl" />
        ))}
      </div>
      <div className="h-80 bg-slate-100 rounded-xl" />
      <div className="h-64 bg-slate-100 rounded-xl" />
    </div>
  );
};
