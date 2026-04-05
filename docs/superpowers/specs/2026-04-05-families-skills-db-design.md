# Families & Skills — DB-backed Architecture

**Date**: 2026-04-05
**Status**: Approved
**Scope**: Backend models, seed mechanism, CRUD API, frontend admin, agent validation

---

## Context

Families and skills are currently defined in JSON seed files (`app/config/families.seed.json`, `app/config/skills.seed.json`) and loaded in memory at startup. Agents reference them via a plain string `family` and a JSONB `skills` list. There is no database persistence, no CRUD, and no referential integrity.

This design promotes families and skills to first-class DB entities with full relational integrity, CRUD administration, and a clean bootstrap-from-JSON mechanism.

## Architecture Rule

- `families.seed.json` and `skills.seed.json` are bootstrap files only.
- They are loaded into the database at application startup (idempotent upsert).
- After that, the database is the sole runtime source of truth.
- Normal application operation never reads the JSON files directly.
- Families and skills are fully administrable via API after init.

---

## 1. Data Model

### 1.1 FamilyDefinition (new table)

| Column | Type | Constraint |
|--------|------|------------|
| family_id | `String(50)` | PK |
| label | `String(255)` | NOT NULL |
| description | `Text` | nullable |
| created_at | `DateTime` | auto |
| updated_at | `DateTime` | auto |

### 1.2 SkillDefinition (new table)

| Column | Type | Constraint |
|--------|------|------------|
| skill_id | `String(100)` | PK |
| label | `String(255)` | NOT NULL |
| category | `String(100)` | NOT NULL |
| description | `Text` | nullable |
| behavior_templates | `JSONB` | default `[]` |
| output_guidelines | `JSONB` | default `[]` |
| created_at | `DateTime` | auto |
| updated_at | `DateTime` | auto |

### 1.3 SkillFamily (join table: skill <-> family)

| Column | Type | Constraint |
|--------|------|------------|
| skill_id | `String(100)` | FK -> SkillDefinition.skill_id, PK composite |
| family_id | `String(50)` | FK -> FamilyDefinition.family_id, PK composite |

ON DELETE CASCADE from both sides (if a skill or family is deleted, the join row is removed).

### 1.4 AgentSkill (join table: agent <-> skill, replaces JSONB `skills`)

| Column | Type | Constraint |
|--------|------|------------|
| agent_id | `String(100)` | FK -> AgentDefinition.id, PK composite |
| skill_id | `String(100)` | FK -> SkillDefinition.skill_id, PK composite |

ON DELETE CASCADE from agent side. ON DELETE RESTRICT from skill side (cannot delete a skill still used by agents).

### 1.5 AgentDefinition modifications

- **Remove**: `skills` column (JSONB)
- **Replace**: `family` (String) -> `family_id` (String(50), FK -> FamilyDefinition.family_id, NOT NULL)
- **Keep**: `skills_content` (Text) — auto-regenerated from resolved skills via AgentSkill join
- **Add ORM relationships**: `family` -> FamilyDefinition, `agent_skills` -> AgentSkill -> SkillDefinition

### 1.6 Data Migration

The Alembic migration must:
1. Create FamilyDefinition, SkillDefinition, SkillFamily, AgentSkill tables
2. Run the seed (insert families and skills from JSON)
3. For each existing agent: insert into AgentSkill from the JSONB `skills` list
4. Rename `family` column to `family_id` (data stays the same — already matches family_id values)
5. Add FK constraint on `family_id`
6. Drop `skills` column

---

## 2. Seed / Bootstrap

### Mechanism

Runs automatically at application startup in the FastAPI `lifespan` context manager, after DB is available.

### Process

1. Open a DB session
2. Read `families.seed.json` -> for each family:
   - If `family_id` exists in DB -> update label, description
   - Else -> insert
3. Read `skills.seed.json` -> for each skill:
   - If `skill_id` exists in DB -> update label, category, description, behavior_templates, output_guidelines
   - Else -> insert
   - Sync `SkillFamily` entries: delete removed families, insert new ones
4. Commit
5. Log result (X families created/updated, Y skills created/updated)

### Properties

