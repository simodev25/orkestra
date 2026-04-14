import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../status-badge';

describe('StatusBadge', () => {
  it('renders the status text', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByRole('status')).toHaveTextContent('running');
  });

  it('replaces underscores with spaces', () => {
    render(<StatusBadge status="waiting_review" />);
    expect(screen.getByRole('status')).toHaveTextContent('waiting review');
  });

  it('has accessible aria-label with readable status', () => {
    render(<StatusBadge status="passed_with_warnings" />);
    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      'Status: passed with warnings',
    );
  });

  it('applies known-status CSS class (not default fallback)', () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByRole('status');
    expect(badge.className).not.toContain('bg-ork-dim');
    expect(badge.className).toContain('ork-green');
  });

  it('applies default fallback class for unknown status', () => {
    render(<StatusBadge status="totally_unknown_status" />);
    const badge = screen.getByRole('status');
    expect(badge.className).toContain('bg-ork-dim');
  });

  it('renders "failed" in red class', () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByRole('status').className).toContain('ork-red');
  });

  it('renders "running" in cyan class', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByRole('status').className).toContain('ork-cyan');
  });

  it('renders "pending" in amber class', () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByRole('status').className).toContain('ork-amber');
  });
});
