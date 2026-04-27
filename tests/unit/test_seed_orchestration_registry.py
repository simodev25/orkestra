"""Regression tests for orchestration family/skill seed completeness."""

from __future__ import annotations

import json
from pathlib import Path


def _load_seed_file(filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "app" / "config" / filename
    return json.loads(path.read_text(encoding="utf-8"))


def test_orchestration_family_exists_in_families_seed() -> None:
    payload = _load_seed_file("families.seed.json")
    family_ids = {entry["family_id"] for entry in payload.get("families", [])}

    assert "orchestration" in family_ids


def test_orchestration_skills_exist_in_skills_seed_and_allow_family() -> None:
    payload = _load_seed_file("skills.seed.json")
    by_id = {entry["skill_id"]: entry for entry in payload.get("skills", [])}

    for skill_id in ("sequential_routing", "context_propagation"):
        assert skill_id in by_id
        assert "orchestration" in by_id[skill_id].get("allowed_families", [])
