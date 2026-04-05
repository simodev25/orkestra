"""Skill registry service — loads, validates and serves skills from skills.seed.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.schemas.skill import (
    AgentSummary,
    SkillContent,
    SkillOut,
    SkillRef,
    SkillSeedEntry,
    SkillSeedPayload,
    SkillWithAgents,
)

logger = logging.getLogger("orkestra.skills")

# In-memory registry — populated at startup from skills.seed.json
_registry: dict[str, SkillSeedEntry] = {}
_registry_loaded: bool = False


# ---------------------------------------------------------------------------
# Seed loading & validation
# ---------------------------------------------------------------------------

def _load_seed_file() -> list[SkillSeedEntry]:
    """Load and validate skills.seed.json, returning a list of SkillSeedEntry."""
    settings = get_settings()
    config_dir = Path(__file__).parent.parent / "config"
    seed_path = config_dir / "skills.seed.json"

    if not seed_path.exists():
        logger.error(f"skills.seed.json not found at {seed_path}")
        raise FileNotFoundError(f"skills.seed.json not found at {seed_path}")

    try:
        raw = seed_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error(f"Failed to read skills.seed.json: {exc}")
        raise

    try:
        payload = SkillSeedPayload.model_validate_json(raw)
    except Exception as exc:
        logger.error(f"skills.seed.json failed validation: {exc}")
        raise

    _validate_entries(payload.skills)

    logger.info(f"skills.seed.json loaded successfully — {len(payload.skills)} skill(s) validated")
    return payload.skills


def _validate_entries(entries: list[SkillSeedEntry]) -> None:
    """Validate skill entries: unique skill_ids, required non-empty fields."""
    seen_ids: set[str] = set()
    errors: list[str] = []

    for entry in entries:
        if not entry.skill_id or not entry.skill_id.strip():
            errors.append("found entry with empty or missing skill_id")
            continue
        if entry.skill_id in seen_ids:
            errors.append(f"duplicate skill_id: '{entry.skill_id}'")
        seen_ids.add(entry.skill_id)

        if not entry.label or not entry.label.strip():
            errors.append(f"skill_id '{entry.skill_id}' has empty label")
        if not entry.category or not entry.category.strip():
            errors.append(f"skill_id '{entry.skill_id}' has empty category")
        if not entry.description or not entry.description.strip():
            errors.append(f"skill_id '{entry.skill_id}' has empty description")
        if not entry.behavior_templates:
            errors.append(f"skill_id '{entry.skill_id}' has empty behavior_templates")
        if not entry.output_guidelines:
            errors.append(f"skill_id '{entry.skill_id}' has empty output_guidelines")

    if errors:
        error_msg = "; ".join(errors)
        logger.error(f"skills.seed.json validation errors: {error_msg}")
        raise ValueError(f"skills.seed.json validation errors: {error_msg}")


def load_skills() -> None:
    """Load and register all skills from skills.seed.json into the in-memory registry.

    Call this once at application startup via the lifespan hook.
    """
    global _registry
    entries = _load_seed_file()
    _registry = {entry.skill_id: entry for entry in entries}
    logger.info(f"Skill registry initialised with {len(_registry)} skill(s)")


def _ensure_loaded() -> None:
    """Lazy-load the skill registry if it hasn't been loaded yet."""
    global _registry_loaded
    if not _registry_loaded:
        try:
            load_skills()
        except Exception:
            # If loading fails (e.g., file missing in tests), registry stays empty
            pass


# ---------------------------------------------------------------------------
# Public read API
# ---------------------------------------------------------------------------

def list_skills() -> list[SkillOut]:
    """Return all registered skills as SkillOut (no agent info)."""
    _ensure_loaded()
    return [_entry_to_out(e) for e in _registry.values()]


def get_skill(skill_id: str) -> Optional[SkillOut]:
    """Return a single skill by skill_id, or None if not found."""
    _ensure_loaded()
    entry = _registry.get(skill_id)
    if not entry:
        return None
    return _entry_to_out(entry)


def resolve_skills(skill_ids: list[str]) -> tuple[list[SkillRef], list[str]]:
    """Resolve a list of skill_ids against the registry.

    Returns:
        A tuple of (resolved, unresolved) where resolved is a list of SkillRef
        and unresolved is a list of unknown skill_ids.
    """
    _ensure_loaded()
    resolved: list[SkillRef] = []
    unresolved: list[str] = []

    for sid in skill_ids:
        entry = _registry.get(sid)
        if not entry:
            unresolved.append(sid)
            logger.warning(f"Agent references unknown skill_id: '{sid}'")
            continue
        resolved.append(_entry_to_ref(entry))

    return resolved, unresolved


def build_skills_content(skill_ids: list[str]) -> str:
    """Build a JSON string describing all resolved skills.

    This is what gets stored in AgentDefinition.skills_content — it is the
    canonical aggregation of skill metadata derived from the seed.
    """
    import json

    resolved, unresolved = resolve_skills(skill_ids)
    if unresolved:
        logger.warning(f"build_skills_content called with unknown skill_ids: {unresolved}")

    content = {
        sid: {
            "description": ref.skills_content.description,
            "behavior_templates": ref.skills_content.behavior_templates,
            "output_guidelines": ref.skills_content.output_guidelines,
        }
        for sid, ref in zip([r.skill_id for r in resolved], resolved)
    }
    return json.dumps(content, indent=2)


def get_skills_with_agents(
    agent_map: dict[str, tuple[str, str]],
) -> list[SkillWithAgents]:
    """Build SkillWithAgents for every registered skill, enriching with agent data.

    Args:
        agent_map: Mapping of agent_id -> (agent_name, agent_family) for agents
                   that may reference skills.
    """
    # Invert: skill_id -> list of (agent_id, agent_name)
    skill_to_agents: dict[str, list[AgentSummary]] = {
        sid: [] for sid in _registry
    }

    for agent_id, (agent_name, agent_family) in agent_map.items():
        # Get the agent's skill list — this would be passed from the caller
        # (agent_registry_service).  We resolve names lazily here.
        pass  # Will be called with actual agent data from the service layer

    results: list[SkillWithAgents] = []
    for entry in _registry.values():
        results.append(
            SkillWithAgents(
                skill_id=entry.skill_id,
                label=entry.label,
                category=entry.category,
                description=entry.description,
                agents=[],  # Filled by caller
            )
        )
    return results


def _entry_to_out(e: SkillSeedEntry) -> SkillOut:
    return SkillOut(
        skill_id=e.skill_id,
        label=e.label,
        category=e.category,
        description=e.description,
        behavior_templates=e.behavior_templates,
        output_guidelines=e.output_guidelines,
    )


def _entry_to_ref(e: SkillSeedEntry) -> SkillRef:
    return SkillRef(
        skill_id=e.skill_id,
        label=e.label,
        category=e.category,
        skills_content=SkillContent(
            description=e.description,
            behavior_templates=e.behavior_templates,
            output_guidelines=e.output_guidelines,
        ),
    )


# ---------------------------------------------------------------------------
# Access to the raw registry (for the agent-aggregation endpoint)
# ---------------------------------------------------------------------------

def get_registry() -> dict[str, SkillSeedEntry]:
    """Return a copy of the in-memory registry (skill_id -> entry)."""
    return dict(_registry)
