// frontend/src/lib/test-lab/graph-types.ts
import type { Node, Edge } from '@xyflow/react';
import type { TestRunEvent, TestRunDiagnostic } from './types';

export type PhaseKind =
  | 'orchestrator'
  | 'preparation'
  | 'runtime'
  | 'assertions'
  | 'diagnostics'
  | 'report';

export interface AgentNodeData extends Record<string, unknown> {
  kind: PhaseKind;
  agentId: string;
  /** Display title, e.g. "Identity Resolution" */
  label: string;
  /** Sub-title, e.g. "identity_resolution_agent" */
  subLabel: string;
  /** Key in LUCIDE_ICONS map */
  iconName: string;
  /** Hex accent colour */
  color: string;
  /** "completed" | "failed" | "warning" | "running" */
  status: string;
  durationMs: number | null;
  events: TestRunEvent[];
  diagnostics: TestRunDiagnostic[];
  /** Parsed final_output JSON (runtime phase only) */
  output: unknown;
  /** Zero-based index used for stagger animation delay */
  index: number;
}

export interface EdgeData extends Record<string, unknown> {
  /** Orchestrator tool name shown as chip, e.g. "execute_target_agent" */
  toolName: string | null;
  /** Hex accent colour matching source node */
  color: string;
}

export type RunNode = Node<AgentNodeData>;
export type RunEdge = Edge<EdgeData>;
