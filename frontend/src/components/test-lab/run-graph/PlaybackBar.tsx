"use client";

import { useMemo } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import type { TestRunEvent } from '@/lib/test-lab/types';

interface PlaybackBarProps {
  totalMs: number;
  currentMs: number;
  startTs: number;
  events: TestRunEvent[];
  isPlaying: boolean;
  speed: number;
  onSeek: (ms: number) => void;
  onTogglePlay: () => void;
  onReset: () => void;
  onSpeedChange: (s: number) => void;
}

function fmt(ms: number): string {
  const s = ms / 1000;
  if (s < 10) return `${s.toFixed(2)}s`;
  return `${s.toFixed(1)}s`;
}

const MARKER_TYPES = new Set([
  'phase_started', 'assertion_phase_started', 'diagnostic_phase_started',
  'report_phase_started', 'phase_completed', 'run_completed',
  'orchestrator_tool_call',
]);

export function PlaybackBar({
  totalMs, currentMs, startTs, events,
  isPlaying, speed, onSeek, onTogglePlay, onReset, onSpeedChange,
}: PlaybackBarProps) {
  const progress = totalMs > 0 ? Math.min(currentMs / totalMs, 1) : 0;

  // Build unique event markers (phase key = event_type + phase)
  const markers = useMemo(() => {
    const seen = new Set<string>();
    const out: { pos: number; isEnd: boolean }[] = [];
    for (const ev of events) {
      if (!MARKER_TYPES.has(ev.event_type)) continue;
      const key = ev.event_type + (ev.phase ?? '');
      if (seen.has(key)) continue;
      seen.add(key);
      const pos = (new Date(ev.timestamp).getTime() - startTs) / totalMs;
      const isEnd = ev.event_type === 'phase_completed' || ev.event_type === 'run_completed';
      out.push({ pos, isEnd });
    }
    return out;
  }, [events, startTs, totalMs]);

  const handleTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    onSeek(ratio * totalMs);
  };

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 flex-shrink-0"
      style={{
        background: 'rgba(7,7,15,0.97)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Reset */}
      <button
        onClick={onReset}
        title="Rejouer depuis le début"
        className="p-1.5 rounded-lg transition-colors"
        style={{ color: '#3f3f5a' }}
        onMouseEnter={e => (e.currentTarget.style.color = '#a78bfa')}
        onMouseLeave={e => (e.currentTarget.style.color = '#3f3f5a')}
      >
        <RotateCcw size={12} />
      </button>

      {/* Play / Pause */}
      <button
        onClick={onTogglePlay}
        className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0"
        style={{
          background: isPlaying ? 'rgba(167,139,250,0.15)' : 'rgba(167,139,250,0.22)',
          color: '#a78bfa',
          border: '1px solid rgba(167,139,250,0.25)',
        }}
      >
        {isPlaying ? <Pause size={12} /> : <Play size={12} />}
      </button>

      {/* Track */}
      <div className="flex-1 flex items-center h-6 cursor-pointer" onClick={handleTrackClick}>
        <div className="relative w-full h-[3px] rounded-full" style={{ background: 'rgba(255,255,255,0.07)' }}>
          {/* Fill */}
          <div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{ width: `${progress * 100}%`, background: 'linear-gradient(90deg, #6d28d9, #a78bfa)' }}
          />
          {/* Event markers */}
          {markers.map((m, i) => (
            <div
              key={i}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full pointer-events-none"
              style={{
                left: `${m.pos * 100}%`,
                width: 4, height: 4,
                background: m.isEnd ? '#10b981' : '#52525b',
                opacity: 0.8,
                zIndex: 1,
              }}
            />
          ))}
          {/* Thumb */}
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 rounded-full pointer-events-none"
            style={{
              left: `${progress * 100}%`,
              width: 12, height: 12,
              background: '#a78bfa',
              boxShadow: '0 0 8px rgba(167,139,250,0.7)',
              zIndex: 2,
            }}
          />
        </div>
      </div>

      {/* Time */}
      <span className="text-[10px] font-mono flex-shrink-0" style={{ color: '#52525b', minWidth: 88 }}>
        {fmt(currentMs)}<span style={{ color: '#2a2a3e' }}> / </span>{fmt(totalMs)}
      </span>

      {/* Speed */}
      <div className="flex items-center gap-1 flex-shrink-0">
        {([1, 2, 4] as const).map(s => (
          <button
            key={s}
            onClick={() => onSpeedChange(s)}
            className="text-[9px] font-bold px-1.5 py-0.5 rounded transition-all"
            style={{
              background: speed === s ? 'rgba(167,139,250,0.2)' : 'transparent',
              color: speed === s ? '#a78bfa' : '#2e2e4a',
              border: '1px solid',
              borderColor: speed === s ? 'rgba(167,139,250,0.35)' : 'transparent',
            }}
          >
            {s}×
          </button>
        ))}
      </div>
    </div>
  );
}
