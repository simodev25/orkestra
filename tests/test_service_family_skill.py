# tests/test_service_family_skill.py
"""Tests unitaires pour family_service et skill_service."""
import pytest

from app.schemas.family import FamilyCreate, FamilyUpdate
from app.schemas.skill import SkillCreate, SkillUpdate
from app.services import family_service, skill_service
from app.models.enums import FamilyStatus


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_family(db_session, family_id: str = "fam_base", label: str = "Base Family"):
    data = FamilyCreate(id=family_id, label=label)
    fam = await family_service.create_family(db_session, data)
    await db_session.commit()
    return fam


# ═══════════════════════════════ family_service ════════════════════════════════

async def test_create_family_basic(db_session):
    data = FamilyCreate(id="fam1", label="Family One")
    fam = await family_service.create_family(db_session, data)
    assert fam.id == "fam1"
    assert fam.label == "Family One"
    assert fam.status == FamilyStatus.active


async def test_create_family_with_rules(db_session):
    data = FamilyCreate(
        id="fam2",
        label="Family Two",
        default_system_rules=["rule1", "rule2"],
        default_forbidden_effects=["write"],
    )
    fam = await family_service.create_family(db_session, data)
    assert fam.default_system_rules == ["rule1", "rule2"]
    assert fam.default_forbidden_effects == ["write"]


async def test_create_family_duplicate_raises(db_session):
    await _create_family(db_session, "fam_dup")
    with pytest.raises(ValueError, match="already exists"):
        await family_service.create_family(db_session, FamilyCreate(id="fam_dup", label="Dup"))


async def test_get_family_returns_family(db_session):
    await _create_family(db_session, "fam3", "F3")

    fam = await family_service.get_family(db_session, "fam3")
    assert fam is not None
    assert fam.id == "fam3"


async def test_get_family_nonexistent_returns_none(db_session):
    fam = await family_service.get_family(db_session, "does_not_exist")
    assert fam is None


async def test_list_families_returns_all(db_session):
    await _create_family(db_session, "fa", "FA")
    await _create_family(db_session, "fb", "FB")

    items, total = await family_service.list_families(db_session)
    assert total >= 2
    ids = [f.id for f in items]
    assert "fa" in ids
    assert "fb" in ids


async def test_list_families_excludes_archived_by_default(db_session):
    await _create_family(db_session, "fam_active", "Active")
    await _create_family(db_session, "fam_arc_list", "Archived")
    await family_service.archive_family(db_session, "fam_arc_list")
    await db_session.commit()

    items, total = await family_service.list_families(db_session)
    ids = [f.id for f in items]
    assert "fam_active" in ids
    assert "fam_arc_list" not in ids


async def test_list_families_includes_archived_when_asked(db_session):
    await _create_family(db_session, "fam_arc_inc", "Arc Inc")
    await family_service.archive_family(db_session, "fam_arc_inc")
    await db_session.commit()

    items, total = await family_service.list_families(db_session, include_archived=True)
    ids = [f.id for f in items]
    assert "fam_arc_inc" in ids


async def test_update_family_label(db_session):
    await _create_family(db_session, "fam_upd", "Old Label")

    updated = await family_service.update_family(
        db_session, "fam_upd", FamilyUpdate(label="New Label")
    )
    assert updated.label == "New Label"


async def test_update_family_bumps_version(db_session):
    await _create_family(db_session, "fam_ver", "Ver")

    updated = await family_service.update_family(
        db_session, "fam_ver", FamilyUpdate(label="Ver Updated")
    )
    # version should be bumped from 1.0.0 to 1.0.1
    assert updated.version != "1.0.0"


async def test_update_family_nonexistent_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        await family_service.update_family(
            db_session, "nonexistent", FamilyUpdate(label="x")
        )


async def test_archive_family_changes_status(db_session):
    await _create_family(db_session, "fam_arc", "Arc")

    archived = await family_service.archive_family(db_session, "fam_arc")
    assert archived.status == "archived"


async def test_archive_family_nonexistent_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        await family_service.archive_family(db_session, "ghost_family")


async def test_is_family_active_returns_true(db_session):
    await _create_family(db_session, "fam_act", "Act")

    result = await family_service.is_family_active(db_session, "fam_act")
    assert result is True


