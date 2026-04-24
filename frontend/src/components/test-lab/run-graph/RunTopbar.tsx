"use client";

import Link from 'next/link';
import { Play, Download, Network, List } from 'lucide-react';
import type { TestRun } from '@/lib/test-lab/types';

interface RunTopbarProps {
  run: TestRun;
  view: 'graph' | 'timeline';
  onViewChange: (v: 'graph' | 'timeline') => void;
  onRerun: () => void;
  rerunning: boolean;
}

const VERDICT_CFG = {
  passed:               { label: 'PASSED',   cls: 'badge badge--passed' },
  passed_with_warnings: { label: 'WARNINGS', cls: 'badge badge--passed_with_warnings' },
  failed:               { label: 'FAILED',   cls: 'badge badge--failed' },
};

function fmtDuration(ms: number | null): string {
  if (ms == null) return '--';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '--';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
}

export function RunTopbar({ run, view, onViewChange, onRerun, rerunning }: RunTopbarProps) {
  const verdict = run.verdict ? VERDICT_CFG[run.verdict as keyof typeof VERDICT_CFG] : null;

  function handleExport() {
    const blob = new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${run.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="topbar" style={{ justifyContent: 'flex-start', gap: 0 }}>
      {/* Logo */}
      <div
        className="flex items-center justify-center flex-shrink-0"
        style={{ width: 44, height: 44, borderRight: '1px solid var(--ork-border)' }}
      >
        <Link href="/">
          <div
            className="flex items-center justify-center"
            style={{
              width: 28, height: 28,
              background: 'color-mix(in oklch, var(--ork-purple) 18%, transparent)',
              border: '1px solid color-mix(in oklch, var(--ork-purple) 30%, transparent)',
              borderRadius: 'var(--radius)',
              color: 'var(--ork-purple)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            ⬡
          </div>
        </Link>
      </div>

      {/* Breadcrumbs */}
      <div
        className="topbar__crumbs"
        style={{ padding: '0 14px', borderRight: '1px solid var(--ork-border)', height: '100%' }}
      >
        <Link href="/test-lab" style={{ color: 'var(--ork-muted-2)' }}>
          TEST LAB
        </Link>
        <span style={{ color: 'var(--ork-border-2)' }}>/</span>
        <strong>{run.id.slice(0, 16)}…</strong>
      </div>

      {/* Status chips */}
      <div className="flex items-center gap-2 px-4">
        {verdict && (
          <span className={verdict.cls}>
            {verdict.label}
          </span>
        )}
        {run.score != null && (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              fontWeight: 700,
              color: run.score >= 80 ? 'var(--ork-green)' : run.score >= 50 ? 'var(--ork-amber)' : 'var(--ork-red)',
            }}
          >
            {Math.round(run.score)}/100
          </span>
        )}
        <div style={{ width: 1, height: 14, background: 'var(--ork-border)' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ork-muted-2)' }}>
          {fmtDuration(run.duration_ms)}
        </span>
        <div style={{ width: 1, height: 14, background: 'var(--ork-border)' }} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ork-muted-2)' }}>
          {fmtDate(run.ended_at)}
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Actions */}
      <div className="topbar__right">
        {/* View toggle */}
        <div
          className="flex items-center overflow-hidden"
          style={{
            background: 'var(--ork-bg)',
            border: '1px solid var(--ork-border)',
            borderRadius: 'var(--radius)',
          }}
        >
          {(['graph', 'timeline'] as const).map((v) => (
            <button
              key={v}
              onClick={() => onViewChange(v)}
              className="topbar__btn"
              style={{
                border: 'none',
                borderRadius: 0,
                color: view === v ? 'var(--ork-cyan)' : 'var(--ork-muted-2)',
                background: view === v ? 'color-mix(in oklch, var(--ork-cyan) 10%, transparent)' : 'transparent',
                gap: 5,
              }}
            >
              {v === 'graph' ? <Network size={11} /> : <List size={11} />}
              {v === 'graph' ? 'Graph' : 'Timeline'}
            </button>
          ))}
        </div>

        <button onClick={handleExport} className="topbar__btn">
          <Download size={11} />
          Export
        </button>

        <button
          onClick={onRerun}
          disabled={rerunning}
          className="topbar__btn"
          style={{
            background: 'color-mix(in oklch, var(--ork-cyan) 10%, transparent)',
            borderColor: 'color-mix(in oklch, var(--ork-cyan) 30%, transparent)',
            color: 'var(--ork-cyan)',
            opacity: rerunning ? 0.6 : 1,
            fontWeight: 700,
          }}
        >
          <Play size={11} fill="currentColor" />
          {rerunning ? 'RUNNING…' : 'RE-RUN'}
        </button>
      </div>
    </div>
  );
}
