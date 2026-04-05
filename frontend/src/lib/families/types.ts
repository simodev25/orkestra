export interface FamilyDefinition {
  id: string;
  label: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface FamilyDetail extends FamilyDefinition {
  skills: SkillBrief[];
  agent_count: number;
}

export interface SkillBrief {
  skill_id: string;
  label: string;
  category: string;
}

export interface SkillDefinition {
  skill_id: string;
  label: string;
  category: string;
  description: string | null;
  behavior_templates: string[];
  output_guidelines: string[];
  allowed_families: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface SkillWithAgents extends SkillDefinition {
  agents: { agent_id: string; label: string }[];
}

export interface FamilyCreatePayload {
  id: string;
  label: string;
  description?: string;
}

export interface FamilyUpdatePayload {
  label?: string;
  description?: string;
}

export interface SkillCreatePayload {
  skill_id: string;
  label: string;
  category: string;
  description?: string;
  behavior_templates: string[];
  output_guidelines: string[];
  allowed_families: string[];
}

export interface SkillUpdatePayload {
  label?: string;
  category?: string;
  description?: string;
  behavior_templates?: string[];
  output_guidelines?: string[];
  allowed_families?: string[];
}
