# Orchestrator Builder Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a split-screen page `/agents/orchestrators/new` that lets the user select existing agents (manual or auto mode), fill an LLM context textarea, and generate a ready-to-save Orchestrator agent.

**Architecture:** Backend: new `POST /api/agents/generate-orchestrator` endpoint + `orchestrator_builder_service.py` that fetches agents from DB, builds an LLM prompt, calls Ollama via `get_chat_model()`, and returns a `GeneratedAgentDraft`. Frontend: split-screen page with a left panel (mode toggle: manual drag-list vs auto textarea) and a right panel (config form + result viewer with Prompt/Skills/Config tabs). Save via existing `POST /api/agents/save-generated-draft`.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Next.js 14 App Router + TypeScript + Tailwind + `ork-*` design tokens (frontend), AgentScope `OllamaChatModel` / `get_chat_model()` from `app/llm/provider.py`, lucide-react icons.

---

## File map

```
Backend
  app/schemas/agent.py                               ← append 2 new schema classes
  app/services/orchestrator_builder_service.py       ← NEW — LLM call + draft assembly
  app/api/routes/agents.py                           ← add POST /generate-orchestrator

Frontend
  frontend/src/lib/agent-registry/types.ts           ← append 2 new TS types
  frontend/src/lib/agent-registry/service.ts         ← append generateOrchestratorDraft()
  frontend/src/components/agents/orchestrator-builder/AgentPipelinePanel.tsx   ← NEW
  frontend/src/components/agents/orchestrator-builder/OrchestratorResultPanel.tsx ← NEW
  frontend/src/app/agents/orchestrators/new/page.tsx ← NEW — main split-screen page
  frontend/src/components/layout/sidebar.tsx         ← add nav item
```

---

## Task 1 — Backend schemas

**Files:**
- Modify: `app/schemas/agent.py` (append after last class `SaveGeneratedDraftRequest`)

- [ ] **Step 1: Open `app/schemas/agent.py` and append the two new schema classes at the end of the file**

The file already imports `Optional` and `Field`. Add after `SaveGeneratedDraftRequest`:

```python
class OrchestratorGenerationRequest(OrkBaseSchema):
    """Request body for POST /generate-orchestrator."""
    name: str = Field(..., min_length=3, description="snake_case id for the orchestrator")
    agent_ids: list[str] = Field(
        default_factory=list,
        description="Ordered list of agent IDs (manual mode). Empty = auto mode.",
    )
    use_case_description: Optional[str] = Field(
        None,
        description="Free-text pipeline description (auto mode). LLM selects agents.",
    )
    user_instructions: Optional[str] = Field(
        None,
        description="Extra context/priorities/constraints passed to LLM in both modes.",
    )
    routing_strategy: str = Field(default="sequential")


class OrchestratorGenerationResponse(OrkBaseSchema):
    """Response from POST /generate-orchestrator."""
    draft: GeneratedAgentDraft
    source: str = "llm"
    selected_agent_ids: list[str] = Field(
        default_factory=list,
        description="Agent IDs picked by the LLM (populated in auto mode).",
    )
```

- [ ] **Step 2: Verify the file parses**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
python -c "from app.schemas.agent import OrchestratorGenerationRequest, OrchestratorGenerationResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/schemas/agent.py
git commit -m "feat(orchestrator-builder): add OrchestratorGenerationRequest/Response schemas"
```

---

## Task 2 — Backend orchestrator builder service

**Files:**
- Create: `app/services/orchestrator_builder_service.py`

- [ ] **Step 1: Write a failing test**

Create `tests/services/test_orchestrator_builder_service.py`:

```python
"""Unit tests for orchestrator_builder_service (LLM-independent parts)."""
import pytest
from app.services.orchestrator_builder_service import (
    _build_agents_block,
    _parse_llm_json,
    _slugify_name,
)


def test_slugify_name():
    assert _slugify_name("Hotel Pipeline Orchestrator") == "hotel_pipeline_orchestrator"
    assert _slugify_name("  My Agent!! ") == "my_agent"


def test_parse_llm_json_clean():
    raw = '{"agent_id":"x","name":"X","family_id":"orchestration","purpose":"p","description":"d","skill_ids":["s"],"selection_hints":{"routing_keywords":["a"],"workflow_ids":[],"use_case_hint":"u","requires_grounded_evidence":false},"allowed_mcps":[],"forbidden_effects":[],"criticality":"medium","cost_profile":"medium","limitations":["l1"],"prompt_content":"pc","skills_content":"sc","version":"1.0.0","status":"draft"}'
    result = _parse_llm_json(raw)
    assert result["agent_id"] == "x"
    assert result["limitations"] == ["l1"]


