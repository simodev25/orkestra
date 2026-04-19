import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentPipelinePanel from '../AgentPipelinePanel';
import type { AgentDefinition } from '@/lib/agent-registry/types';

// Mock lucide-react icons to avoid SVG rendering issues in jsdom
vi.mock('lucide-react', () => ({
  GripVertical: () => null,
  X: () => null,
  Plus: () => null,
}));

const mockAgents: AgentDefinition[] = [
  {
    id: 'weather_agent',
    name: 'Weather Agent',
    family_id: 'analysis',
    family: null,
    purpose: 'Check weather',
    description: null,
    skill_ids: null,
    skills_resolved: null,
    selection_hints: null,
    allowed_mcps: null,
    forbidden_effects: null,
    input_contract_ref: null,
    output_contract_ref: null,
    criticality: 'low',
    cost_profile: 'low',
    limitations: null,
    prompt_ref: null,
    prompt_content: null,
    skills_ref: null,
    skills_content: null,
    soul_content: null,
    llm_provider: null,
    llm_model: null,
    allow_code_execution: false,
    allowed_builtin_tools: null,
    version: '1.0.0',
    status: 'active',
    owner: null,
    last_test_status: 'passed',
    last_validated_at: null,
    usage_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'budget_agent',
    name: 'Budget Agent',
    family_id: 'analysis',
    family: null,
    purpose: 'Check budget',
    description: null,
    skill_ids: null,
    skills_resolved: null,
    selection_hints: null,
    allowed_mcps: null,
    forbidden_effects: null,
    input_contract_ref: null,
    output_contract_ref: null,
    criticality: 'medium',
    cost_profile: 'medium',
    limitations: null,
    prompt_ref: null,
    prompt_content: null,
    skills_ref: null,
    skills_content: null,
    soul_content: null,
    llm_provider: null,
    llm_model: null,
    allow_code_execution: false,
    allowed_builtin_tools: null,
    version: '1.0.0',
    status: 'active',
    owner: null,
    last_test_status: 'passed',
    last_validated_at: null,
    usage_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'hotel_agent',
    name: 'Hotel Agent',
    family_id: 'analysis',
    family: null,
    purpose: 'Find hotels',
    description: null,
    skill_ids: null,
    skills_resolved: null,
    selection_hints: null,
    allowed_mcps: null,
    forbidden_effects: null,
    input_contract_ref: null,
    output_contract_ref: null,
    criticality: 'low',
    cost_profile: 'low',
    limitations: null,
    prompt_ref: null,
    prompt_content: null,
    skills_ref: null,
    skills_content: null,
    soul_content: null,
    llm_provider: null,
    llm_model: null,
    allow_code_execution: false,
    allowed_builtin_tools: null,
    version: '1.0.0',
    status: 'active',
    owner: null,
    last_test_status: 'passed',
    last_validated_at: null,
    usage_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const defaultProps = {
  mode: 'manual' as const,
  onModeChange: vi.fn(),
  selectedIds: [],
  onSelectedIdsChange: vi.fn(),
  useCase: '',
  onUseCaseChange: vi.fn(),
  allAgents: mockAgents,
};

describe('AgentPipelinePanel', () => {
  it('renders mode toggle buttons', () => {
    render(<AgentPipelinePanel {...defaultProps} />);
    expect(screen.getByText('Manuel')).toBeInTheDocument();
    expect(screen.getByText('Auto (LLM choisit)')).toBeInTheDocument();
  });

  it('manual mode is active by default style', () => {
    render(<AgentPipelinePanel {...defaultProps} mode="manual" />);
    const manuelButton = screen.getByText('Manuel');
    expect(manuelButton.className).toContain('bg-ork-cyan');
  });

  it('clicking Auto button calls onModeChange with "auto"', () => {
    const onModeChange = vi.fn();
    render(<AgentPipelinePanel {...defaultProps} onModeChange={onModeChange} />);
    fireEvent.click(screen.getByText('Auto (LLM choisit)'));
    expect(onModeChange).toHaveBeenCalledWith('auto');
  });

  it('clicking Manuel button calls onModeChange with "manual"', () => {
    const onModeChange = vi.fn();
    render(<AgentPipelinePanel {...defaultProps} mode="auto" onModeChange={onModeChange} />);
    fireEvent.click(screen.getByText('Manuel'));
    expect(onModeChange).toHaveBeenCalledWith('manual');
  });

  it('manual mode shows selected agent ids', () => {
    render(<AgentPipelinePanel {...defaultProps} selectedIds={['weather_agent']} />);
    expect(screen.getByText('weather_agent')).toBeInTheDocument();
  });

  it('manual mode shows order numbers', () => {
    render(
      <AgentPipelinePanel
        {...defaultProps}
        selectedIds={['weather_agent', 'budget_agent']}
      />
    );
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('remove button calls onSelectedIdsChange without the agent', () => {
    const onSelectedIdsChange = vi.fn();
    render(
      <AgentPipelinePanel
        {...defaultProps}
        selectedIds={['weather_agent', 'budget_agent']}
        onSelectedIdsChange={onSelectedIdsChange}
      />
    );
    fireEvent.click(screen.getByLabelText('Remove weather_agent'));
    expect(onSelectedIdsChange).toHaveBeenCalledWith(['budget_agent']);
  });

  it('auto mode shows textarea', () => {
    render(<AgentPipelinePanel {...defaultProps} mode="auto" />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('auto mode textarea has correct placeholder', () => {
    render(<AgentPipelinePanel {...defaultProps} mode="auto" />);
    const textarea = screen.getByRole('textbox');
    expect(textarea).toHaveAttribute('placeholder', expect.stringContaining('Je veux un pipeline'));
  });

  it('auto mode textarea calls onUseCaseChange on input', () => {
    const onUseCaseChange = vi.fn();
    render(
      <AgentPipelinePanel {...defaultProps} mode="auto" onUseCaseChange={onUseCaseChange} />
    );
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'new value' } });
    expect(onUseCaseChange).toHaveBeenCalledWith('new value');
  });

  it('add agent button opens picker', () => {
    render(<AgentPipelinePanel {...defaultProps} selectedIds={[]} />);
    fireEvent.click(screen.getByText('Ajouter un agent…'));
    expect(screen.getByText('weather_agent')).toBeInTheDocument();
    expect(screen.getByText('budget_agent')).toBeInTheDocument();
    expect(screen.getByText('hotel_agent')).toBeInTheDocument();
  });

  it('picker only shows agents not already selected', () => {
    render(<AgentPipelinePanel {...defaultProps} selectedIds={['weather_agent']} />);
    fireEvent.click(screen.getByText('Ajouter un agent…'));
    // weather_agent is selected so shows in the list (the id text element in selected row)
    // but it should NOT appear in the picker dropdown
    // The picker renders agent ids as button text — check available ones appear
    const buttons = screen.getAllByRole('button');
    const pickerButtons = buttons.filter(
      (b) => b.textContent?.includes('budget_agent') || b.textContent?.includes('hotel_agent')
    );
    expect(pickerButtons.length).toBeGreaterThan(0);

    // weather_agent in the picker specifically — check it's not a picker entry button
    // The picker entries are inside the dropdown. We verify no picker button has weather_agent as its main text.
    // The selected list item also shows weather_agent as a span, not a button with that text.
    // So we check that the "Add" dropdown buttons don't include weather_agent
    const pickerEntryWithWeather = buttons.find(
      (b) =>
        b.className.includes('font-mono') &&
        b.textContent?.startsWith('weather_agent')
    );
    expect(pickerEntryWithWeather).toBeUndefined();
  });

  it('clicking agent in picker calls onSelectedIdsChange with that agent added', () => {
    const onSelectedIdsChange = vi.fn();
    render(
      <AgentPipelinePanel
        {...defaultProps}
        selectedIds={['weather_agent']}
        onSelectedIdsChange={onSelectedIdsChange}
      />
    );
    fireEvent.click(screen.getByText('Ajouter un agent…'));
    // Find the picker button for budget_agent
    const allButtons = screen.getAllByRole('button');
    const budgetPickerBtn = allButtons.find(
      (b) => b.textContent?.includes('budget_agent') && b.className.includes('font-mono')
    );
    expect(budgetPickerBtn).toBeDefined();
    fireEvent.click(budgetPickerBtn!);
    expect(onSelectedIdsChange).toHaveBeenCalledWith(['weather_agent', 'budget_agent']);
  });

  it('picker shows empty message when all agents selected', () => {
    render(
      <AgentPipelinePanel
        {...defaultProps}
        selectedIds={['weather_agent', 'budget_agent', 'hotel_agent']}
      />
    );
    fireEvent.click(screen.getByText('Ajouter un agent…'));
    expect(screen.getByText('Tous les agents sont déjà sélectionnés')).toBeInTheDocument();
  });
});
