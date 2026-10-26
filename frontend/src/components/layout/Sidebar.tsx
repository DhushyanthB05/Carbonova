import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  PlusCircle,
  CalendarCheck,
  GitCompare,
  History,
  BookOpen,
  Cpu,
  Menu,
  X,
  Radio,
} from 'lucide-react';
import { SystemStatus } from '../../types';

interface SidebarProps {
  systemStatus: SystemStatus;
}

const PRIMARY_NAV = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/submit-job', label: 'Submit Job', icon: PlusCircle },
  { path: '/schedule-results', label: 'Schedule Results', icon: CalendarCheck },
  { path: '/policy-comparison', label: 'Policy Comparison', icon: GitCompare },
  { path: '/carbon-time-machine', label: 'Carbon Time Machine', icon: History },
  { path: '/methodology', label: 'Methodology', icon: BookOpen },
];

const OPTIONAL_NAV = [
  { path: '/greengate', label: 'GreenGate AI', icon: Cpu, badge: 'Optional' },
];

export const Sidebar: React.FC<SidebarProps> = ({ systemStatus }) => {
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile Drawer Toggle Button */}
      <button
        type="button"
        onClick={() => setIsMobileOpen(true)}
        aria-label="Open navigation sidebar"
        className="lg:hidden fixed top-3 left-4 z-40 p-2 rounded-lg bg-white border border-slate-200 text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Backdrop for Mobile Drawer */}
      {isMobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/40 backdrop-blur-xs transition-opacity"
          onClick={() => setIsMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        aria-label="Main Application Sidebar"
        className={`fixed left-0 top-0 h-full w-64 bg-white border-r border-slate-200 z-50 flex flex-col justify-between shadow-xs transition-transform duration-200 lg:translate-x-0 ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col flex-1 min-h-0">
          {/* Brand Header */}
          <div className="px-5 py-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Leaf + Data Signal Logo Mark */}
              <div
                className="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shrink-0 shadow-sm"
                aria-hidden="true"
              >
                <svg
                  className="w-5 h-5 text-emerald-100"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 2C7 2 3 6 3 11c0 4.5 3.5 8.5 9 10 5.5-1.5 9-5.5 9-10 0-5-4-9-9-9z" />
                  <path d="M12 21V11" />
                  <path d="M9 14l3-3 3 3" />
                </svg>
              </div>

              <div className="flex flex-col">
                <span className="text-[15px] font-bold tracking-tight text-slate-900 leading-none">
                  CARBONOVA
                </span>
                <span className="text-[10px] font-medium text-slate-500 tracking-wide mt-1">
                  Smarter AI. Cleaner Computing.
                </span>
              </div>
            </div>

            {isMobileOpen && (
              <button
                type="button"
                onClick={() => setIsMobileOpen(false)}
                className="lg:hidden text-slate-400 hover:text-slate-700 p-1 rounded-lg"
                aria-label="Close navigation sidebar"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-1">
            <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Core Modules
            </div>

            {PRIMARY_NAV.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/'}
                  onClick={() => setIsMobileOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all group ${
                      isActive
                        ? 'bg-emerald-50 text-emerald-800 font-semibold border-l-3 border-emerald-600'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon
                        className={`w-4 h-4 transition-colors ${
                          isActive ? 'text-emerald-600' : 'text-slate-400 group-hover:text-slate-600'
                        }`}
                      />
                      <span className="truncate">{item.label}</span>
                    </>
                  )}
                </NavLink>
              );
            })}

            <div className="px-3 pt-4 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Extensions
            </div>

            {OPTIONAL_NAV.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setIsMobileOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all group ${
                      isActive
                        ? 'bg-emerald-50 text-emerald-800 font-semibold border-l-3 border-emerald-600'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <div className="flex items-center gap-3">
                        <Icon
                          className={`w-4 h-4 transition-colors ${
                            isActive ? 'text-emerald-600' : 'text-slate-400 group-hover:text-slate-600'
                          }`}
                        />
                        <span className="truncate">{item.label}</span>
                      </div>
                      {item.badge && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-slate-100 text-slate-500">
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* System Status Footnote */}
          <div className="p-3 m-3 bg-slate-50 border border-slate-200 rounded-xl flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                System Status
              </span>
              <span className="flex items-center gap-1.5">
                <Radio
                  className={`w-3.5 h-3.5 ${
                    systemStatus.isOnline ? 'text-emerald-600 animate-pulse' : 'text-amber-500'
                  }`}
                />
                <span className="text-[10px] font-bold text-slate-700">
                  {systemStatus.isOnline ? 'Online' : 'Fallback Mode'}
                </span>
              </span>
            </div>

            <div className="flex flex-col gap-1 text-[11px] text-slate-600 font-mono">
              <div className="flex justify-between">
                <span className="text-slate-400">Grid:</span>
                <span className="font-medium text-slate-700">CAISO-Z2</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Engine:</span>
                <span className="font-medium text-slate-700 truncate max-w-[120px]" title={systemStatus.core}>
                  {systemStatus.version}
                </span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
