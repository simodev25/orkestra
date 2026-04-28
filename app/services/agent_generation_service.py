"""Structured draft generation for Agent Registry."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.llm.provider import get_chat_model, is_agentscope_available
from app.models.platform_capability import PlatformCapability
from app.models.secret import PlatformSecret
from app.schemas.agent import AgentGenerationRequest, GeneratedAgentDraft, McpCatalogSummary

logger = logging.getLogger(__name__)

_TRACE_DIR = Path(os.getenv("ORKESTRA_DEBUG_AGENT_GENERATION_DIR", "/app/storage/debug-agent-generation"))
_LLM_TIMEOUT_SECONDS = 30


@dataclass
class AgentGenerationContext:
    families: list[dict]
    skills: list[dict]
    similar_agents: list[dict]


@dataclass
class _RankedMcp:
    mcp: McpCatalogSummary
    score: int
    reason: str


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not slug:
        slug = "generated_agent"
    if len(slug) > 90:
        slug = slug[:90].rstrip("_")
    return slug


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower())}


def _truncate(value: str, max_len: int) -> str:
    return value if len(value) <= max_len else value[: max_len - 3].rstrip() + "..."


def _parse_llm_json(raw: str) -> dict:
    clean = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    clean = re.sub(r"```\s*$", "", clean, flags=re.MULTILINE).strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"LLM returned invalid JSON (first 300 chars): {raw[:300]}")


def _write_trace(filename: str, data: dict) -> None:
    try:
        _TRACE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_TRACE_DIR / filename, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning("Could not write agent-generation trace: %s", exc)


async def _read_llm_config_from_db(db: AsyncSession) -> dict:
    keys = ["LLM_PROVIDER", "OLLAMA_HOST", "OLLAMA_MODEL", "OPENAI_MODEL", "OPENAI_BASE_URL"]
    result = await db.execute(select(PlatformCapability).where(PlatformCapability.key.in_(keys)))
    rows = {row.key: row.value for row in result.scalars().all()}

    ollama_secret = await db.get(PlatformSecret, "OLLAMA_API_KEY")
    openai_secret = await db.get(PlatformSecret, "OPENAI_API_KEY")

    def _decrypt(secret: PlatformSecret | None) -> str | None:
        if secret is None:
            return None
        try:
            return decrypt_value(secret.value)
        except Exception:
            return None

    return {
        "provider": rows.get("LLM_PROVIDER"),
        "ollama_host": rows.get("OLLAMA_HOST"),
        "ollama_model": rows.get("OLLAMA_MODEL"),
        "openai_model": rows.get("OPENAI_MODEL"),
        "openai_base_url": rows.get("OPENAI_BASE_URL"),
        "ollama_api_key": _decrypt(ollama_secret),
        "openai_api_key": _decrypt(openai_secret),
    }


def build_generation_prompt(
    request: AgentGenerationRequest,
    catalog: list[McpCatalogSummary],
    context: AgentGenerationContext,
) -> str:
    serialized_mcps = [
        {
            "id": m.id,
            "name": m.name,
            "purpose": _truncate(m.purpose or "", 160),
            "effect_type": m.effect_type,
            "criticality": m.criticality,
            "approval_required": m.approval_required,
            "obot_state": m.obot_state,
            "orkestra_state": m.orkestra_state,
        }
        for m in catalog
    ]
    mcps_for_prompt = serialized_mcps
    mcp_omitted = 0
    if len(serialized_mcps) > 50:
        ranked = _rank_mcps(request, catalog)
        top_ids = [r.mcp.id for r in ranked[:30]]
        mcps_for_prompt = [m for m in serialized_mcps if m["id"] in set(top_ids)]
        mcp_omitted = len(serialized_mcps) - len(mcps_for_prompt)

    payload = {
        "request": {
            "intent": request.intent,
            "use_case": request.use_case,
            "target_workflow": request.target_workflow,
            "criticality_target": request.criticality_target,
            "preferred_family": request.preferred_family,
            "preferred_skill_ids": request.preferred_skill_ids or [],
            "preferred_output_style": request.preferred_output_style,
            "preferred_mcp_scope": request.preferred_mcp_scope,
            "constraints": request.constraints,
            "owner": request.owner,
        },
        "context": {
            "mcp_catalog": mcps_for_prompt,
            "mcp_catalog_omitted_count": mcp_omitted,
            "families": context.families,
            "skills": context.skills,
            "similar_agents": context.similar_agents[:5],
        },
    }
    return (
        "You generate a governed Orkestra agent draft. "
        "Return strict JSON only with no markdown, comments, or explanation. "
        "Output must conform to GeneratedAgentDraft fields.\n\n"
        f"INPUT:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "- Use only existing family_id and skill_ids from context where possible.\n"
        "- Use allowed_mcps from context.mcp_catalog IDs only.\n"
        "- Fill mcp_rationale for selected MCP IDs.\n"
        "- Keep limitations non-empty.\n"
        "- Keep status as 'draft'."
    )


async def _call_llm(prompt: str, db: AsyncSession) -> str:
    if not is_agentscope_available():
        raise ValueError("AgentScope unavailable")
    llm_config = await _read_llm_config_from_db(db)
    model = get_chat_model(config=llm_config)
    if model is None:
        raise ValueError("LLM model could not be created")

    response = await asyncio.wait_for(
        model(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the JSON draft now."},
            ]
        ),
        timeout=_LLM_TIMEOUT_SECONDS,
    )
    content = response.get("content") or []
    text = "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )
    return text or str(response)


def _normalize_llm_draft(
    draft: GeneratedAgentDraft,
    request: AgentGenerationRequest,
    catalog: list[McpCatalogSummary],
    context: AgentGenerationContext,
) -> GeneratedAgentDraft:
    active_family_ids = [f.get("id") for f in context.families if f.get("status") == "active" and f.get("id")]
    all_family_ids = [f.get("id") for f in context.families if f.get("id")]
    allowed_families = set(active_family_ids or all_family_ids)

    if draft.family_id not in allowed_families:
        if request.preferred_family in allowed_families:
            draft.family_id = request.preferred_family  # type: ignore[assignment]
        elif allowed_families:
            draft.family_id = sorted(allowed_families)[0]  # type: ignore[assignment]

    active_skill_ids = {
        s.get("skill_id")
        for s in context.skills
        if s.get("skill_id") and s.get("status") in (None, "active")
    }
    compatible_skill_ids = {
        s.get("skill_id")
        for s in context.skills
        if s.get("skill_id")
        and s.get("status") in (None, "active")
        and (not s.get("allowed_families") or draft.family_id in (s.get("allowed_families") or []))
    }

    incoming_skills = list(dict.fromkeys(draft.skill_ids or []))
    normalized_skills = [sid for sid in incoming_skills if sid in active_skill_ids and sid in compatible_skill_ids]
    if not normalized_skills and request.preferred_skill_ids:
        normalized_skills = [sid for sid in request.preferred_skill_ids if sid in compatible_skill_ids]
    draft.skill_ids = normalized_skills

    allowed_mcp_ids = {m.id for m in catalog}
    normalized_mcps = [mid for mid in dict.fromkeys(draft.allowed_mcps or []) if mid in allowed_mcp_ids]
    draft.allowed_mcps = normalized_mcps
    draft.mcp_rationale = {k: v for k, v in (draft.mcp_rationale or {}).items() if k in set(normalized_mcps)}

    if not draft.limitations:
        draft.limitations = ["Validate evidence before final recommendation."]
    draft.status = "draft"
    return draft


def _infer_family(req: AgentGenerationRequest) -> str:
    if req.preferred_family:
        return req.preferred_family.strip().lower()

    intent = req.intent.lower()
    if "review" in intent or "compliance" in intent or "conform" in intent:
        return "reviewer"
    if "risk" in intent or "control" in intent or "policy" in intent:
        return "monitor"
    if "plan" in intent or "route" in intent or "orchestr" in intent:
        return "planner"
    if "enrich" in intent or "collect" in intent or "find" in intent:
        return "analyst"
    return "analyst"


def _infer_criticality(req: AgentGenerationRequest) -> str:
    if req.criticality_target:
        return req.criticality_target.strip().lower()
    low_intent = req.intent.lower()
    if any(w in low_intent for w in ("compliance", "legal", "approval", "sensitive")):
        return "high"
    return "medium"


def _infer_cost_profile(req: AgentGenerationRequest, mcp_count: int) -> str:
    if mcp_count >= 5:
        return "high"
    if req.preferred_output_style and "detailed" in req.preferred_output_style.lower():
        return "high"
    if mcp_count <= 2:
        return "low"
    return "medium"


def _rank_mcps(req: AgentGenerationRequest, catalog: list[McpCatalogSummary]) -> list[_RankedMcp]:
    intent_keywords = _keywords(" ".join(filter(None, [req.intent, req.use_case, req.constraints])))
    ranked: list[_RankedMcp] = []

    for mcp in catalog:
        mcp_text = " ".join(
            [
                mcp.id,
                mcp.name,
                mcp.purpose,
                mcp.effect_type,
                mcp.criticality,
            ]
        )
        mcp_keywords = _keywords(mcp_text)
        overlap = len(intent_keywords & mcp_keywords)
        score = overlap * 4

        if mcp.orkestra_state in {"enabled", "restricted"}:
            score += 3
        if mcp.obot_state == "active":
            score += 2
        if req.preferred_mcp_scope and req.preferred_mcp_scope.lower() in mcp_text.lower():
            score += 3
        if "search" in req.intent.lower() and mcp.effect_type == "search":
            score += 1
        if "lookup" in req.intent.lower() and mcp.effect_type in {"read", "search"}:
            score += 1

        reason_parts = []
        if overlap > 0:
            reason_parts.append(f"keyword overlap ({overlap})")
        if mcp.orkestra_state in {"enabled", "restricted"}:
            reason_parts.append("allowed in Orkestra")
        if mcp.obot_state == "active":
            reason_parts.append("active on Obot")
        if mcp.effect_type in {"read", "search"} and "lookup" in req.intent.lower():
            reason_parts.append("effect type fits lookup intent")
        reason = ", ".join(reason_parts) if reason_parts else "fallback relevance"

        ranked.append(_RankedMcp(mcp=mcp, score=score, reason=reason))

    ranked.sort(key=lambda r: (-r.score, r.mcp.name.lower()))
    return ranked


def _suggest_missing_mcps(req: AgentGenerationRequest, selected: list[str]) -> list[str]:
    text = req.intent.lower()
    suggestions: list[str] = []
    if "societe" in text or "siren" in text or "entreprise" in text:
        if not any("sirene" in m for m in selected):
            suggestions.append("company_registry_enrichment_mcp")
    if "marche" in text or "procurement" in text:
        if not any("boamp" in m for m in selected):
            suggestions.append("public_procurement_alerts_mcp")
    if "web" in text or "site" in text:
        if not any("web" in m for m in selected):
            suggestions.append("trusted_web_crawl_mcp")
    return suggestions


def _heuristic_generate_agent_draft(
    request: AgentGenerationRequest,
    catalog: list[McpCatalogSummary],
) -> GeneratedAgentDraft:
    family = _infer_family(request)
    criticality = _infer_criticality(request)

    ranked = _rank_mcps(request, catalog)
    allowed_ranked = [r for r in ranked if r.mcp.orkestra_state in {"enabled", "restricted"}]
    selected_ranked = [r for r in allowed_ranked if r.score > 0][:5]
    if not selected_ranked:
        selected_ranked = allowed_ranked[:2]

    allowed_mcps = [r.mcp.id for r in selected_ranked]
    mcp_rationale = {r.mcp.id: r.reason for r in selected_ranked}

    base_name = request.use_case or request.intent.split(".")[0][:64]
    name = base_name.strip().capitalize() if base_name else "Generated Agent"
    agent_id = _slugify(name)
    cost_profile = _infer_cost_profile(request, len(allowed_mcps))

    workflow_hint = request.target_workflow.strip() if request.target_workflow else ""
    selection_hints: dict[str, str | list[str] | bool] = {
        "routing_keywords": sorted(_keywords(request.intent))[:12],
        "requires_grounded_evidence": True,
    }
    if workflow_hint:
        selection_hints["workflow_ids"] = [workflow_hint]

    purpose = request.intent.strip()
    description = (
        f"Specialized agent generated from user intent. Focused on: {purpose}. "
        "Constrained by explicit MCP allowlist and governance limitations."
    )

    limitations = [
        "Do not execute actions outside allowed MCP list.",
        "Escalate when confidence is low or evidence is contradictory.",
        "Never claim legal certainty without citing collected evidence.",
    ]
    if request.constraints:
        limitations.append(f"User constraint: {request.constraints.strip()}")

    suggested_missing = _suggest_missing_mcps(request, allowed_mcps)
    forbidden_effects = ["act", "write"] if criticality in {"high", "critical"} else ["act"]

    prompt_content = (
        "You are a governed Orkestra sub-agent.\n"
        f"Mission: {purpose}\n"
        f"Allowed MCP IDs: {', '.join(allowed_mcps) if allowed_mcps else 'none'}\n"
        "Execution rules:\n"
        "- Ground every conclusion on retrieved evidence.\n"
        "- Explicitly report uncertainty and missing data.\n"
        "- Respect limitations and forbidden effects.\n"
    )

    skills_content = (
        "# Skills File\n"
        f"- domain: {request.use_case or 'general'}\n"
        f"- family: {family}\n"
        f"- preferred_output_style: {request.preferred_output_style or 'concise_structured'}\n"
        f"- target_workflow: {workflow_hint or 'n/a'}\n"
        "- operating_mode: evidence_first\n"
    )

    skills = [
        "context_gap_detection",
        "document_analysis",
        "source_comparison",
    ]

    return GeneratedAgentDraft(
        agent_id=agent_id,
        name=name,
        family=family,
        purpose=purpose,
        description=description,
        skills=skills,
        selection_hints=selection_hints,
        allowed_mcps=allowed_mcps,
        forbidden_effects=forbidden_effects,
        input_contract_ref=f"contracts/{agent_id}.input.v1",
        output_contract_ref=f"contracts/{agent_id}.output.v1",
        criticality=criticality,
        cost_profile=cost_profile,
        limitations=limitations,
        prompt_content=prompt_content,
        skills_content=skills_content,
        owner=request.owner or "agent-registry",
        version="1.0.0",
        status="draft",
        suggested_missing_mcps=suggested_missing,
        mcp_rationale=mcp_rationale,
    )


def generate_agent_draft(
    request: AgentGenerationRequest,
    catalog: list[McpCatalogSummary],
) -> GeneratedAgentDraft:
    """Backward-compatible heuristic generator."""
    return _heuristic_generate_agent_draft(request, catalog)


async def generate_agent_draft_with_fallback(
    db: AsyncSession,
    request: AgentGenerationRequest,
    catalog: list[McpCatalogSummary],
    context: AgentGenerationContext,
) -> tuple[GeneratedAgentDraft, str]:
    timestamp = datetime.now(timezone.utc)
    trace_name = f"{timestamp.strftime('%Y-%m-%dT%H-%M-%S')}_{_slugify((request.use_case or request.intent)[:80])}.json"
    trace = {
        "timestamp": timestamp.isoformat(),
        "request": request.model_dump(),
        "context": {
            "mcp_catalog_count": len(catalog),
            "families_count": len(context.families),
            "skills_count": len(context.skills),
            "similar_agents_count": len(context.similar_agents),
            "families": context.families,
            "skills": context.skills,
            "similar_agents": context.similar_agents[:5],
        },
        "system_prompt": None,
        "llm_raw_response": None,
        "llm_parsed": None,
        "fallback_reason": None,
        "source": None,
        "duration_ms": None,
    }
    started = time.monotonic()

    try:
        prompt = build_generation_prompt(request, catalog, context)
        trace["system_prompt"] = prompt
        raw = await _call_llm(prompt, db)
        trace["llm_raw_response"] = raw
        parsed = _parse_llm_json(raw)
        trace["llm_parsed"] = parsed

        validated = GeneratedAgentDraft.model_validate(parsed)
        normalized = _normalize_llm_draft(validated, request, catalog, context)
        trace["source"] = "llm"
        trace["duration_ms"] = round((time.monotonic() - started) * 1000)
        _write_trace(trace_name, trace)
        return normalized, "llm"
    except Exception as exc:
        trace["fallback_reason"] = str(exc)
        fallback = _heuristic_generate_agent_draft(request, catalog)
        trace["llm_parsed"] = fallback.model_dump()
        trace["source"] = "heuristic_template"
        trace["duration_ms"] = round((time.monotonic() - started) * 1000)
        _write_trace(trace_name, trace)
        return fallback, "heuristic_template"
