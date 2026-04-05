import type {
  FamilyCreatePayload,
  FamilyDefinition,
  FamilyDetail,
  FamilyUpdatePayload,
  SkillCreatePayload,
  SkillDefinition,
  SkillUpdatePayload,
  SkillWithAgents,
} from "./types";

async function request<R>(url: string, opts?: RequestInit): Promise<R> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
  return res.json();
}

// Families
export async function listFamilies(): Promise<FamilyDefinition[]> {
  return request<FamilyDefinition[]>("/api/families");
}

export async function getFamily(familyId: string): Promise<FamilyDetail> {
  return request<FamilyDetail>(`/api/families/${familyId}`);
}

export async function createFamily(payload: FamilyCreatePayload): Promise<FamilyDefinition> {
  return request<FamilyDefinition>("/api/families", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateFamily(familyId: string, payload: FamilyUpdatePayload): Promise<FamilyDefinition> {
  return request<FamilyDefinition>(`/api/families/${familyId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function deleteFamily(familyId: string): Promise<void> {
  const res = await fetch(`/api/families/${familyId}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
}

// Skills
export async function listSkills(): Promise<SkillDefinition[]> {
  return request<SkillDefinition[]>("/api/skills");
}

export async function listSkillsByFamily(familyId: string): Promise<SkillDefinition[]> {
  return request<SkillDefinition[]>(`/api/skills/by-family/${familyId}`);
}

export async function listSkillsWithAgents(): Promise<SkillWithAgents[]> {
  return request<SkillWithAgents[]>("/api/skills/with-agents");
}

export async function createSkill(payload: SkillCreatePayload): Promise<SkillDefinition> {
  return request<SkillDefinition>("/api/skills", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateSkill(skillId: string, payload: SkillUpdatePayload): Promise<SkillDefinition> {
  return request<SkillDefinition>(`/api/skills/${skillId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function deleteSkill(skillId: string): Promise<void> {
  const res = await fetch(`/api/skills/${skillId}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || res.statusText);
  }
}
