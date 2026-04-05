# Families, Skills & Prompt Architecture

## 1. What is a Family

A **FamilyDefinition** groups agents that share the same operational context and compliance rules.

**Structuration** — Every agent must belong to exactly one family (via `family_id`). A family has:
- `id` (slug, e.g. `analysis`), `label`, `description`, `version`, `status`, `owner`
- `default_system_rules` — rules injected into every agent's prompt as Layer 1
- `default_forbidden_effects` — actions forbidden by default (merged with agent-level rules)
- `default_output_expectations` — guidelines injected as Layer 5 of the prompt

**Filtering** — The list endpoint hides archived families by default (`status != 'archived'`). Pass `?include_archived=true` to see all.

**Prompt contribution** — Layers 1 and 5 come entirely from the family.

---

## 2. What is a Skill

A **SkillDefinition** is a reusable capability block that agents can declare.

**Capability** — A skill carries:
- `skill_id`, `label`, `category`, `description`, `version`, `status`, `owner`
- `behavior_templates` — behavioral directives injected as Layer 2
- `output_guidelines` — output quality rules injected alongside behavior templates

**Constraint by `allowed_families`** — A skill can only be assigned to an agent whose family appears in `allowed_families`. The join table `skill_families` enforces this at creation and update time. Agent validation rejects skills that are not in the family's allowed set.

**Prompt contribution** — Every active skill assigned to an agent adds a `### {label}` block in Layer 2 (SKILL RULES).

---

## 3. Versioning

Each family and skill has three version-related fields:

| Field | Purpose |
|---|---|
| `version` | Semantic version of this specific record (e.g. `1.2.0`) |
| `status` | Lifecycle state: `active`, `deprecated`, or `archived` |
| `owner` | Team or person responsible for the definition |

Seed files (JSON) also carry a `schema_version` and optionally a `seed_version` at the root level. These are bootstrap-only metadata and have no runtime meaning.

---

## 4. Bootstrap vs Runtime

**Bootstrap (JSON seed files)** — `families.seed.json` and `skills.seed.json` are applied once at startup (or via explicit seed commands). They are the canonical source of *initial* definitions. The seed service is idempotent: it upserts but never overwrites manual changes made at runtime.

**Runtime (DB as source of truth)** — All reads during agent execution, validation, and prompt building query the database. The JSON files are never consulted at runtime. Mutations (create, update, archive) go directly to the DB.

---

## 5. Prompt Composition

`build_agent_prompt(db, agent, runtime_context)` assembles a system prompt from 7 ordered layers:

| Order | Section header | Source |
|---|---|---|
| 1 | `FAMILY RULES` | `family.default_system_rules` |
| 2 | `SKILL RULES` | `skill.behavior_templates` + `skill.output_guidelines` for each skill |
| 3 | `SOUL` | `agent.soul_content` — **skipped if empty** |
| 4 | `AGENT MISSION` | `agent.name`, `purpose`, `description`, `prompt_content` |
| 5 | `OUTPUT EXPECTATIONS` | `family.default_output_expectations` |
| 6 | `CONTRACTS` | `agent.input_contract_ref`, `agent.output_contract_ref` — **skipped if both empty** |
| 7 | `RUNTIME CONTEXT` | criticality, merged forbidden effects, allowed tools, limitations, runtime_context dict |

Forbidden effects in Layer 7 are the **union** of `family.default_forbidden_effects` and `agent.forbidden_effects`.

---

## 6. CRUD / Integrity / Archive

### Create
- Family: `POST /api/families` — id must be unique, slug format.
- Skill: `POST /api/skills` — all `allowed_families` must exist in the DB.
- Agent: `POST /api/agents` — family must exist **and be active**; all skill_ids must exist, be active, and be in the family's allowed set.

### Update
- `PATCH /api/families/{id}` — partial update, all fields optional.
- `PATCH /api/skills/{id}` — removing a family from `allowed_families` is blocked if any agent in that family still uses the skill.
- `PATCH /api/agents/{id}` — skill compatibility is re-validated on every update.

### Archive
- `PATCH /api/families/{id}/archive` — always archives regardless of references.
- `PATCH /api/skills/{id}/archive` — always archives regardless of references.
- Once archived, a family or skill can no longer be assigned to new agents.

### Delete
- `DELETE /api/families/{id}` — archives if referenced by agents or skills; hard-deletes otherwise.
- `DELETE /api/skills/{id}` — archives if referenced by agents; hard-deletes otherwise.
- `DELETE /api/agents/{id}` — only allowed when agent status is not `active`.

### Guard rails summary
| Situation | Behaviour |
|---|---|
| Agent references archived family | 400 Validation error at creation |
| Agent references archived skill | 400 Validation error at creation |
| Delete family with agents/skills | 200 — family archived automatically |
| Delete skill with agents | 200 — skill archived automatically |
| Remove family from skill while agents use it | 409 Conflict |
