/**
 * Tests unitaires pour graph-layout.ts — computePlaybackState()
 */
import { describe, it, expect } from 'vitest';
import { computePlaybackState, TOOL_TO_PHASE } from '../graph-layout';
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
