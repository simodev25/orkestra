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
  passed:               { label: 'PASSED',   color: '#10b981', bg: 'rgba(16,185,129,0.1)',   border: 'rgba(16,185,129,0.25)' },
  passed_with_warnings: { label: 'WARNINGS', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',   border: 'rgba(245,158,11,0.25)' },
  failed:               { label: 'FAILED',   color: '#ef4444', bg: 'rgba(239,68,68,0.1)',    border: 'rgba(239,68,68,0.25)' },
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
    <div
      className="flex items-center h-[52px] flex-shrink-0"
      style={{
        background: 'rgba(9,9,18,0.97)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center justify-center flex-shrink-0"
        style={{ width: 52, height: 52, borderRight: '1px solid rgba(255,255,255,0.06)' }}
      >
        <Link href="/">
          <div
            className="flex items-center justify-center rounded-[9px] text-[15px] font-extrabold"
            style={{
              width: 32, height: 32,
              background: 'linear-gradient(135deg, rgba(167,139,250,0.3), rgba(0,212,255,0.2))',
              border: '1px solid rgba(167,139,250,0.4)',
              color: '#a78bfa',
              boxShadow: '0 0 20px rgba(167,139,250,0.15)',
            }}
          >
            ⬡
          </div>
        </Link>
      </div>

      {/* Breadcrumb */}
      <div
        className="flex items-center gap-2 px-4 h-full"
        style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}
      >
        <Link href="/test-lab" className="text-[12px] font-mono transition-colors hover:text-ork-cyan" style={{ color: '#3f3f5a' }}>
          TEST LAB
        </Link>
        <span style={{ color: '#252538' }}>/</span>
        <span className="text-[12px] font-mono font-semibold" style={{ color: '#71717a' }}>
          {run.id.slice(0, 16)}…
        </span>
      </div>

      {/* Status chips */}
      <div className="flex items-center gap-2.5 px-4">
        {verdict && (
          <div
            className="flex items-center gap-1.5 rounded-full px-3 py-1"
            style={{
              background: verdict.bg, border: `1px solid ${verdict.border}`,
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: verdict.color,
            }}
          >
            <div
              className="rounded-full"
              style={{
                width: 6, height: 6, background: verdict.color,
                animation: 'verdictPulse 2s ease-in-out infinite',
              }}
            />
            {verdict.label}
          </div>
        )}
        {run.score != null && (
          <span className="font-mono text-[13px] font-bold" style={{ color: run.score >= 80 ? '#10b981' : run.score >= 50 ? '#f59e0b' : '#ef4444' }}>
            {Math.round(run.score)}/100
          </span>
        )}
        <div style={{ width: 1, height: 14, background: '#1e1e2e' }} />
        <span className="font-mono text-[11px]" style={{ color: '#3f3f5a' }}>
          {fmtDuration(run.duration_ms)}
        </span>
        <div style={{ width: 1, height: 14, background: '#1e1e2e' }} />
        <span className="font-mono text-[11px]" style={{ color: '#3f3f5a' }}>
          {fmtDate(run.ended_at)}
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Actions */}
      <div className="flex items-center gap-2 pr-4">
        {/* View toggle */}
        <div
          className="flex items-center overflow-hidden rounded-lg"
          style={{ background: '#0d0d18', border: '1px solid #1e1e2e' }}
        >
          {(['graph', 'timeline'] as const).map((v) => (
            <button
              key={v}
              onClick={() => onViewChange(v)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-semibold transition-colors"
              style={{
                color: view === v ? '#00d4ff' : '#3f3f5a',
                background: view === v ? 'rgba(0,212,255,0.1)' : 'transparent',
              }}
            >
              {v === 'graph' ? <Network size={10} /> : <List size={10} />}
              {v === 'graph' ? 'Graph' : 'Timeline'}
            </button>
          ))}
        </div>

        <button
          onClick={handleExport}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium transition-all hover:text-ork-text"
          style={{ background: 'transparent', border: '1px solid #1e1e2e', color: '#52525b' }}
        >
          <Download size={11} />
          Export
        </button>

        <button
          onClick={onRerun}
          disabled={rerunning}
          className="flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-[11px] font-bold transition-all"
          style={{
            background: 'rgba(0,212,255,0.12)',
            border: '1px solid rgba(0,212,255,0.3)',
            color: '#00d4ff',
            opacity: rerunning ? 0.6 : 1,
          }}
        >
          <Play size={11} fill="currentColor" />
          {rerunning ? 'RUNNING…' : 'RE-RUN'}
        </button>
      </div>
    </div>
  );
}
