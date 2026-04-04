"""Structured draft generation for Agent Registry."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.agent import (
    AgentGenerationRequest,
    GeneratedAgentDraft,
    McpCatalogSummary,
)


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


def generate_agent_draft(
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
        "entity_resolution",
        "evidence_collection",
        "source_cross_check",
        "structured_summary",
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