def test_parse_llm_json_with_fences():
    raw = '```json\n{"agent_id":"x","name":"X","family_id":"orchestration","purpose":"p","description":"d","skill_ids":["s"],"selection_hints":{"routing_keywords":["a"],"workflow_ids":[],"use_case_hint":"u","requires_grounded_evidence":false},"allowed_mcps":[],"forbidden_effects":[],"criticality":"medium","cost_profile":"medium","limitations":["l1"],"prompt_content":"pc","skills_content":"sc","version":"1.0.0","status":"draft"}\n```'
    result = _parse_llm_json(raw)
    assert result["name"] == "X"


def test_parse_llm_json_invalid_raises():
    with pytest.raises(ValueError, match="LLM returned invalid JSON"):
        _parse_llm_json("not json at all")


def test_build_agents_block_ordered():
    agents = [
        {"id": "weather_agent", "name": "Weather Agent", "purpose": "Check weather", "description": "Searches forecasts", "limitations": ["7-day limit"]},
        {"id": "budget_agent", "name": "Budget Agent", "purpose": "Score budget", "description": "Evaluates fit", "limitations": []},
    ]
    block = _build_agents_block(agents)
    assert "1. weather_agent" in block
    assert "2. budget_agent" in block
    assert "Check weather" in block
```

- [ ] **Step 2: Run — confirm fails**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
python -m pytest tests/services/test_orchestrator_builder_service.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or `ImportError` (file doesn't exist yet).

- [ ] **Step 3: Create `app/services/orchestrator_builder_service.py`**

```python
"""Orchestrator Builder Service.

Fetches selected agents from DB, builds an LLM prompt, calls Ollama,
and returns a GeneratedAgentDraft for the new orchestrator agent.
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent import GeneratedAgentDraft, OrchestratorGenerationRequest

logger = logging.getLogger(__name__)


# ── Helpers (pure, testable without DB or LLM) ────────────────────────────────

def _slugify_name(name: str) -> str:
    """Convert a human name to a snake_case id."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "orchestrator"


def _build_agents_block(agents: list[dict]) -> str:
    """Render a numbered list of agent summaries for the LLM prompt."""
    lines: list[str] = []
    for i, a in enumerate(agents, 1):
        limitations = a.get("limitations") or []
        lim_text = "; ".join(limitations[:3]) if limitations else "none specified"
        lines.append(
            f"{i}. {a['id']}\n"
            f"   Name: {a['name']}\n"
            f"   Purpose: {a['purpose']}\n"
            f"   Description: {a['description']}\n"
            f"   Limitations: {lim_text}"
        )
    return "\n\n".join(lines)


def _parse_llm_json(raw: str) -> dict:
    """Extract and parse JSON from LLM output (handles markdown fences)."""
    # Strip markdown code fences if present
    clean = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    clean = re.sub(r"```\s*$", "", clean, flags=re.MULTILINE).strip()

    # Try direct parse first
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Fallback: find first {...} block
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"LLM returned invalid JSON. Raw output (first 300 chars): {raw[:300]}")


def _build_system_prompt(
    agent_block: str,
    orchestrator_name: str,
    routing_strategy: str,
    user_instructions: str | None,
    use_case_description: str | None,
    is_auto_mode: bool,
) -> str:
    slug = _slugify_name(orchestrator_name)
    mode_section = ""
    if is_auto_mode and use_case_description:
        mode_section = f"\nUSER'S PIPELINE DESCRIPTION:\n{use_case_description}\n"

    instructions_section = ""
    if user_instructions:
        instructions_section = f"\nADDITIONAL INSTRUCTIONS FROM USER:\n{user_instructions}\n"

    return f"""You are an expert AI architect. Your task is to generate a configuration for an Orchestrator agent that coordinates a pipeline of specialized agents.

ORCHESTRATOR NAME: {orchestrator_name} (id: {slug})
ROUTING STRATEGY: {routing_strategy}
{mode_section}{instructions_section}
AGENTS IN THE PIPELINE (in execution order):
{agent_block}

Generate a complete orchestrator agent configuration. The orchestrator must:
- Know the purpose and capabilities of each agent in its pipeline
- Route tasks to the correct agents in the right order
- Pass accumulated context from each agent to the next
- Handle errors without blocking the pipeline

YOUR RESPONSE MUST BE RAW JSON ONLY — no markdown, no prose, no code fences.
Output exactly this JSON schema (all fields required):

{{
  "agent_id": "{slug}",
  "name": "{orchestrator_name}",
  "family_id": "orchestration",
  "purpose": "<one sentence: what this orchestrator does>",
  "description": "<2-3 sentences: pipeline it manages, agent order, coordination logic>",
  "skill_ids": ["sequential_routing", "context_propagation"],
  "selection_hints": {{
    "routing_keywords": ["orchestrate", "pipeline", "coordinate"],
    "workflow_ids": [],
    "use_case_hint": "<short use case description>",
    "requires_grounded_evidence": false
  }},
  "allowed_mcps": [],
  "forbidden_effects": ["publish", "approve", "external_act", "book", "purchase"],
  "criticality": "medium",
  "cost_profile": "medium",
  "limitations": [
    "<limitation 1>",
    "<limitation 2>"
  ],
  "prompt_content": "<the full system prompt for this orchestrator — 200-400 words>",
  "skills_content": "<description of orchestration skills: sequential_routing: ... context_propagation: ...>",
  "version": "1.0.0",
  "status": "draft"
}}

Rules:
- prompt_content must be a detailed system prompt (200+ words) describing exactly how the orchestrator coordinates the agents
- skills_content must describe each skill_id as "skill_name: description" separated by newlines
- limitations must be a non-empty list (at least 2 items)
- selection_hints.routing_keywords must include relevant keywords for routing
- Do NOT include any text outside the JSON object"""