async def test_is_family_active_returns_false_after_archive(db_session):
    await _create_family(db_session, "fam_inact", "Inact")
    await family_service.archive_family(db_session, "fam_inact")
    await db_session.commit()

    result = await family_service.is_family_active(db_session, "fam_inact")
    assert result is False


async def test_is_family_active_nonexistent_returns_false(db_session):
    result = await family_service.is_family_active(db_session, "ghost")
    assert result is False


async def test_get_family_detail_includes_skills(db_session):
    await _create_family(db_session, "fam_det", "Det")

    detail = await family_service.get_family_detail(db_session, "fam_det")
    assert detail is not None
    assert "skills" in detail
    assert isinstance(detail["skills"], list)
    assert detail["agent_count"] == 0


async def test_get_family_detail_nonexistent_returns_none(db_session):
    detail = await family_service.get_family_detail(db_session, "ghost_family")
    assert detail is None


async def test_get_family_history_empty_initially(db_session):
    await _create_family(db_session, "fam_hist", "Hist")

    history = await family_service.get_family_history(db_session, "fam_hist")
    assert isinstance(history, list)
    assert len(history) == 0


async def test_get_family_history_has_entry_after_update(db_session):
    await _create_family(db_session, "fam_hist2", "Hist2")

    await family_service.update_family(
        db_session, "fam_hist2", FamilyUpdate(label="Hist2 Updated")
    )
    await db_session.commit()

    history = await family_service.get_family_history(db_session, "fam_hist2")
    assert len(history) == 1


async def test_delete_family_hard_deletes_when_unreferenced(db_session):
    await _create_family(db_session, "fam_del", "Del")

    result = await family_service.delete_family(db_session, "fam_del")
    await db_session.commit()

    # returns None on hard delete
    assert result is None
    fam = await family_service.get_family(db_session, "fam_del")
    assert fam is None


async def test_delete_family_nonexistent_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        await family_service.delete_family(db_session, "ghost_fam")


# ═══════════════════════════════ skill_service ════════════════════════════════
# skill_service functions return dict (via _skill_to_dict), not ORM objects.

async def test_create_skill_basic(db_session):
    data = SkillCreate(id="skill_test", label="Test Skill", category="analysis")
    skill = await skill_service.create_skill(db_session, data)
    assert skill["skill_id"] == "skill_test"
    assert skill["label"] == "Test Skill"
    assert skill["category"] == "analysis"


async def test_create_skill_duplicate_raises(db_session):
    data = SkillCreate(id="sk_dup", label="Dup Skill", category="analysis")
    await skill_service.create_skill(db_session, data)
    await db_session.commit()

    with pytest.raises(ValueError, match="already exists"):
        await skill_service.create_skill(db_session, SkillCreate(id="sk_dup", label="Dup2", category="analysis"))


async def test_create_skill_with_allowed_families(db_session):
    await _create_family(db_session, "fam_sk", "Fam Sk")

    data = SkillCreate(
        id="sk_with_fam",
        label="Skill With Family",
        category="analysis",
        allowed_families=["fam_sk"],
    )
    skill = await skill_service.create_skill(db_session, data)
    assert "fam_sk" in skill["allowed_families"]


async def test_create_skill_invalid_family_raises(db_session):
    data = SkillCreate(
        id="sk_bad_fam",
        label="Bad Fam",
        category="analysis",
        allowed_families=["nonexistent_family"],
    )
    with pytest.raises(ValueError, match="not found"):
        await skill_service.create_skill(db_session, data)