- **Idempotent**: rerun = same result, no duplicates
- **Stable identifiers**: family_id and skill_id are natural PKs from JSON
- **Upsert**: create if absent, update if present
- **Non-destructive**: families/skills added manually in DB after seed are not deleted
- **Order**: families first (skills reference families via SkillFamily)

### Post-seed

- The in-memory skill registry (`skill_registry_service.py`) is replaced by DB-backed `SkillService`
- No JSON file is read at runtime after startup seed

---

## 3. Services

### 3.1 FamilyService (`app/services/family_service.py`)

- `seed_families(db, json_path)` — bootstrap from JSON, upsert
- `list_families(db)` — all families from DB
- `get_family(db, family_id)` — single family + associated skills
- `create_family(db, data)` — create, error if family_id already exists
- `update_family(db, family_id, data)` — update label/description
- `delete_family(db, family_id)` — hard delete with guards:
  - **Refuse** if agents reference this family (AgentDefinition.family_id) -> 409
  - **Refuse** if skills reference this family (SkillFamily) -> 409

### 3.2 SkillService (`app/services/skill_service.py`)

Replaces `skill_registry_service.py`.

- `seed_skills(db, json_path)` — bootstrap from JSON, upsert + sync SkillFamily
- `list_skills(db)` — all skills from DB
- `get_skill(db, skill_id)` — single skill + allowed_families
- `get_skills_for_family(db, family_id)` — skills filtered by family via SkillFamily
- `create_skill(db, data)` — create + insert SkillFamily entries
- `update_skill(db, skill_id, data)` — update fields, sync SkillFamily, check agent compatibility
- `delete_skill(db, skill_id)` — hard delete with guards:
  - **Refuse** if agents use this skill (AgentSkill) -> 409
- `build_skills_content(db, skill_ids)` — same role as before but reads from DB
- `resolve_skills(db, skill_ids)` — validate + resolve from DB

### 3.3 AgentRegistryService (modifications)

- `create_agent`: validate family_id exists in DB, validate each skill_id exists in DB, verify each skill allows the agent's family (via SkillFamily), insert into AgentSkill, generate skills_content
- `update_agent`: if family_id changes -> revalidate skill/family compatibility; if skills change -> sync AgentSkill + regenerate skills_content
- `enrich_agent_skills`: read from DB via AgentSkill join instead of in-memory registry
- Remove all in-memory registry references

---

## 4. API Endpoints

### 4.1 Families — `/api/families`

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/families` | List all families |
| GET | `/api/families/{family_id}` | Family detail + associated skills |
| POST | `/api/families` | Create a family |
| PATCH | `/api/families/{family_id}` | Update label/description |
| DELETE | `/api/families/{family_id}` | Delete (with guards) |

### 4.2 Skills — `/api/skills` (reworked)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/skills` | List all skills |
| GET | `/api/skills/{skill_id}` | Skill detail + allowed_families |
| GET | `/api/skills/by-family/{family_id}` | Skills filtered by family |
| POST | `/api/skills` | Create a skill |
| PATCH | `/api/skills/{skill_id}` | Update a skill |
| DELETE | `/api/skills/{skill_id}` | Delete (with guards) |
| GET | `/api/skills/with-agents` | Skills enriched with agents (existing, adapted) |

### 4.3 Agents — `/api/agents` (adaptations)

- `POST /api/agents`: body accepts `family_id` (string) + `skill_ids` (list) instead of `family` + `skills`
- `PATCH /api/agents/{agent_id}`: same
- `GET /api/agents`: filter param renamed `family_id`
- `GET /api/agents/{agent_id}`: response enriched with `family` (object) and `skills_resolved` (from DB)

### 4.4 Error Codes

| Code | Case |
|------|------|
| 404 | Family/skill/agent not found |
| 409 | Cannot delete — referenced by agents or skills |
| 422 | Skill incompatible with agent's family |
| 422 | family_id or skill_id does not exist |

---

## 5. Pydantic Schemas

### 5.1 Family Schemas (`app/schemas/family.py`)

