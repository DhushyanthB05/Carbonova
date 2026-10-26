import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { Layers, Sparkles } from 'lucide-react';
import { MetricCard } from '../common/MetricCard';

describe('MetricCard Rendering & Icon Handling', () => {
  it('renders correctly when icon is passed as a Lucide component object (icon={Layers})', () => {
    // This was the exact bug that caused the white screen crash on Overview!
    const html = renderToStaticMarkup(
      <MetricCard
        title="Total Workloads"
        value={12}
        unit="jobs"
        icon={Layers}
        tooltip="Test metric"
      />
    );

    expect(html).toContain('Total Workloads');
    expect(html).toContain('12');
    expect(html).toContain('jobs');
    expect(html).toContain('<svg');
  });

  it('renders correctly when icon is passed as a React element (icon={<Sparkles />})', () => {
    const html = renderToStaticMarkup(
      <MetricCard
        title="Avoided Emissions"
        value="24.5"
        unit="kgCO₂e"
        icon={<Sparkles className="w-4 h-4" />}
        tooltip="Avoided carbon"
      />
    );

    expect(html).toContain('Avoided Emissions');
    expect(html).toContain('24.5');
    expect(html).toContain('<svg');
  });

  it('renders with baseline comparison and provenance badge', () => {
    const html = renderToStaticMarkup(
      <MetricCard
        title="Realized Emissions"
        value="48.2"
        unit="kgCO₂e"
        icon={Layers}
        comparison={{
          text: '-15% reduction',
          positive: true,
          baselineName: 'FIFO Baseline',
        }}
        provenanceType="measured"
        tooltip="Realized carbon"
      />
    );

    expect(html).toContain('Realized Emissions');
    expect(html).toContain('-15% reduction');
    expect(html).toContain('vs FIFO Baseline');
    expect(html).toContain('Measured Energy');
  });
});
