"""Seed service — idempotent bootstrap from JSON files into DB."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import FamilyDefinition, SkillFamily
from app.models.skill import SkillDefinition

logger = logging.getLogger("orkestra.seed")

CONFIG_DIR = Path(__file__).parent.parent / "config"


async def seed_all(db: AsyncSession) -> None:
    """Run the full idempotent seed: families first, then skills."""
    f_created, f_updated = await _seed_families(db)
    s_created, s_updated = await _seed_skills(db)
    await db.commit()
    logger.info(
        f"Seed complete — families: {f_created} created, {f_updated} updated | "
        f"skills: {s_created} created, {s_updated} updated"
    )


async def _seed_families(db: AsyncSession) -> tuple[int, int]:
    path = CONFIG_DIR / "families.seed.json"
    if not path.exists():
        logger.warning(f"families.seed.json not found at {path}, skipping family seed")
        return 0, 0

    data = json.loads(path.read_text(encoding="utf-8"))
    created, updated = 0, 0

    for entry in data.get("families", []):
        fid = entry["family_id"]
        existing = await db.get(FamilyDefinition, fid)
        if existing:
            existing.label = entry["label"]
            existing.description = entry.get("description")
            existing.default_system_rules = entry.get("default_system_rules", [])
            existing.default_forbidden_effects = entry.get("default_forbidden_effects", [])
            existing.default_output_expectations = entry.get("default_output_expectations", [])
            existing.version = entry.get("version", "1.0.0")
            existing.status = entry.get("status", "active")
            existing.owner = entry.get("owner")
            updated += 1
        else:
            db.add(FamilyDefinition(
                id=fid,
                label=entry["label"],
                description=entry.get("description"),
                default_system_rules=entry.get("default_system_rules", []),
                default_forbidden_effects=entry.get("default_forbidden_effects", []),
                default_output_expectations=entry.get("default_output_expectations", []),
                version=entry.get("version", "1.0.0"),
                status=entry.get("status", "active"),
                owner=entry.get("owner"),
            ))
            created += 1

    await db.flush()
    return created, updated


async def _seed_skills(db: AsyncSession) -> tuple[int, int]:
    path = CONFIG_DIR / "skills.seed.json"
    if not path.exists():
        logger.warning(f"skills.seed.json not found at {path}, skipping skill seed")
        return 0, 0

    data = json.loads(path.read_text(encoding="utf-8"))
    created, updated = 0, 0

    for entry in data.get("skills", []):
        sid = entry["skill_id"]
        existing = await db.get(SkillDefinition, sid)
        if existing:
            existing.label = entry["label"]
            existing.category = entry["category"]
            existing.description = entry.get("description")
            existing.behavior_templates = entry.get("behavior_templates", [])
            existing.output_guidelines = entry.get("output_guidelines", [])
            existing.version = entry.get("version", "1.0.0")
            existing.status = entry.get("status", "active")
            existing.owner = entry.get("owner")
            updated += 1
        else:
            db.add(SkillDefinition(
                id=sid,
                label=entry["label"],
                category=entry["category"],
                description=entry.get("description"),
                behavior_templates=entry.get("behavior_templates", []),
                output_guidelines=entry.get("output_guidelines", []),
                version=entry.get("version", "1.0.0"),
                status=entry.get("status", "active"),
                owner=entry.get("owner"),
            ))
            created += 1

        await db.flush()

        # Sync SkillFamily entries
        allowed = set(entry.get("allowed_families", []))
        existing_sf = await db.execute(
            select(SkillFamily).where(SkillFamily.skill_id == sid)
        )
        current_families = {sf.family_id for sf in existing_sf.scalars().all()}

        to_remove = current_families - allowed
        if to_remove:
            await db.execute(
                delete(SkillFamily).where(
                    SkillFamily.skill_id == sid,
                    SkillFamily.family_id.in_(to_remove),
                )
            )

        to_add = allowed - current_families
        for fam_id in to_add:
            db.add(SkillFamily(skill_id=sid, family_id=fam_id))

    await db.flush()
    return created, updated
