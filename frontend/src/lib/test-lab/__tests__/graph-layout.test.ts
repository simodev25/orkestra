/**
 * Tests unitaires pour graph-layout.ts — computePlaybackState()
 */
import { describe, it, expect } from 'vitest';
import { computePlaybackState, TOOL_TO_PHASE, buildGraph, calcInitialViewport } from '../graph-layout';
import type { TestRunEvent } from '../types';

const START_TS = new Date('2024-01-01T00:00:00.000Z').getTime();

function makeEvent(
  event_type: string,
  deltaMs: number,
  overrides: Partial<TestRunEvent> = {}
): TestRunEvent {
  return {
    id: `evt_${Math.random().toString(36).slice(2)}`,
    run_id: 'run_test',
    event_type,
    phase: null,
    message: null,
    timestamp: new Date(START_TS + deltaMs).toISOString(),
    duration_ms: null,
    details: null,
    ...overrides,
  };
}

describe('computePlaybackState', () => {
  it('initializes all phases as pending', () => {
    const { phaseStatuses } = computePlaybackState([], START_TS, 0);
    expect(phaseStatuses['orchestrator']).toBe('pending');
    expect(phaseStatuses['preparation']).toBe('pending');
    expect(phaseStatuses['runtime']).toBe('pending');
  });

  it('ignores events after cutoff', () => {
    const events: TestRunEvent[] = [
      makeEvent('run_created', 2000),  // after cutoff of 1000ms
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 1000);
    expect(phaseStatuses['orchestrator']).toBe('pending');
  });

  it('sets orchestrator to running on run_created event', () => {
    const events: TestRunEvent[] = [
      makeEvent('run_created', 100),
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 5000);
    expect(phaseStatuses['orchestrator']).toBe('running');
  });

  it('sets orchestrator to running on orchestrator_started event', () => {
    const events: TestRunEvent[] = [
      makeEvent('orchestrator_started', 100),
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 5000);
    expect(phaseStatuses['orchestrator']).toBe('running');
  });

  it('sets orchestrator to completed on run_completed', () => {
    const events: TestRunEvent[] = [
      makeEvent('run_created', 100),
      makeEvent('run_completed', 500),
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 5000);
    expect(phaseStatuses['orchestrator']).toBe('completed');
  });

  it('sets phase to running on phase_started with mapped phase', () => {
    const events: TestRunEvent[] = [
      makeEvent('phase_started', 200, { phase: 'preparation' }),
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 5000);
    expect(phaseStatuses['preparation']).toBe('running');
  });

  it('sets phase to completed on phase_completed', () => {
    const events: TestRunEvent[] = [
      makeEvent('phase_started', 100, { phase: 'preparation' }),
      makeEvent('phase_completed', 300, { phase: 'preparation', message: 'done' }),
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 5000);
    expect(phaseStatuses['preparation']).toBe('completed');
  });

  it('sets phase to failed on phase_completed with error in message', () => {
    const events: TestRunEvent[] = [
      makeEvent('phase_started', 100, { phase: 'runtime' }),
      makeEvent('phase_completed', 300, { phase: 'runtime', message: 'runtime error occurred' }),
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 5000);
    expect(phaseStatuses['runtime']).toBe('failed');
  });

  it('maps verdict phase events to report node via PHASE_MAP_PB', () => {
    const events: TestRunEvent[] = [
      makeEvent('report_phase_started', 100, { phase: 'verdict' }),
    ];
    const { phaseStatuses } = computePlaybackState(events, START_TS, 5000);
    expect(phaseStatuses['report']).toBe('running');
  });

  it('activeEdgeTargets is empty when no tool call events', () => {
    const { activeEdgeTargets } = computePlaybackState([], START_TS, 5000);
    expect(activeEdgeTargets.size).toBe(0);
  });

  it('adds target to activeEdgeTargets when tool called but phase still pending', () => {
    const events: TestRunEvent[] = [
      makeEvent('orchestrator_tool_call', 100, {
        phase: 'orchestrator',
        details: { tool_name: 'execute_target_agent' },
      }),
    ];
    const { activeEdgeTargets } = computePlaybackState(events, START_TS, 5000);
    expect(activeEdgeTargets.has('runtime')).toBe(true);
  });

  it('removes target from activeEdgeTargets when phase is running', () => {
    const events: TestRunEvent[] = [
      makeEvent('orchestrator_tool_call', 100, {
        phase: 'orchestrator',
        details: { tool_name: 'execute_target_agent' },
      }),
      makeEvent('phase_started', 200, { phase: 'runtime' }),
    ];
    const { activeEdgeTargets } = computePlaybackState(events, START_TS, 5000);
    expect(activeEdgeTargets.has('runtime')).toBe(false);
  });

  it('handles empty events list gracefully', () => {
    const { phaseStatuses, activeEdgeTargets } = computePlaybackState([], START_TS, 5000);
    expect(Object.keys(phaseStatuses).length).toBeGreaterThan(0);
    expect(activeEdgeTargets.size).toBe(0);
  });
});

describe('TOOL_TO_PHASE', () => {
  it('maps execute_target_agent to runtime', () => {
    expect(TOOL_TO_PHASE['execute_target_agent']).toBe('runtime');
  });

  it('maps prepare_test_scenario to preparation', () => {
    expect(TOOL_TO_PHASE['prepare_test_scenario']).toBe('preparation');
  });

  it('maps run_assertion_evaluation to assertions', () => {
    expect(TOOL_TO_PHASE['run_assertion_evaluation']).toBe('assertions');
  });

  it('maps run_diagnostic_analysis to diagnostics', () => {
    expect(TOOL_TO_PHASE['run_diagnostic_analysis']).toBe('diagnostics');
  });

  it('maps compute_final_verdict to report', () => {
    expect(TOOL_TO_PHASE['compute_final_verdict']).toBe('report');
  });
});

