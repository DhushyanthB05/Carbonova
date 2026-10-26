import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { PageLoadingFallback } from '../common/PageLoadingFallback';
import { getSystemHealth } from '../../services/api';
import { SystemStatus } from '../../types';
import { MOCK_SYSTEM_STATUS } from '../../data/mockData';

const ROUTE_INFO: Record<string, { title: string; subtitle: string }> = {
  '/': {
    title: 'Carbon Intelligence Overview',
    subtitle: 'Understand grid emissions. Schedule smarter. Compute responsibly.',
  },
  '/submit-job': {
    title: 'Workload Intake & Scheduling',
    subtitle: 'Submit computing jobs and solve optimal carbon-aware execution windows.',
  },
  '/schedule-results': {
    title: 'Schedule Results & Dispatch Gantt',
    subtitle: 'Inspect scheduled execution windows, capacity boundaries, and solver rationale.',
  },
  '/policy-comparison': {
    title: 'Policy Comparison & Benchmarks',
    subtitle: 'Empirical multi-policy benchmark across 500 trace seeds with backfire analysis.',
  },
  '/carbon-time-machine': {
    title: 'Carbon Time Machine',
    subtitle: 'Interactive temporal replay and reactive scheduler recomputation engine.',
  },
  '/methodology': {
    title: 'Methodology & Scientific Model',
    subtitle: 'Formulas, provenance architecture, heuristics, research citations, and limitations.',
  },
  '/greengate': {
    title: 'GreenGate AI Semantic Router',
    subtitle: 'Adaptive multi-tier LLM inference routing based on query complexity and grid intensity.',
  },
};

export const AppShell: React.FC = () => {
  const location = useLocation();
  const [systemStatus, setSystemStatus] = useState<SystemStatus>(MOCK_SYSTEM_STATUS);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchStatus = async () => {
    try {
      const status = await getSystemHealth();
      setSystemStatus(status);
    } catch {
      // Offline fallback
      setSystemStatus({
        ...MOCK_SYSTEM_STATUS,
        isOnline: false,
        mode: 'Demo Mode (Simulation)',
        lastUpdated: new Date().toLocaleTimeString(),
      });
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchStatus();
    setTimeout(() => {
      setIsRefreshing(false);
      window.dispatchEvent(new Event('carbonova:refresh'));
    }, 300);
  };

  const currentRoute = ROUTE_INFO[location.pathname] || {
    title: 'Carbonova',
    subtitle: 'Carbon-aware computing and intelligent workload scheduling platform',
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#111827] flex">
      {/* Sidebar */}
      <Sidebar systemStatus={systemStatus} />

      {/* Main Container */}
      <div className="flex-1 lg:pl-64 flex flex-col min-w-0 transition-all duration-200">
        <Header
          title={currentRoute.title}
          subtitle={currentRoute.subtitle}
          systemStatus={systemStatus}
          isRefreshing={isRefreshing}
          onRefresh={handleRefresh}
        />

        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
          <ErrorBoundary fallbackTitle="View Rendering Error">
            <React.Suspense fallback={<PageLoadingFallback />}>
              <Outlet />
            </React.Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
};
