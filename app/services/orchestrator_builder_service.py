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
    slug = slug or "orchestrator"
    return slug[:90]  # DB column is String(100); leave room for suffixes


def _build_agents_block(agents: list[dict]) -> str:
    """Render a numbered list of agent summaries for the LLM prompt."""
    lines: list[str] = []
    for i, a in enumerate(agents, 1):
        limitations = a.get("limitations") or []
        lim_text = "; ".join(limitations[:3]) if limitations else "none specified"
        lines.append(
            f"{i}. {a.get('id', 'unknown')}\n"
            f"   Name: {a.get('name', '')}\n"
            f"   Purpose: {a.get('purpose', '')}\n"
            f"   Description: {a.get('description', '')}\n"
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
        if (a.family_id or "").lower() != "orchestration"
    ]


# ── LLM call ─────────────────────────────────────────────────────────────────

async def _call_llm(system_prompt: str) -> str:
    """Call the configured LLM with a single system prompt. Returns raw text.

    OllamaChatModel.__call__ is a coroutine — must be awaited.
    Messages must be plain dicts (list[dict[str, Any]]).
    Text is extracted from ChatResponse.content (list of TextBlock dicts).
    """
    from app.llm.provider import get_chat_model, is_agentscope_available

    if not is_agentscope_available():
        raise ValueError("AgentScope is not available. Cannot generate orchestrator.")

    model = get_chat_model()
    if model is None:
        raise ValueError("LLM model could not be created. Check OLLAMA_HOST / LLM_PROVIDER config.")

    response = await model([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the orchestrator JSON configuration now."},
    ])

    # ChatResponse.content is a list of TextBlock-like dicts: {"type": "text", "text": "..."}
    content = response.get("content") or []
    text_parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "".join(text_parts)
    if not text:
        # Fallback: stringify the whole response
        text = str(response)
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
    raw = await _call_llm(system_prompt)
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

    from pydantic import ValidationError
    try:
        draft = GeneratedAgentDraft.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"LLM response missing required fields: {exc}") from exc

    # Attach pipeline agent IDs to the draft so save_generated_draft persists them
    draft.pipeline_agent_ids = selected_ids

    return draft, selected_ids
