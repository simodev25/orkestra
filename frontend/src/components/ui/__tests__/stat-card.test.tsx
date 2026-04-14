import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatCard } from '../stat-card';

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard label="Total Agents" value={42} />);
    expect(screen.getByText('Total Agents')).toBeDefined();
    expect(screen.getByText('42')).toBeDefined();
  });

  it('renders sub text when provided', () => {
    render(<StatCard label="Agents" value={5} sub="active in prod" />);
    expect(screen.getByText('active in prod')).toBeDefined();
  });

  it('does not render sub element when sub is omitted', () => {
    render(<StatCard label="Agents" value={5} />);
    expect(screen.queryByText(/active/)).toBeNull();
  });

  it('applies cyan border by default', () => {
    const { container } = render(<StatCard label="L" value="V" />);
    const panel = container.firstChild as HTMLElement;
    expect(panel.className).toContain('ork-cyan');
  });

  it('applies green border when accent=green', () => {
    const { container } = render(<StatCard label="L" value="V" accent="green" />);
    const panel = container.firstChild as HTMLElement;
    expect(panel.className).toContain('ork-green');
  });

  it('applies red border when accent=red', () => {
    const { container } = render(<StatCard label="L" value="V" accent="red" />);
    const panel = container.firstChild as HTMLElement;
    expect(panel.className).toContain('ork-red');
  });

  it('renders string value correctly', () => {
    render(<StatCard label="Status" value="healthy" />);
    expect(screen.getByText('healthy')).toBeDefined();
  });
});