// ── buildGraph() helpers ───────────────────────────────────────────────────────

function makeRun(overrides: Partial<any> = {}): any {
  return {
    id: 'trun_test',
    scenario_id: 'scn_test',
    agent_id: 'identity_resolution_agent',
    status: 'completed',
    verdict: 'passed',
    score: 100,
    duration_ms: 1200,
    final_output: null,
    iteration_count: 2,
    error_message: null,
    created_at: '2026-04-13T10:00:00Z',
    updated_at: '2026-04-13T10:00:01Z',
    ...overrides,
  };
}

function makeEv(
  event_type: string,
  phase: string,
  timestamp = '2026-04-13T10:00:00.000Z',
  details: Record<string, unknown> = {},
): any {
  return { id: `ev_${event_type}`, run_id: 'trun_test', event_type, phase, message: null, details, timestamp };
}

describe('buildGraph()', () => {
  it('always includes orchestrator node', () => {
    const { nodes } = buildGraph([], makeRun(), []);
    expect(nodes.some((n: any) => n.id === 'orchestrator')).toBe(true);
  });

  it('nodes get numeric positions from dagre', () => {
    const events = [makeEv('orchestrator_started', 'orchestrator'), makeEv('phase_started', 'preparation')];
    const { nodes } = buildGraph(events, makeRun(), []);
    const orch = nodes.find((n: any) => n.id === 'orchestrator')!;
    expect(typeof orch.position.x).toBe('number');
    expect(typeof orch.position.y).toBe('number');
  });

  it('creates edge from tool_call event to target phase', () => {
    const events = [
      makeEv('orchestrator_tool_call', 'orchestrator', '2026-04-13T10:00:00Z', { tool_name: 'prepare_test_scenario' }),
      makeEv('phase_started', 'preparation'),
    ];
    const { edges } = buildGraph(events, makeRun(), []);
    expect(edges.some((e: any) => e.source === 'orchestrator' && e.target === 'preparation')).toBe(true);
  });

  it('does not duplicate edges for repeated tool calls', () => {
    const events = [
      makeEv('orchestrator_tool_call', 'orchestrator', '2026-04-13T10:00:00Z', { tool_name: 'execute_target_agent' }),
      makeEv('orchestrator_tool_call', 'orchestrator', '2026-04-13T10:00:01Z', { tool_name: 'execute_target_agent' }),
      makeEv('phase_started', 'runtime'),
    ];
    const { edges } = buildGraph(events, makeRun(), []);
    const runtimeEdges = edges.filter((e: any) => e.target === 'runtime');
    expect(runtimeEdges.length).toBe(1);
  });

  it('falls back to sequential edges when no tool call events', () => {
    const events = [makeEv('orchestrator_started', 'orchestrator'), makeEv('phase_started', 'preparation')];
    const { edges } = buildGraph(events, makeRun(), []);
    expect(edges.length).toBeGreaterThan(0);
  });

  it('runtime node uses run.agent_id as subLabel', () => {
    const events = [makeEv('phase_started', 'runtime')];
    const { nodes } = buildGraph(events, makeRun({ agent_id: 'chat_agent' }), []);
    const runtime = nodes.find((n: any) => n.id === 'runtime');
    expect(runtime?.data.subLabel).toBe('chat_agent');
  });

  it('report node includes verdict and score', () => {
    const events = [makeEv('report_phase_started', 'report')];
    const { nodes } = buildGraph(events, makeRun({ verdict: 'passed', score: 95 }), []);
    const report = nodes.find((n: any) => n.id === 'report');
    expect(report?.data.verdict).toBe('passed');
    expect(report?.data.score).toBe(95);
  });

  it('verdict phase maps to report node (no separate verdict node)', () => {
    const events = [makeEv('phase_started', 'verdict')];
    const { nodes } = buildGraph(events, makeRun(), []);
    expect(nodes.find((n: any) => n.id === 'verdict')).toBeUndefined();
  });
});

describe('calcInitialViewport()', () => {
  it('returns default when nodes array is empty', () => {
    const vp = calcInitialViewport([], 800, 600);
    expect(vp).toEqual({ x: 0, y: 0, zoom: 1 });
  });

  it('zoom does not exceed 1.5', () => {
    const nodes = [{ id: 'n', position: { x: 0, y: 0 }, width: 10, height: 10 }] as any;
    const vp = calcInitialViewport(nodes, 2000, 2000);
    expect(vp.zoom).toBeLessThanOrEqual(1.5);
  });

  it('zoom is greater than 0', () => {
    const nodes = [
      { id: 'a', position: { x: 0, y: 0 }, width: 210, height: 108 },
      { id: 'b', position: { x: 340, y: 0 }, width: 210, height: 108 },
    ] as any;
    const vp = calcInitialViewport(nodes, 1280, 720);
    expect(vp.zoom).toBeGreaterThan(0);
  });

  it('centers the graph — x and y are finite numbers', () => {
    const nodes = [{ id: 'n', position: { x: 100, y: 50 }, width: 210, height: 108 }] as any;
    const vp = calcInitialViewport(nodes, 1280, 720);
    expect(Number.isFinite(vp.x)).toBe(true);
    expect(Number.isFinite(vp.y)).toBe(true);
  });
});