# ── DB fetching ───────────────────────────────────────────────────────────────

async def _fetch_agents_as_dicts(
    db: AsyncSession,
    agent_ids: list[str],
) -> list[dict]:
    """Fetch specific agents by ID, preserving order. Raises ValueError if any missing."""
    from app.services.agent_registry_service import get_agent

    result = []
    for aid in agent_ids:
        agent = await get_agent(db, aid)
        if agent is None:
            raise ValueError(f"Agent '{aid}' not found in registry")
        result.append({
            "id": agent.id,
            "name": agent.name,
            "purpose": agent.purpose or "",
            "description": agent.description or "",
            "limitations": agent.limitations or [],
        })
    return result


async def _fetch_all_agents_as_dicts(db: AsyncSession) -> list[dict]:
    """Fetch all active/designed agents for auto-mode selection."""
    from app.services.agent_registry_service import list_agents

    agents, _ = await list_agents(db, status="designed", limit=100)
    if not agents:
        # Fall back to all statuses if no designed agents
        agents, _ = await list_agents(db, limit=100)

    return [
        {
            "id": a.id,
            "name": a.name,
            "purpose": a.purpose or "",
            "description": a.description or "",
            "limitations": a.limitations or [],
        }
        for a in agents
    ]


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_llm(system_prompt: str) -> str:
    """Call the configured LLM with a single system prompt. Returns raw text."""
    from app.llm.provider import get_chat_model, is_agentscope_available

    if not is_agentscope_available():
        raise ValueError("AgentScope is not available. Cannot generate orchestrator.")

    model = get_chat_model()
    if model is None:
        raise ValueError("LLM model could not be created. Check OLLAMA_HOST / LLM_PROVIDER config.")

    from agentscope.message import Msg

    response = model([
        Msg(name="system", content=system_prompt, role="system"),
        Msg(name="user", content="Generate the orchestrator JSON configuration now.", role="user"),
    ])

    text = response.text if hasattr(response, "text") else str(response)
    logger.debug("LLM raw response (first 500): %s", text[:500])
    return text


# ── Main entry point ──────────────────────────────────────────────────────────

async def generate_orchestrator(
    db: AsyncSession,
    req: OrchestratorGenerationRequest,
) -> tuple[GeneratedAgentDraft, list[str]]:
    """Generate an orchestrator draft via LLM.

    Returns (draft, selected_agent_ids).
    selected_agent_ids is populated in auto mode to tell the UI which agents were selected.
    """
    is_auto_mode = len(req.agent_ids) == 0

    if is_auto_mode and not req.use_case_description:
        raise ValueError("In auto mode, use_case_description is required.")

    # Fetch agents
    if is_auto_mode:
        agents = await _fetch_all_agents_as_dicts(db)
        selected_ids = [a["id"] for a in agents]
    else:
        agents = await _fetch_agents_as_dicts(db, req.agent_ids)
        selected_ids = req.agent_ids

    if not agents:
        raise ValueError("No agents found. Add agents to the registry first.")

    agent_block = _build_agents_block(agents)
    system_prompt = _build_system_prompt(
        agent_block=agent_block,
        orchestrator_name=req.name,
        routing_strategy=req.routing_strategy,
        user_instructions=req.user_instructions,
        use_case_description=req.use_case_description,
        is_auto_mode=is_auto_mode,
    )

    # Call LLM
    raw = _call_llm(system_prompt)
    data = _parse_llm_json(raw)

    # Ensure required non-empty fields
    if not data.get("limitations"):
        data["limitations"] = ["Performance depends on the reliability of sub-agents in the pipeline"]
    if not data.get("skills_content"):
        data["skills_content"] = (
            "sequential_routing: Execute pipeline agents in strict sequential order, "
            "passing accumulated context to each step\n"
            "context_propagation: Merge outputs of each agent into a shared context "
            "transmitted to subsequent agents"
        )

    draft = GeneratedAgentDraft.model_validate(data)
    return draft, selected_ids
```

- [ ] **Step 4: Run tests — confirm pass**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
python -m pytest tests/services/test_orchestrator_builder_service.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/orchestrator_builder_service.py tests/services/test_orchestrator_builder_service.py
git commit -m "feat(orchestrator-builder): add orchestrator_builder_service with LLM generation"
```

---

## Task 3 — Backend API endpoint

**Files:**
- Modify: `app/api/routes/agents.py`

- [ ] **Step 1: Add the import at the top of `app/api/routes/agents.py`**