- **FamilyCreate**: family_id, label, description (optional)
- **FamilyUpdate**: label (optional), description (optional)
- **FamilyOut**: family_id, label, description, created_at, updated_at
- **FamilyDetail**: FamilyOut + skills (list of SkillOut)

### 5.2 Skill Schemas (`app/schemas/skill.py` — reworked)

- **SkillCreate**: skill_id, label, category, description (optional), behavior_templates, output_guidelines, allowed_families (list of family_ids)
- **SkillUpdate**: label, category, description, behavior_templates, output_guidelines, allowed_families — all optional
- **SkillOut**: skill_id, label, category, description, behavior_templates, output_guidelines, allowed_families, created_at, updated_at
- **SkillWithAgents**: SkillOut + agents (list)

### 5.3 Agent Schemas (`app/schemas/agent.py` — adapted)

- **AgentCreate**: `family` -> `family_id`, `skills` -> `skill_ids`
- **AgentUpdate**: same rename
- **AgentOut**: includes `family` (FamilyOut object), `skill_ids` (list), `skills_resolved` (list of SkillOut)

---

## 6. Frontend

### 6.1 Agent Form (`agent-form.tsx`)

- **Family**: dropdown fed by `GET /api/families` (label + description tooltip)
- **Skills**: multi-select fed by `GET /api/skills/by-family/{family_id}`, dynamically filtered when family changes
- **Family change**: auto-deselects incompatible skills, shows warning message
- **Validation**: readable errors from API (409, 422)

### 6.2 Families Admin (`/agents/families`)

- List with label, description, agent count, skill count
- Create button -> form (family_id, label, description)
- Edit (label, description)
- Delete with confirmation modal — shows refusal reason on 409

### 6.3 Skills Admin (`/agents/skills` — replaces empty page)

- List with label, category, allowed_families (badges), agent count
- Create button -> form (skill_id, label, category, description, behavior_templates, output_guidelines, allowed_families multi-select)
- Edit modal
- Delete with confirmation modal — shows refusal reason on 409

### 6.4 UX

- Clean empty states on every list
- Modal confirmations before any deletion
- Integrity errors displayed clearly (no raw technical messages)
- Family description visible on hover in agent form

---

## 7. Business Rules

### 7.1 Agent Validation

On agent create and update:
1. `family_id` must exist in FamilyDefinition
2. Each `skill_id` must exist in SkillDefinition
3. Each selected skill must have a SkillFamily entry with the agent's family_id
4. If family changes, incompatible skills are reported (422 error, no silent correction)

### 7.2 Deletion Strategy: Hard Delete

Consistent with the existing repo (agent delete = hard delete, no soft delete pattern). No `deleted_at` column.

**Guards:**

| Entity | Block condition | Response |
|--------|----------------|----------|
| Family | Referenced by >= 1 agent (AgentDefinition.family_id) | 409 + list agents |
| Family | Referenced by >= 1 skill (SkillFamily) | 409 + list skills |
| Skill | Used by >= 1 agent (AgentSkill) | 409 + list agents |

### 7.3 Updating allowed_families on a Skill

When modifying a skill's allowed_families:
- If a family is removed -> check if agents with that family use this skill
- If yes -> 409 with explicit message ("skill X is used by agent Y which belongs to family Z that you are removing")
- Caller must first remove the skill from concerned agents before modifying allowed_families

### 7.4 skills_content Cascade

When a skill is modified (label, description, behavior_templates, output_guidelines):
- Agents using this skill have their `skills_content` regenerated automatically

---

## 8. Points of Attention

1. **Migration order matters**: create FamilyDefinition + SkillDefinition first, seed data, then migrate AgentDefinition columns
2. **Existing agents**: must have valid family_id and skill_ids matching seed data, or migration fails — add validation step
3. **In-memory registry removal**: `skill_registry_service.py` must be fully replaced, not left as dead code
4. **Startup performance**: seed upsert should be fast (< 100ms for ~8 families + ~15 skills), no concern
5. **Frontend API contract change**: `family` -> `family_id`, `skills` -> `skill_ids` is a breaking change — frontend must be updated simultaneously
6. **skills_content regeneration on skill update**: could touch many agents — acceptable at current scale, but worth noting for future
