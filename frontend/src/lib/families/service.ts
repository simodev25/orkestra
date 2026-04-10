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
import { request } from "../api-client";

// Families
export async function listFamilies(includeArchived = false): Promise<FamilyDefinition[]> {
  const qs = includeArchived ? "?include_archived=true" : "";
  const res = await request<{ items: FamilyDefinition[] } | FamilyDefinition[]>(`/api/families${qs}`);
  return Array.isArray(res) ? res : res.items;
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

export async function archiveFamily(familyId: string): Promise<FamilyDefinition> {
  return request<FamilyDefinition>(`/api/families/${familyId}/archive`, { method: "PATCH" });
}

// Skills
export async function listSkills(includeArchived = false): Promise<SkillDefinition[]> {
  const qs = includeArchived ? "?include_archived=true" : "";
  const res = await request<{ items: SkillDefinition[] } | SkillDefinition[]>(`/api/skills${qs}`);
  return Array.isArray(res) ? res : res.items;
}

export async function listSkillsByFamily(familyId: string): Promise<SkillDefinition[]> {
  return request<SkillDefinition[]>(`/api/skills/by-family/${familyId}`);
}

export async function listSkillsWithAgents(includeArchived = false): Promise<SkillWithAgents[]> {
  const qs = includeArchived ? "?include_archived=true" : "";
  return request<SkillWithAgents[]>(`/api/skills/with-agents${qs}`);
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

export async function archiveSkill(skillId: string): Promise<SkillDefinition> {
  return request<SkillDefinition>(`/api/skills/${skillId}/archive`, { method: "PATCH" });
}

export async function getFamilyHistory(familyId: string): Promise<any[]> {
  return request<any[]>(`/api/families/${familyId}/history`);
}

export async function getSkillHistory(skillId: string): Promise<any[]> {
  return request<any[]>(`/api/skills/${skillId}/history`);
}

export async function restoreFamily(familyId: string, historyId: string): Promise<FamilyDefinition> {
  return request<FamilyDefinition>(`/api/families/${familyId}/restore/${historyId}`, { method: "POST" });
}

export async function restoreSkill(skillId: string, historyId: string): Promise<SkillDefinition> {
  return request<SkillDefinition>(`/api/skills/${skillId}/restore/${historyId}`, { method: "POST" });
}
