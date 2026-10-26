import { describe, it, expect, beforeAll } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import {
  AppRoutes,
  Overview,
  JobSubmission,
  ScheduleResults,
  PolicyComparison,
  CarbonTimeMachine,
  Methodology,
  GreenGate,
  NotFound,
} from './App';

describe('App Route Navigation & Server Rendering', () => {
  beforeAll(async () => {
    // Eagerly resolve all lazy chunks for server-side static markup tests
    await Promise.all([
      Overview.preload(),
      JobSubmission.preload(),
      ScheduleResults.preload(),
      PolicyComparison.preload(),
      CarbonTimeMachine.preload(),
      Methodology.preload(),
      GreenGate.preload(),
      NotFound.preload(),
    ]);
  });

  it('renders the Overview dashboard at / without crashing', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('CARBONOVA');
    expect(html).toContain('Carbon Intelligence Overview');
  });

  it('renders Submit Job at /submit-job without crashing', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/submit-job']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('Add Computational Job');
    expect(html).toContain('Job Identifier');
  });

  it('renders Schedule Results at /schedule-results without crashing', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/schedule-results']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('Workload Schedule Results');
    expect(html).toContain('Avoided Emissions');
  });

  it('renders Policy Comparison at /policy-comparison without crashing', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/policy-comparison']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('Policy Benchmarks &amp; Sensitivity Analysis');
    expect(html).toContain('Standard FIFO');
    expect(html).toContain('Carbonova');
  });

  it('renders Carbon Time Machine at /carbon-time-machine without crashing', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/carbon-time-machine']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('Carbon Time Machine');
    expect(html).toContain('Simulation Clock');
  });

  it('renders Methodology at /methodology without crashing', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/methodology']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('Scientific &amp; Engineering Methodology');
  });

  it('renders GreenGate at /greengate without crashing', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/greengate']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('GreenGate AI Inference Router');
  });

  it('renders the 404 NotFound page on invalid routes instead of a blank screen', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={['/non-existent-route-xyz']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(html).toContain('Error 404 · Page Not Found');
    expect(html).toContain('Route Does Not Exist');
    expect(html).toContain('Go to Overview');
  });
});
