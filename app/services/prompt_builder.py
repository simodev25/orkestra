"""Prompt builder — assembles multi-layer system prompts for agents."""

from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import FamilyDefinition, AgentSkill
from app.models.skill import SkillDefinition
from app.models.registry import AgentDefinition

logger = logging.getLogger("orkestra.prompt_builder")

_CODE_EXECUTION_GUIDE = """\
You have `execute_python_code`. Use it when you need a computed, deterministic answer.

Typical uses: calculations, formatting, data extraction, HTTP API calls.

Rules:
- `print()` every value you need — only stdout comes back to you.
- Import libraries at the top; use try/except and print errors.
- For HTTP: `import httpx; r = httpx.get(url, params={...}, timeout=15); r.raise_for_status(); print(r.json())`
- Print ONLY the fields you need from API responses — never dump the full JSON object.
- One focused task per snippet. Each call is independent.\
"""


async def build_agent_prompt(
    db: AsyncSession,
    agent: AgentDefinition,
    runtime_context: dict | None = None,
) -> str:
    """Assemble the multi-layer system prompt for an agent.

    Layers (in order):
    1. Family rules — family.default_system_rules
    2. Skill rules — skills behavior_templates + output_guidelines
    3. Soul rules — agent.soul_content (optional)
    4. Agent mission — purpose + description + prompt_content
    5. Output expectations — family.default_output_expectations
    6. Contract rules — input/output contract refs
    7. Runtime context — criticality, allowed tools, forbidden effects, limitations
    """
    sections: list[str] = []

    # Layer 1 — Family rules
    family = await db.get(FamilyDefinition, agent.family_id)
    if family and family.default_system_rules:
        sections.append(_format_section(
            "FAMILY RULES",
            "\n".join(f"- {rule}" for rule in family.default_system_rules)
        ))

    # Layer 2 — Skill rules
    skill_result = await db.execute(
        select(SkillDefinition)
        .join(AgentSkill, AgentSkill.skill_id == SkillDefinition.id)
        .where(AgentSkill.agent_id == agent.id)
        .order_by(SkillDefinition.label)
    )
    skills = list(skill_result.scalars().all())
    if skills:
        skill_parts = []
        for skill in skills:
            lines = [f"### {skill.label}"]
            if skill.behavior_templates:
                lines.append("Behavior:")
                lines.extend(f"- {t}" for t in skill.behavior_templates)
            if skill.output_guidelines:
                lines.append("Output guidelines:")
                lines.extend(f"- {g}" for g in skill.output_guidelines)
            skill_parts.append("\n".join(lines))
        sections.append(_format_section("SKILL RULES", "\n\n".join(skill_parts)))

    # Layer 3 — Soul rules (optional)
    if agent.soul_content:
        sections.append(_format_section("SOUL", agent.soul_content))

    # Layer 4 — Agent mission
    mission_parts = [f"You are {agent.name}."]
    if agent.purpose:
        mission_parts.append(f"Mission: {agent.purpose}")
    if agent.description:
        mission_parts.append(agent.description)
    if agent.prompt_content:
        mission_parts.append(agent.prompt_content)
    sections.append(_format_section("AGENT MISSION", "\n\n".join(mission_parts)))

    # Layer 4.5 — Code execution guide (injected only when opted in)
    if getattr(agent, "allow_code_execution", False):
        sections.append(_format_section("CODE EXECUTION", _CODE_EXECUTION_GUIDE))

    # Layer 5 — Output expectations
    if family and family.default_output_expectations:
        sections.append(_format_section(
            "OUTPUT EXPECTATIONS",
            "\n".join(f"- {exp}" for exp in family.default_output_expectations)
        ))

    # Layer 6 — Contract rules
    contract_parts = []
    if agent.input_contract_ref:
        contract_parts.append(f"Input contract: {agent.input_contract_ref}")
    if agent.output_contract_ref:
        contract_parts.append(f"Output contract: {agent.output_contract_ref}")
    if contract_parts:
        sections.append(_format_section("CONTRACTS", "\n".join(contract_parts)))

    # Layer 7 — Runtime context
    runtime_parts = []

    # From agent definition
    if agent.criticality:
        runtime_parts.append(f"Criticality: {agent.criticality}")

    # Merge forbidden effects: family defaults + agent overrides
    forbidden = set()
    if family and family.default_forbidden_effects:
        forbidden.update(family.default_forbidden_effects)
    if agent.forbidden_effects:
        forbidden.update(agent.forbidden_effects)
    if forbidden:
        runtime_parts.append(f"Forbidden effects: {', '.join(sorted(forbidden))}")

    if agent.allowed_mcps:
        runtime_parts.append(f"Allowed tools: {', '.join(agent.allowed_mcps)}")

    if agent.limitations:
        runtime_parts.append("Limitations:")
        runtime_parts.extend(f"- {lim}" for lim in agent.limitations)

    # From runtime context dict (passed at invocation time)
    if runtime_context:
        if runtime_context.get("use_case"):
            runtime_parts.append(f"Use case: {runtime_context['use_case']}")
        if runtime_context.get("run_criticality"):
            runtime_parts.append(f"Run criticality: {runtime_context['run_criticality']}")
        # Extensible: add more runtime keys as needed

    if runtime_parts:
        sections.append(_format_section("RUNTIME CONTEXT", "\n".join(runtime_parts)))

    return "\n\n".join(sections)


def _format_section(title: str, content: str) -> str:
    """Format a prompt section with a clear header."""
    return f"## {title}\n\n{content}"
