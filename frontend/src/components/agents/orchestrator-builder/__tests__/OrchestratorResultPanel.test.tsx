import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import OrchestratorResultPanel from '../OrchestratorResultPanel';
import type { GeneratedAgentDraft } from '@/lib/agent-registry/types';

// Mock lucide-react icons to avoid SVG rendering issues in jsdom
vi.mock('lucide-react', () => ({
  RotateCcw: () => null,
  Save: () => null,
}));

const mockDraft: GeneratedAgentDraft = {
  agent_id: 'test_orch',
  name: 'Test Orchestrator',
  family_id: 'orchestration',
  purpose: 'Test purpose',
  description: 'Test description',
  skill_ids: ['sequential_routing', 'context_propagation'],
  selection_hints: {
    routing_keywords: ['orchestrate'],
    workflow_ids: [],
    use_case_hint: 'test',
    requires_grounded_evidence: false,
  },
  allowed_mcps: [],
  forbidden_effects: [],
  input_contract_ref: null,
  output_contract_ref: null,
  criticality: 'medium',
  cost_profile: 'medium',
  limitations: ['Limitation one', 'Limitation two'],
  prompt_content: 'You are a test orchestrator. Route tasks to agents.',
  skills_content: 'sequential_routing: Routes tasks\ncontext_propagation: Passes context',
  owner: null,
  version: '1.0.0',
  status: 'draft',
  suggested_missing_mcps: [],
  mcp_rationale: {},
};

const defaultProps = {
  draft: mockDraft,
  selectedAgentIds: ['weather_agent', 'budget_agent'],
  onModify: vi.fn(),
  onRegenerate: vi.fn(),
  onSave: vi.fn().mockResolvedValue(undefined),
  saving: false,
};

describe('OrchestratorResultPanel', () => {
  it('renders Prompt tab by default', () => {
    render(<OrchestratorResultPanel {...defaultProps} />);
    expect(screen.getByText('Prompt')).toBeInTheDocument();
    expect(screen.getByText('You are a test orchestrator. Route tasks to agents.')).toBeInTheDocument();
  });

  it('prompt tab shows prompt_content in pre element', () => {
    render(<OrchestratorResultPanel {...defaultProps} />);
    const pre = screen.getByText('You are a test orchestrator. Route tasks to agents.').closest('pre');
    expect(pre).toBeInTheDocument();
  });

  it('clicking Skills tab shows skill_ids', () => {
    render(<OrchestratorResultPanel {...defaultProps} />);
    fireEvent.click(screen.getByText('Skills'));
    expect(screen.getByText('sequential_routing')).toBeInTheDocument();
    expect(screen.getByText('context_propagation')).toBeInTheDocument();
  });

  it('skills tab shows limitations', () => {
    render(<OrchestratorResultPanel {...defaultProps} />);
    fireEvent.click(screen.getByText('Skills'));
    expect(screen.getByText('Limitation one')).toBeInTheDocument();
    expect(screen.getByText('Limitation two')).toBeInTheDocument();
  });

  it('clicking Config tab shows JSON', () => {
    render(<OrchestratorResultPanel {...defaultProps} />);
    fireEvent.click(screen.getByText('Config'));
    const pre = document.querySelector('pre');
    expect(pre?.textContent).toContain('test_orch');
  });

  it('config JSON includes selectedAgentIds', () => {
    render(
      <OrchestratorResultPanel
        {...defaultProps}
        selectedAgentIds={['weather_agent', 'budget_agent']}
      />
    );
    fireEvent.click(screen.getByText('Config'));
    const pre = document.querySelector('pre');
    expect(pre?.textContent).toContain('weather_agent');
    expect(pre?.textContent).toContain('budget_agent');
  });

  it('Modifier button calls onModify', () => {
    const onModify = vi.fn();
    render(<OrchestratorResultPanel {...defaultProps} onModify={onModify} />);
    fireEvent.click(screen.getByText('✎ Modifier'));
    expect(onModify).toHaveBeenCalledOnce();
  });

  it('Regénérer button calls onRegenerate', () => {
    const onRegenerate = vi.fn();
    render(<OrchestratorResultPanel {...defaultProps} onRegenerate={onRegenerate} />);
    fireEvent.click(screen.getByText('Regénérer'));
    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it('Sauvegarder button calls onSave', () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<OrchestratorResultPanel {...defaultProps} onSave={onSave} />);
    fireEvent.click(screen.getByText('Sauvegarder'));
    expect(onSave).toHaveBeenCalledOnce();
  });

  it('Sauvegarder button is disabled when saving=true', () => {
    render(<OrchestratorResultPanel {...defaultProps} saving={true} />);
    const button = screen.getByText('Sauvegarde…').closest('button');
    expect(button).toBeDisabled();
  });

  it('shows "Sauvegarde…" text when saving', () => {
    render(<OrchestratorResultPanel {...defaultProps} saving={true} />);
    expect(screen.getByText('Sauvegarde…')).toBeInTheDocument();
  });
});