async def test_get_skill_returns_dict(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_get", label="Get Skill", category="analysis"))
    await db_session.commit()

    skill = await skill_service.get_skill(db_session, "sk_get")
    assert skill is not None
    assert skill["skill_id"] == "sk_get"
    assert skill["label"] == "Get Skill"


async def test_get_skill_nonexistent_returns_none(db_session):
    skill = await skill_service.get_skill(db_session, "nonexistent_skill")
    assert skill is None


async def test_list_skills_returns_all(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk1", label="S1", category="analysis"))
    await skill_service.create_skill(db_session, SkillCreate(id="sk2", label="S2", category="synthesis"))
    await db_session.commit()

    skills, total = await skill_service.list_skills(db_session)
    assert total >= 2
    skill_ids = [s["skill_id"] for s in skills]
    assert "sk1" in skill_ids
    assert "sk2" in skill_ids


async def test_list_skills_excludes_archived_by_default(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_active", label="Active", category="analysis"))
    await skill_service.create_skill(db_session, SkillCreate(id="sk_arc_lst", label="Archived", category="analysis"))
    await db_session.commit()
    await skill_service.archive_skill(db_session, "sk_arc_lst")
    await db_session.commit()

    skills, total = await skill_service.list_skills(db_session)
    skill_ids = [s["skill_id"] for s in skills]
    assert "sk_active" in skill_ids
    assert "sk_arc_lst" not in skill_ids


async def test_update_skill_label(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_upd", label="Old", category="analysis"))
    await db_session.commit()

    updated = await skill_service.update_skill(db_session, "sk_upd", SkillUpdate(label="Updated"))
    assert updated["label"] == "Updated"


async def test_update_skill_bumps_version(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_ver", label="Ver", category="analysis"))
    await db_session.commit()

    updated = await skill_service.update_skill(db_session, "sk_ver", SkillUpdate(label="Ver Updated"))
    assert updated["version"] != "1.0.0"


async def test_update_skill_nonexistent_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        await skill_service.update_skill(db_session, "ghost_skill", SkillUpdate(label="x"))


async def test_archive_skill_changes_status(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_arc", label="Arc Skill", category="analysis"))
    await db_session.commit()

    archived = await skill_service.archive_skill(db_session, "sk_arc")
    assert archived["status"] == "archived"


async def test_archive_skill_nonexistent_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        await skill_service.archive_skill(db_session, "ghost_skill")


async def test_delete_skill_hard_deletes_when_unreferenced(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_del", label="Del", category="analysis"))
    await db_session.commit()

    result = await skill_service.delete_skill(db_session, "sk_del")
    await db_session.commit()

    # returns None on hard delete
    assert result is None
    skill = await skill_service.get_skill(db_session, "sk_del")
    assert skill is None


async def test_delete_skill_nonexistent_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        await skill_service.delete_skill(db_session, "ghost_skill")


async def test_get_skill_history_empty_initially(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_hist", label="Hist Skill", category="analysis"))
    await db_session.commit()

    history = await skill_service.get_skill_history(db_session, "sk_hist")
    assert isinstance(history, list)
    assert len(history) == 0


async def test_get_skill_history_has_entry_after_update(db_session):
    await skill_service.create_skill(db_session, SkillCreate(id="sk_hist2", label="Hist2", category="analysis"))
    await db_session.commit()

    await skill_service.update_skill(db_session, "sk_hist2", SkillUpdate(label="Hist2 Updated"))
    await db_session.commit()

    history = await skill_service.get_skill_history(db_session, "sk_hist2")
    assert len(history) == 1


async def test_get_skills_for_family_returns_skills_in_family(db_session):
    await _create_family(db_session, "fam_for_sk", "Fam For Sk")

    await skill_service.create_skill(db_session, SkillCreate(
        id="sk_in_fam",
        label="In Family",
        category="analysis",
        allowed_families=["fam_for_sk"],
    ))
    await skill_service.create_skill(db_session, SkillCreate(
        id="sk_not_in_fam",
        label="Not In Family",
        category="analysis",
    ))
    await db_session.commit()

    skills = await skill_service.get_skills_for_family(db_session, "fam_for_sk")
    skill_ids = [s["skill_id"] for s in skills]
    assert "sk_in_fam" in skill_ids
    assert "sk_not_in_fam" not in skill_ids


async def test_resolve_skills_returns_refs_and_unresolved(db_session):
    await skill_service.create_skill(db_session, SkillCreate(
        id="sk_resolve",
        label="Resolve Me",
        category="analysis",
        behavior_templates=["behave well"],
        output_guidelines=["be clear"],
    ))
    await db_session.commit()

    resolved, unresolved = await skill_service.resolve_skills(db_session, ["sk_resolve", "ghost"])
    assert len(resolved) == 1
    assert resolved[0].skill_id == "sk_resolve"
    assert "ghost" in unresolved
