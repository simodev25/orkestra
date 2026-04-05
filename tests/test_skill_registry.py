"""Tests for the skill registry system — seed loading, validation, and resolution."""

import pytest
from unittest.mock import patch, MagicMock

from app.services import skill_registry_service
from app.services.skill_registry_service import (
    _validate_entries,
    _load_seed_file,
    load_skills,
    resolve_skills,
    build_skills_content,
    get_registry,
    list_skills,
    get_skill,
)
from app.schemas.skill import SkillSeedEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the in-memory skill registry before each test."""
    skill_registry_service._registry = {}
    skill_registry_service._registry_loaded = False
    yield
    skill_registry_service._registry = {}
    skill_registry_service._registry_loaded = False


@pytest.fixture
def valid_seed_entries():
    return [
        SkillSeedEntry(
            skill_id="test_skill_a",
            label="Test Skill A",
            category="preparation",
            description="A test skill for unit testing.",
            behavior_templates=["Do the thing.", "Then do it better."],
            output_guidelines=["Be concise.", "Be accurate."],
        ),
        SkillSeedEntry(
            skill_id="test_skill_b",
            label="Test Skill B",
            category="analysis",
            description="Another test skill.",
            behavior_templates=["Analyze it."],
            output_guidelines=["Be thorough."],
        ),
    ]


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidateEntries:
    def test_valid_entries_pass(self, valid_seed_entries):
        _validate_entries(valid_seed_entries)  # should not raise

    def test_duplicate_skill_ids_raises(self, valid_seed_entries):
        dup = SkillSeedEntry(
            skill_id="test_skill_a",  # same as first entry
            label="Duplicate",
            category="preparation",
            description="Dup",
            behavior_templates=["x"],
            output_guidelines=["y"],
        )
        with pytest.raises(ValueError, match="duplicate skill_id"):
            _validate_entries([*valid_seed_entries, dup])

    def test_empty_skill_id_raises(self, valid_seed_entries):
        bad = SkillSeedEntry(
            skill_id="",
            label="Bad",
            category="preparation",
            description="Bad",
            behavior_templates=["x"],
            output_guidelines=["y"],
        )
        with pytest.raises(ValueError, match="empty"):
            _validate_entries([*valid_seed_entries, bad])

    def test_empty_behavior_templates_raises(self, valid_seed_entries):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="too_short"):
            SkillSeedEntry(
                skill_id="bad_skill",
                label="Bad Skill",
                category="preparation",
                description="Bad",
                behavior_templates=[],  # empty — rejected by Pydantic min_length=1
                output_guidelines=["y"],
            )

    def test_empty_output_guidelines_raises(self, valid_seed_entries):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="too_short"):
            SkillSeedEntry(
                skill_id="bad_skill",
                label="Bad Skill",
                category="preparation",
                description="Bad",
                behavior_templates=["x"],
                output_guidelines=[],  # empty — rejected by Pydantic min_length=1
            )


# ---------------------------------------------------------------------------
# Load from real file
# ---------------------------------------------------------------------------

class TestLoadSkillsFromFile:
    def test_load_skills_works(self):
        """Load the actual skills.seed.json and verify count."""
        skill_registry_service._registry = {}
        skill_registry_service.load_skills()
        registry = skill_registry_service.get_registry()
        assert len(registry) == 14
        assert "user_need_reformulation" in registry
        assert registry["user_need_reformulation"].label == "User Need Reformulation"

    def test_load_skills_idempotent(self):
        skill_registry_service.load_skills()
        skill_registry_service.load_skills()  # should not raise
        assert len(skill_registry_service.get_registry()) == 14


# ---------------------------------------------------------------------------
# Resolve skills
# ---------------------------------------------------------------------------

class TestResolveSkills:
    def test_resolve_known_skills(self):
        skill_registry_service.load_skills()
        resolved, unresolved = resolve_skills([
            "user_need_reformulation",
            "task_structuring",
        ])
        assert len(resolved) == 2
        assert unresolved == []
        assert resolved[0].skill_id == "user_need_reformulation"
        assert resolved[0].skills_content.description.startswith("Transform")

    def test_resolve_unknown_skills(self):
        skill_registry_service.load_skills()
        resolved, unresolved = resolve_skills(["nonexistent_skill"])
        assert resolved == []
        assert unresolved == ["nonexistent_skill"]

    def test_resolve_mixed_skills(self):
        skill_registry_service.load_skills()
        resolved, unresolved = resolve_skills([
            "user_need_reformulation",
            "unknown_skill",
        ])
        assert len(resolved) == 1
        assert resolved[0].skill_id == "user_need_reformulation"
        assert unresolved == ["unknown_skill"]


# ---------------------------------------------------------------------------
# Build skills_content
# ---------------------------------------------------------------------------

class TestBuildSkillsContent:
    def test_build_skills_content_json(self):
        skill_registry_service.load_skills()
        content = build_skills_content(["user_need_reformulation"])
        import json
        parsed = json.loads(content)
        assert "user_need_reformulation" in parsed
        assert "description" in parsed["user_need_reformulation"]
        assert "behavior_templates" in parsed["user_need_reformulation"]
        assert "output_guidelines" in parsed["user_need_reformulation"]


# ---------------------------------------------------------------------------
# list_skills / get_skill
# ---------------------------------------------------------------------------

class TestListAndGetSkills:
    def test_list_skills_returns_all(self):
        skill_registry_service.load_skills()
        skills = list_skills()
        assert len(skills) == 14
        assert all(s.skill_id for s in skills)

    def test_get_skill_returns_correct(self):
        skill_registry_service.load_skills()
        skill = get_skill("risk_identification")
        assert skill is not None
        assert skill.label == "Risk Identification"
        assert skill.category == "governance"

    def test_get_skill_unknown_returns_none(self):
        skill_registry_service.load_skills()
        assert get_skill("does_not_exist") is None
