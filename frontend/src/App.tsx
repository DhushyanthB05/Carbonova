import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { PageLoadingFallback } from './components/common/PageLoadingFallback';
import { lazyWithPreload } from './utils/lazyWithPreload';

export const Overview = lazyWithPreload(() => import('./pages/Overview'), 'Overview');
export const JobSubmission = lazyWithPreload(() => import('./pages/JobSubmission'), 'JobSubmission');
export const ScheduleResults = lazyWithPreload(() => import('./pages/ScheduleResults'), 'ScheduleResults');
export const PolicyComparison = lazyWithPreload(() => import('./pages/PolicyComparison'), 'PolicyComparison');
export const CarbonTimeMachine = lazyWithPreload(() => import('./pages/CarbonTimeMachine'), 'CarbonTimeMachine');
export const Methodology = lazyWithPreload(() => import('./pages/Methodology'), 'Methodology');
export const GreenGate = lazyWithPreload(() => import('./pages/GreenGate'), 'GreenGate');
export const NotFound = lazyWithPreload(() => import('./pages/NotFound'), 'NotFound');

export const AppRoutes: React.FC = () => {
  return (
    <Suspense fallback={<PageLoadingFallback />}>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Overview />} />
          <Route path="submit-job" element={<JobSubmission />} />
          <Route path="schedule-results" element={<ScheduleResults />} />
          <Route path="policy-comparison" element={<PolicyComparison />} />
          <Route path="carbon-time-machine" element={<CarbonTimeMachine />} />
          <Route path="methodology" element={<Methodology />} />
          <Route path="greengate" element={<GreenGate />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
};

export const App: React.FC = () => {
  return (
    <ErrorBoundary fallbackTitle="Application Initialization Error">
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </ErrorBoundary>
  );
};

export default App;