Find the existing imports block (around line 10-20). Add:

```python
from app.services import orchestrator_builder_service
from app.schemas.agent import OrchestratorGenerationRequest, OrchestratorGenerationResponse
```

These go alongside the existing imports like `from app.services import agent_generation_service`.

- [ ] **Step 2: Add the endpoint after the `save-generated-draft` endpoint**

Find the block ending with:
```python
@router.post("/save-generated-draft", response_model=AgentOut, status_code=201)
async def save_generated_draft(
    data: SaveGeneratedDraftRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        agent = await agent_registry_service.save_generated_draft(db, data.draft)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

Add immediately after it:

```python
@router.post("/generate-orchestrator", response_model=OrchestratorGenerationResponse)
async def generate_orchestrator(
    data: OrchestratorGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate an orchestrator agent draft via LLM.

    Manual mode: provide agent_ids (ordered list).
    Auto mode: provide use_case_description; LLM selects agents from registry.
    """
    if not data.name or len(data.name) < 3:
        raise HTTPException(status_code=400, detail="name must be at least 3 characters")
    if not data.agent_ids and not data.use_case_description:
        raise HTTPException(
            status_code=400,
            detail="Provide agent_ids (manual mode) or use_case_description (auto mode)",
        )
    try:
        draft, selected_ids = await orchestrator_builder_service.generate_orchestrator(db, data)
        return OrchestratorGenerationResponse(
            draft=draft,
            source="llm",
            selected_agent_ids=selected_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Orchestrator generation failed")
        raise HTTPException(status_code=503, detail=f"LLM generation failed: {exc}")
```

- [ ] **Step 3: Verify the app starts without import errors**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
python -c "from app.api.routes.agents import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Check the route appears in OpenAPI**

```bash
curl -s http://localhost:8200/openapi.json | python -m json.tool | grep generate-orchestrator
```

Expected: `"path": "/api/agents/generate-orchestrator"` (or similar) — only run this if the server is already running.

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/agents.py
git commit -m "feat(orchestrator-builder): add POST /api/agents/generate-orchestrator endpoint"
```

---

## Task 4 — Frontend TypeScript types

**Files:**
- Modify: `frontend/src/lib/agent-registry/types.ts` (append at end)

- [ ] **Step 1: Append two new interfaces at the end of `frontend/src/lib/agent-registry/types.ts`**

```typescript
export interface OrchestratorGenerationRequest {
  name: string;
  agent_ids: string[];               // ordered; empty = auto mode
  use_case_description?: string;     // auto mode: free-text pipeline description
  user_instructions?: string;        // always: extra context for LLM
  routing_strategy?: string;         // default: "sequential"
}

export interface OrchestratorGenerationResponse {
  draft: GeneratedAgentDraft;
  source: string;
  selected_agent_ids: string[];      // populated in auto mode
}
```

- [ ] **Step 2: Verify TypeScript compiles with no new errors**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors (pre-existing errors are OK to ignore if count doesn't increase).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/agent-registry/types.ts
git commit -m "feat(orchestrator-builder): add OrchestratorGenerationRequest/Response TS types"
```

---

## Task 5 — Frontend service function

**Files:**
- Modify: `frontend/src/lib/agent-registry/service.ts` (append one function)

- [ ] **Step 1: Add import at the top of `service.ts` if not already present**

Check if `OrchestratorGenerationRequest` and `OrchestratorGenerationResponse` are already in the import from `./types`. If not, add them:

```typescript
import type {
  // ... existing imports ...
  OrchestratorGenerationRequest,
  OrchestratorGenerationResponse,
} from "./types";
```

- [ ] **Step 2: Append the new function at the end of `service.ts`**

```typescript
export async function generateOrchestratorDraft(
  payload: OrchestratorGenerationRequest,
): Promise<OrchestratorGenerationResponse> {
  return request<OrchestratorGenerationResponse>(`${BASE}/generate-orchestrator`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
```

`BASE` is already defined as `"/api/agents"` in the file.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/agent-registry/service.ts
git commit -m "feat(orchestrator-builder): add generateOrchestratorDraft() service function"
```

---

## Task 6 — Frontend AgentPipelinePanel component

**Files:**
- Create: `frontend/src/components/agents/orchestrator-builder/AgentPipelinePanel.tsx`

This is the left panel of the split-screen. It handles two modes:
- **Manual**: numbered, drag-and-drop ordered list of selected agents + an "Add" dropdown
- **Auto**: a textarea where the user describes the pipeline in natural language

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /Users/mbensass/projetPreso/multiAgents/orkestra/frontend/src/components/agents/orchestrator-builder
```

- [ ] **Step 2: Create `AgentPipelinePanel.tsx`**

```tsx
"use client";

import { useState, useRef } from "react";
import { GripVertical, X, Plus } from "lucide-react";
import type { AgentDefinition } from "@/lib/agent-registry/types";

export type SelectionMode = "manual" | "auto";

interface AgentPipelinePanelProps {
  mode: SelectionMode;
  onModeChange: (mode: SelectionMode) => void;
  /** Manual mode: ordered list of selected agent IDs */
  selectedIds: string[];
  onSelectedIdsChange: (ids: string[]) => void;
  /** Auto mode: free-text description */
  useCase: string;
  onUseCaseChange: (text: string) => void;
  /** Full registry for the add-agent picker */
  allAgents: AgentDefinition[];
}

export default function AgentPipelinePanel({
  mode,
  onModeChange,
  selectedIds,
  onSelectedIdsChange,
  useCase,
  onUseCaseChange,
  allAgents,
}: AgentPipelinePanelProps) {
  const [showPicker, setShowPicker] = useState(false);
  const dragIdx = useRef<number | null>(null);

  // ── Drag & drop ──────────────────────────────────────────────────────
  function handleDragStart(idx: number) {
    dragIdx.current = idx;
  }

  function handleDrop(targetIdx: number) {
    const from = dragIdx.current;
    if (from === null || from === targetIdx) return;
    const next = [...selectedIds];
    const [moved] = next.splice(from, 1);
    next.splice(targetIdx, 0, moved);
    onSelectedIdsChange(next);
    dragIdx.current = null;
  }

  function removeAgent(id: string) {
    onSelectedIdsChange(selectedIds.filter((x) => x !== id));
  }

  function addAgent(id: string) {
    if (!selectedIds.includes(id)) {
      onSelectedIdsChange([...selectedIds, id]);
    }
    setShowPicker(false);
  }

  // Agents not yet in the pipeline
  const available = allAgents.filter((a) => !selectedIds.includes(a.id));

  // Lookup map for display
  const agentMap = Object.fromEntries(allAgents.map((a) => [a.id, a]));

  return (
    <div className="flex flex-col h-full bg-[#111827] border-r border-[#1e2530]">

      {/* Mode toggle bar */}
      <div className="px-4 py-3 border-b border-[#1e2530] flex items-center gap-3">
        <span className="text-xs text-ork-dim">Mode :</span>
        <div className="flex bg-[#0d1117] border border-[#2d3748] rounded-full p-0.5">
          {(["manual", "auto"] as const).map((m) => (
            <button
              key={m}
              onClick={() => onModeChange(m)}
              className={`text-xs px-4 py-1.5 rounded-full transition-colors font-mono ${
                mode === m
                  ? "bg-ork-cyan text-black font-bold"
                  : "text-ork-dim hover:text-ork-text"
              }`}
            >
              {m === "manual" ? "Manuel" : "Auto (LLM choisit)"}
            </button>
          ))}
        </div>
      </div>

      {/* Manual mode — drag & drop list */}
      {mode === "manual" && (
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="px-4 pt-3 pb-1 text-[10px] text-ork-dim uppercase tracking-widest">
            Pipeline d&apos;agents — glisser pour ordonner
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2 flex flex-col gap-2">
            {selectedIds.map((id, idx) => {
              const agent = agentMap[id];
              return (
                <div
                  key={id}
                  draggable
                  onDragStart={() => handleDragStart(idx)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDrop(idx)}
                  className="flex items-center gap-2 bg-[#1e2530] border border-ork-cyan rounded-md px-3 py-2 cursor-grab active:cursor-grabbing"
                >
                  <GripVertical className="w-4 h-4 text-[#2d3748] shrink-0" />
                  <span className="bg-ork-cyan text-black text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0">
                    {idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-ork-cyan font-mono truncate">{id}</div>
                    {agent && (
                      <div className="text-[10px] text-ork-dim truncate">{agent.name}</div>
                    )}
                  </div>
                  <button
                    onClick={() => removeAgent(id)}
                    className="text-ork-dim hover:text-ork-red shrink-0"
                    aria-label={`Remove ${id}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })}

            {/* Add button */}
            <div className="relative">
              <button
                onClick={() => setShowPicker((v) => !v)}
                className="w-full border border-dashed border-[#2d3748] rounded-md py-2 text-xs text-ork-dim hover:border-ork-cyan hover:text-ork-cyan flex items-center justify-center gap-1.5 transition-colors"
              >
                <Plus className="w-3 h-3" />
                Ajouter un agent…
              </button>

              {showPicker && (
                <div className="absolute left-0 right-0 top-full mt-1 z-20 bg-[#1e2530] border border-[#2d3748] rounded-md shadow-lg max-h-48 overflow-y-auto">
                  {available.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-ork-dim">Tous les agents sont déjà sélectionnés</div>
                  ) : (
                    available.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => addAgent(a.id)}
                        className="w-full text-left px-3 py-2 text-xs text-ork-text hover:bg-ork-cyan/10 hover:text-ork-cyan border-b border-[#0d1117] last:border-0 font-mono"
                      >
                        {a.id}
                        <span className="ml-2 text-ork-dim font-sans">{a.name}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Auto mode — textarea */}
      {mode === "auto" && (
        <div className="flex flex-col flex-1 p-4 gap-3">
          <div className="text-[10px] text-ork-dim uppercase tracking-widest">
            Décris ton pipeline
          </div>
          <textarea
            className="flex-1 bg-[#0d1117] border border-[#2d6a7a] rounded-md p-3 text-xs text-[#a0c4ce] font-mono resize-none focus:outline-none focus:border-ork-cyan placeholder:text-[#2d3748]"
            placeholder="Ex: Je veux un pipeline qui gère la recherche hôtelière. Il doit évaluer la météo, vérifier le budget, puis trouver les hôtels disponibles…"
            value={useCase}
            onChange={(e) => onUseCaseChange(e.target.value)}
          />
          <p className="text-[10px] text-ork-dim leading-relaxed">
            Le LLM lira les descriptions de tous les agents disponibles et sélectionnera ceux qui correspondent à ton pipeline.
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/agents/orchestrator-builder/AgentPipelinePanel.tsx
git commit -m "feat(orchestrator-builder): add AgentPipelinePanel component (manual/auto toggle)"
```

---

## Task 7 — Frontend OrchestratorResultPanel component

**Files:**
- Create: `frontend/src/components/agents/orchestrator-builder/OrchestratorResultPanel.tsx`

This renders after generation: tabs (Prompt / Skills / Config) + Modifier / Regénérer / Sauvegarder buttons.

- [ ] **Step 1: Create `OrchestratorResultPanel.tsx`**

```tsx
"use client";

import { useState } from "react";
import { RotateCcw, Save } from "lucide-react";
import type { GeneratedAgentDraft } from "@/lib/agent-registry/types";

type Tab = "prompt" | "skills" | "config";

interface OrchestratorResultPanelProps {
  draft: GeneratedAgentDraft;
  selectedAgentIds: string[];
  onModify: () => void;
  onRegenerate: () => void;
  onSave: () => Promise<void>;
  saving: boolean;
}

export default function OrchestratorResultPanel({
  draft,
  selectedAgentIds,
  onModify,
  onRegenerate,
  onSave,
  saving,
}: OrchestratorResultPanelProps) {
  const [tab, setTab] = useState<Tab>("prompt");

  const configJson = JSON.stringify(
    {
      id: draft.agent_id,
      name: draft.name,
      family_id: draft.family_id,
      agent_ids: selectedAgentIds,
      mode: "sequential",
      criticality: draft.criticality,
      cost_profile: draft.cost_profile,
    },
    null,
    2,
  );

  const tabs: { key: Tab; label: string }[] = [
    { key: "prompt", label: "Prompt" },
    { key: "skills", label: "Skills" },
    { key: "config", label: "Config" },
  ];

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Tab bar + actions */}
      <div className="flex items-center border-b border-[#1e2530] bg-[#111827] px-4">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-xs px-4 py-3 border-b-2 font-mono transition-colors -mb-px ${
              tab === t.key
                ? "border-ork-cyan text-ork-cyan"
                : "border-transparent text-ork-dim hover:text-ork-text"
            }`}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={onModify}
            className="text-xs px-3 py-1.5 bg-[#1e2530] text-ork-text rounded hover:bg-[#2d3748] transition-colors"
          >
            ✎ Modifier
          </button>
          <button
            onClick={onRegenerate}
            className="text-xs px-3 py-1.5 bg-[#1e2530] text-ork-text rounded hover:bg-[#2d3748] transition-colors flex items-center gap-1"
          >
            <RotateCcw className="w-3 h-3" />
            Regénérer
          </button>
          <button
            onClick={onSave}
            disabled={saving}
            className="text-xs px-4 py-1.5 bg-ork-cyan text-black font-bold rounded hover:bg-ork-cyan/90 transition-colors flex items-center gap-1 disabled:opacity-50"
          >
            <Save className="w-3 h-3" />
            {saving ? "Sauvegarde…" : "Sauvegarder"}
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-5">
        {tab === "prompt" && (
          <div>
            <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-3">
              Prompt généré
            </div>
            <pre className="bg-[#111827] border border-[#1e2530] rounded-lg p-4 text-xs text-[#a0c4ce] font-mono leading-relaxed whitespace-pre-wrap">
              {draft.prompt_content}
            </pre>
          </div>
        )}

        {tab === "skills" && (
          <div>
            <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-3">
              Skills générées
            </div>
            <div className="flex flex-col gap-3">
              {draft.skill_ids.map((skillId) => {
                // Extract description from skills_content (format: "skill_name: description")
                const match = new RegExp(
                  `${skillId}:\\s*([^\\n]+)`,
                  "i",
                ).exec(draft.skills_content ?? "");
                const desc = match ? match[1].trim() : "";
                return (
                  <div
                    key={skillId}
                    className="bg-[#111827] border border-[#1e2530] rounded-lg px-4 py-3"
                  >
                    <div className="text-xs text-ork-cyan font-mono font-semibold mb-1">
                      {skillId}
                    </div>
                    {desc && (
                      <div className="text-xs text-ork-dim leading-relaxed">{desc}</div>
                    )}
                  </div>
                );
              })}
              {draft.limitations.length > 0 && (
                <div className="mt-2">
                  <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-2">
                    Limitations
                  </div>
                  <ul className="list-disc list-inside text-xs text-ork-dim space-y-1">
                    {draft.limitations.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "config" && (
          <div>
            <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-3">
              Configuration JSON
            </div>
            <pre className="bg-[#111827] border border-[#1e2530] rounded-lg p-4 text-xs text-[#a0c4ce] font-mono leading-relaxed">
              {configJson}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/agents/orchestrator-builder/OrchestratorResultPanel.tsx
git commit -m "feat(orchestrator-builder): add OrchestratorResultPanel component (tabs)"
```

---

## Task 8 — Frontend page + sidebar

**Files:**
- Create: `frontend/src/app/agents/orchestrators/new/page.tsx`
- Modify: `frontend/src/components/layout/sidebar.tsx`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /Users/mbensass/projetPreso/multiAgents/orkestra/frontend/src/app/agents/orchestrators/new
```

- [ ] **Step 2: Create `page.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import AgentPipelinePanel, {
  type SelectionMode,
} from "@/components/agents/orchestrator-builder/AgentPipelinePanel";
import OrchestratorResultPanel from "@/components/agents/orchestrator-builder/OrchestratorResultPanel";
import { listAgents, generateOrchestratorDraft, saveGeneratedDraft } from "@/lib/agent-registry/service";
import type { AgentDefinition, GeneratedAgentDraft } from "@/lib/agent-registry/types";

export default function OrchestratorBuilderPage() {
  const router = useRouter();

  // Registry
  const [allAgents, setAllAgents] = useState<AgentDefinition[]>([]);

  // Left panel state
  const [mode, setMode] = useState<SelectionMode>("manual");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [useCase, setUseCase] = useState("");

  // Right panel — config form
  const [name, setName] = useState("");
  const [userInstructions, setUserInstructions] = useState("");

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [draft, setDraft] = useState<GeneratedAgentDraft | null>(null);
  const [resultSelectedIds, setResultSelectedIds] = useState<string[]>([]);

  // Save state
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listAgents().then(setAllAgents).catch(console.error);
  }, []);

  const canGenerate =
    name.trim().length >= 3 &&
    (mode === "manual" ? selectedIds.length >= 2 : useCase.trim().length > 0);

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    try {
      const resp = await generateOrchestratorDraft({
        name: name.trim(),
        agent_ids: mode === "manual" ? selectedIds : [],
        use_case_description: mode === "auto" ? useCase.trim() : undefined,
        user_instructions: userInstructions.trim() || undefined,
        routing_strategy: "sequential",
      });
      setDraft(resp.draft);
      setResultSelectedIds(
        mode === "manual" ? selectedIds : resp.selected_agent_ids,
      );
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Génération échouée");
    } finally {
      setGenerating(false);
    }
  }

  function handleModify() {
    setDraft(null);
    setGenerateError(null);
  }

  async function handleSave() {
    if (!draft) return;
    setSaving(true);
    try {
      const saved = await saveGeneratedDraft(draft);
      router.push(`/agents/${saved.id}`);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Sauvegarde échouée");
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col h-screen bg-ork-bg overflow-hidden">
      {/* Page header */}
      <div className="flex items-center gap-4 px-6 py-3.5 border-b border-[#1e2530] bg-ork-bg shrink-0">
        <button
          onClick={() => router.push("/agents")}
          className="text-xs text-ork-dim hover:text-ork-text transition-colors"
        >
          ← Agents
        </button>
        <h1 className="text-base font-bold font-mono text-ork-text">
          Orchestrator Builder
        </h1>
        <span className="text-[10px] text-ork-cyan border border-ork-cyan px-2 py-0.5 rounded-full">
          BETA
        </span>
      </div>

      {/* Split layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT — agent selection */}
        <div className="w-80 shrink-0 flex flex-col overflow-hidden">
          <AgentPipelinePanel
            mode={mode}
            onModeChange={setMode}
            selectedIds={selectedIds}
            onSelectedIdsChange={setSelectedIds}
            useCase={useCase}
            onUseCaseChange={setUseCase}
            allAgents={allAgents}
          />
        </div>

        {/* RIGHT — config + result */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Config form — fades when result shown */}
          <div
            className={`px-6 py-5 border-b border-[#1e2530] flex flex-col gap-4 shrink-0 transition-opacity ${
              draft ? "opacity-50" : "opacity-100"
            }`}
          >
            {/* Name */}
            <div>
              <label className="block text-[10px] text-ork-dim uppercase tracking-widest mb-1.5">
                Nom de l&apos;orchestrateur
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="hotel_pipeline_orchestrator"
                disabled={!!draft}
                className="w-full bg-[#1e2530] border border-[#2d3748] rounded-md px-3 py-2 text-sm text-ork-text font-mono placeholder:text-[#2d3748] focus:outline-none focus:border-ork-cyan disabled:cursor-not-allowed"
              />
            </div>

            {/* LLM instructions */}
            <div>
              <label className="block text-[10px] text-ork-dim uppercase tracking-widest mb-1.5">
                Instructions pour le LLM{" "}
                <span className="text-[9px] normal-case tracking-normal">
                  (contexte, priorités, contraintes…)
                </span>
              </label>
              <textarea
                value={userInstructions}
                onChange={(e) => setUserInstructions(e.target.value)}
                placeholder="Ex: Cet orchestrateur gère un pipeline hôtelier. Les agents doivent être appelés dans l'ordre : météo → budget → hôtels…"
                disabled={!!draft}
                rows={3}
                className="w-full bg-[#1e2530] border border-[#2d6a7a] rounded-md px-3 py-2 text-xs text-[#a0c4ce] font-mono placeholder:text-[#2d3748] focus:outline-none focus:border-ork-cyan resize-none disabled:cursor-not-allowed"
              />
            </div>

            {/* Generate button */}
            {!draft && (
              <button
                onClick={handleGenerate}
                disabled={!canGenerate || generating}
                className="w-full bg-ork-cyan text-black font-bold py-3 rounded-lg text-sm flex items-center justify-center gap-2 hover:bg-ork-cyan/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {generating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Génération en cours…
                  </>
                ) : (
                  "⚡ Générer l'orchestrateur"
                )}
              </button>
            )}

            {generateError && (
              <div className="text-xs text-ork-red bg-ork-red/10 border border-ork-red/30 rounded-md px-3 py-2">
                {generateError}
              </div>
            )}

            {!canGenerate && !generating && !draft && (
              <p className="text-[10px] text-ork-dim">
                {mode === "manual"
                  ? "Sélectionne au moins 2 agents et donne un nom (≥ 3 caractères)."
                  : "Décris ton pipeline et donne un nom (≥ 3 caractères)."}
              </p>
            )}
          </div>

          {/* Result panel */}
          {draft && (
            <OrchestratorResultPanel
              draft={draft}
              selectedAgentIds={resultSelectedIds}
              onModify={handleModify}
              onRegenerate={handleGenerate}
              onSave={handleSave}
              saving={saving}
            />
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add nav item to sidebar**

Open `frontend/src/components/layout/sidebar.tsx`. Find the `NAV` array. After the `{ label: "Agents", href: "/agents", icon: Bot }` entry, add:

```typescript
{ label: "Orchestrateurs", href: "/agents/orchestrators/new", icon: Bot },
```

The full updated NAV entry block (around the Agents section) will look like:

```typescript
{ section: "Registries" },
{ label: "Agents", href: "/agents", icon: Bot },
{ label: "Orchestrateurs", href: "/agents/orchestrators/new", icon: Bot },
{ label: "Families", href: "/agents/families", icon: Bot },
{ label: "Agent Skills", href: "/agents/skills", icon: Bot },
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 5: Check the page loads in dev server**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npm run dev &
```

Open `http://localhost:3300/agents/orchestrators/new` in the browser. You should see:
- Header: "← Agents | Orchestrator Builder | BETA"
- Left panel with toggle "Manuel / Auto (LLM choisit)"
- Right panel with name input, instructions textarea, and disabled generate button
- "Orchestrateurs" in the sidebar

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/agents/orchestrators/new/page.tsx frontend/src/components/layout/sidebar.tsx
git commit -m "feat(orchestrator-builder): add split-screen page and sidebar nav item"
```

---

## Self-Review Checklist (done by plan author)

**Spec coverage:**
- ✅ Split-screen layout with left/right panels
- ✅ Mode toggle Manual / Auto with distinct left panel content
- ✅ Manual: drag-and-drop ordered agent list + add picker
- ✅ Auto: free-text textarea + hint
- ✅ "Instructions pour le LLM" textarea (right panel, always)
- ✅ Name field (right panel)
- ✅ Generate button with disable conditions (≥2 agents manual / non-empty auto / name ≥3)
- ✅ Result panel: Prompt / Skills / Config tabs
- ✅ Modifier / Regénérer / Sauvegarder buttons
- ✅ Backend: manual mode (fetch by IDs in order) vs auto mode (fetch all, LLM selects)
- ✅ `selected_agent_ids` returned in response (populated in auto mode)
- ✅ Redirect to `/agents/{id}` after save
- ✅ Sidebar nav item

**Type consistency:**
- `generateOrchestratorDraft()` returns `OrchestratorGenerationResponse` — matches type in types.ts ✅
- `draft.agent_id` used in `OrchestratorResultPanel` — matches `GeneratedAgentDraft.agent_id` ✅
- `saveGeneratedDraft(draft)` — already exists in service.ts, takes `GeneratedAgentDraft`, returns `AgentDefinition` ✅
- `saved.id` used for redirect — `AgentDefinition.id` exists ✅

**No placeholders:** All code blocks are complete. ✅
