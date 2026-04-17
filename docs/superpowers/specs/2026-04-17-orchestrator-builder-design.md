# Orchestrator Builder Page — Design Spec

**Date:** 2026-04-17  
**Status:** Approved

---

## Goal

Add a page `/agents/orchestrators/new` that lets the user generate a new Orchestrator agent from a set of existing agents. The LLM reads the selected agents' descriptions, purpose, skills, and prompt, then proposes a coherent orchestrator prompt + skills. The user reviews and saves.

---

## Layout — Split-screen

The page is split into two fixed columns separated by a vertical divider.

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Agents    Orchestrator Builder                      [BETA]   │
├─────────────────────────────────────────────────────────────────┤
│  Mode: [Manuel ●] [Auto (LLM choisit)]    Tu sélectionnes…      │
├───────────────────────┬─────────────────────────────────────────┤
│  LEFT PANEL (320px)   │  RIGHT PANEL (flex:1)                   │
│                       │                                         │
│  [Mode Manuel]        │  Nom de l'orchestrateur                 │
│  Pipeline — drag list │  ┌─────────────────────────────┐        │
│  ① weather_agent  ✕   │  │ hotel_pipeline_orchestrator │        │
│  ② budget_fit     ✕   │  └─────────────────────────────┘        │
│  ③ hotel_search   ✕   │                                         │
│  + Ajouter…           │  Instructions pour le LLM               │
│                       │  ┌─────────────────────────────┐        │
│  [Mode Auto]          │  │ Contexte, ordre, contraintes│        │
│  Textarea libre:      │  │ …                           │        │
│  "Je veux un pipeline │  └─────────────────────────────┘        │
│   qui gère…"          │                                         │
│                       │  [⚡ Générer l'orchestrateur]           │
│                       ├─────────────────────────────────────────┤
│                       │  [Prompt] [Skills] [Config]  [Modifier] │
│                       │                                         │
│                       │  <generated content>                    │
│                       │                                         │
│                       │              [↺ Regénérer] [✓ Save]     │
└───────────────────────┴─────────────────────────────────────────┘
```

---

## Mode Toggle

A pill toggle in the header bar switches between two modes. The toggle state changes only the **left panel content** — the right panel (config + result) is identical in both modes.

### Mode Manuel
- Left panel shows a numbered, drag-and-drop ordered list of selected agents.
- Each row: drag handle `⠿` + order number chip + agent name + family + ✕ remove.
- At the bottom: "+ Ajouter un agent…" button that opens a modal/dropdown to pick from the agent registry.
- The ordered list is passed to the backend as `agent_ids: string[]` in order.

### Mode Auto
- Left panel shows a single `<textarea>` with placeholder: *"Décris ton pipeline: ex. Je veux un pipeline qui gère la recherche hôtelière. Il doit évaluer la météo, le budget, et trouver les meilleurs hôtels…"*
- Below: a hint line — *"Le LLM lira les descriptions de tous les agents disponibles et sélectionnera ceux qui correspondent."*
- The textarea value is passed to the backend as `use_case_description: string`. `agent_ids` is empty (`[]`) in this mode.
- The backend fetches all agents from the registry and includes their descriptions in the LLM prompt.

---

## Right Panel — Configuration

Always visible, regardless of mode.

| Field | Type | Validation |
|-------|------|-----------|
| Nom de l'orchestrateur | text input | required, min 3 chars, snake_case recommended |
| Instructions pour le LLM | textarea (3 rows) | optional — context, priorities, constraints, agent order rationale |

**Generate button** (`⚡ Générer l'orchestrateur`) — full-width, cyan background. Disabled if:
- Mode Manuel and `agent_ids.length < 2`
- Mode Auto and `use_case_description` is empty
- Name is empty

On click: POST to `/api/agents/generate-orchestrator`, show spinner in button.

---

## Right Panel — Result (after generation)

The result section appears below the config section (which becomes 50% opacity but stays visible for reference).

### Tabs

**Prompt** — the generated system prompt displayed in a monospace code block, read-only but selectable.

**Skills** — list of generated skill objects. Each shows:
- Skill name (cyan)
- Skill description (muted)

**Config** — generated JSON preview of the agent config (id, name, family_id, agent_ids, mode, criticality, cost_profile).

### Actions
- **Modifier** (ghost button) — hides result section, restores config to full opacity. User can change inputs and regenerate.
- **Regénérer** (ghost button) — re-calls the API with same inputs, replaces result in place.
- **Sauvegarder** (primary cyan button) — calls `POST /api/agents/save-generated-draft`, then redirects to `/agents/{id}`.

---

## Backend — API endpoint

### `POST /api/agents/generate-orchestrator`

**Request body:**
```json
{
  "name": "hotel_pipeline_orchestrator",
  "agent_ids": ["weather_agent", "budget_fit_agent", "hotel_search_agent"],
  "use_case_description": "Optional free text (mode auto)",
  "user_instructions": "Optional LLM context textarea content",
  "routing_strategy": "sequential"
}
```

**Behaviour:**
- If `agent_ids` non-empty: fetch those agents from DB in the given order.
- If `agent_ids` empty and `use_case_description` non-empty: fetch **all** agents from DB, include all their descriptions in the LLM prompt so it can choose.
- Build a structured LLM prompt including:
  - The agent names, purpose, description, skills, limitations (in order if sequential)
  - The `user_instructions` field if provided
  - The `use_case_description` if in auto mode
  - Instruction to output raw JSON matching `GeneratedAgentDraft` schema
- Call Ollama via `OllamaChatModel` (model from env/config, `num_ctx: 32768`).
- Parse JSON response → `GeneratedAgentDraft`.
- Return `OrchestratorGenerationResponse { draft, source: "llm" }`.

**Error cases:**
- 400 if both `agent_ids` empty and `use_case_description` empty.
- 400 if `name` missing.
- 503 if LLM call fails or returns unparseable JSON (return error detail).

### Reuse existing endpoint

Save via existing `POST /api/agents/save-generated-draft` — no backend changes needed for save.

---

## Data flow

```
User fills form → POST /api/agents/generate-orchestrator
  └─ Backend fetches agents from DB
  └─ Builds LLM prompt
  └─ Calls Ollama → parses GeneratedAgentDraft
  └─ Returns draft to frontend

User clicks Sauvegarder → POST /api/agents/save-generated-draft
  └─ Saves agent to DB
  └─ Frontend redirects to /agents/{id}
```

---

## Navigation

- Add "Orchestrators" section in sidebar under "Agents" with a "+ New" link → `/agents/orchestrators/new`.
- Page breadcrumb: `Agents → Orchestrator Builder`.
- After save: redirect to agent detail page.

---

## Schemas

### `OrchestratorGenerationRequest`
```python
class OrchestratorGenerationRequest(OrkBaseSchema):
    name: str = Field(..., min_length=3)
    agent_ids: list[str] = Field(default_factory=list)      # ordered; empty = auto mode
    use_case_description: Optional[str] = None               # auto mode: LLM selects agents
    user_instructions: Optional[str] = None                  # always: extra context for LLM
    routing_strategy: str = "sequential"
```

### `OrchestratorGenerationResponse`
```python
class OrchestratorGenerationResponse(OrkBaseSchema):
    draft: GeneratedAgentDraft
    source: str = "llm"
    selected_agent_ids: list[str]   # populated in auto mode so UI can show which were picked
```

---

## Out of scope

- Parallel / conditional routing strategies (routing_strategy is stored but UI only shows sequential for now).
- Drag-and-drop reordering animation (use HTML5 drag or a simple up/down arrow fallback).
- Agent search/filter within the add-agent modal (list all, scrollable).
- Saving as "draft" vs "designed" — always saves as "draft", user promotes from agent detail page.
