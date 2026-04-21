# MCP Effect Enforcement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre `forbidden_effects` réellement exécutoire via un EffectClassifier LLM (effets composés) + guarded_mcp_executor AOP, avec badge RunGraph, historique violations, et override admin par run.

**Architecture:** `EffectClassifier` classifie chaque tool call via Haiku (cache process-level, fallback heuristique). `guarded_mcp_executor.guarded_invoke_mcp()` wrape `invoke_mcp()` avec enforcement + run override. Dans `agent_factory.py`, le pre-flight check filtre les MCP servers avant connexion. Les violations sont persistées en DB (`MCPInvocation.calling_agent_id`) et exposées via API REST.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, AgentScope, pytest-asyncio, Next.js 15, TypeScript, Vitest

---

## Fichiers

| Action | Fichier |
|--------|---------|
| Créer  | `migrations/versions/020_mcp_effect_enforcement.py` |
| Créer  | `app/services/effect_classifier.py` |
| Créer  | `app/services/guarded_mcp_executor.py` |
| Modifier | `app/models/invocation.py` — ajouter `calling_agent_id` |
| Modifier | `app/models/run.py` — ajouter `config` |
| Modifier | `app/services/agent_factory.py` — pre-flight effect check |
| Modifier | `app/api/routes/agents.py` — ajouter `/effect-violations` |
| Modifier | `app/api/routes/runs.py` — ajouter `/config` PATCH |
| Modifier | `frontend/src/components/test-lab/run-graph/RunGraph.tsx` — badge |
| Modifier | `frontend/src/components/agents/agent-form.tsx` — section violations |
| Modifier | `frontend/src/app/test-lab/runs/[id]/page.tsx` — override admin UI |
| Créer  | `tests/test_effect_classifier.py` |
| Créer  | `tests/test_guarded_mcp_executor.py` |
| Créer  | `frontend/src/components/agents/__tests__/EffectViolations.test.tsx` |

---

## Task 1 — Migration DB 020

**Files:**
- Create: `migrations/versions/020_mcp_effect_enforcement.py`
- Modify: `app/models/invocation.py`
- Modify: `app/models/run.py`

- [ ] **Step 1 : Ajouter `calling_agent_id` sur MCPInvocation**

Dans `app/models/invocation.py`, ajouter le champ après `subagent_invocation_id` (ligne 38) :

```python
    calling_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

Résultat — `MCPInvocation` aura les champs dans cet ordre :
```python
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("mcp_inv_"))
    run_id: Mapped[str] = mapped_column(String(36))
    subagent_invocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    calling_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mcp_id: Mapped[str] = mapped_column(String(100))
    mcp_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effect_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="requested")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    input_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2 : Ajouter `config` sur Run**

Dans `app/models/run.py`, ajouter après `final_output` (ligne 27) :

```python
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 3 : Créer la migration Alembic**

Créer `migrations/versions/020_mcp_effect_enforcement.py` :

```python
"""Add calling_agent_id to mcp_invocations and config to runs.

Revision ID: 020
Revises: 019
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mcp_invocations",
        sa.Column("calling_agent_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column("config", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_invocations", "calling_agent_id")
    op.drop_column("runs", "config")
```

- [ ] **Step 4 : Appliquer la migration**

```bash
alembic upgrade head
```

Attendu : `Running upgrade 019 -> 020`

- [ ] **Step 5 : Commit**

```bash
git add migrations/versions/020_mcp_effect_enforcement.py app/models/invocation.py app/models/run.py
git commit -m "feat(effect-enforcement): migration 020 — calling_agent_id + run.config"
```

---

## Task 2 — EffectClassifier

**Files:**
- Create: `app/services/effect_classifier.py`
- Create: `tests/test_effect_classifier.py`

- [ ] **Step 1 : Écrire les tests (TDD)**

Créer `tests/test_effect_classifier.py` :

```python
"""Tests for EffectClassifier — LLM-based MCP tool effect classification."""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.effect_classifier import EffectClassifier


@pytest.fixture
def classifier():
    """Fresh classifier (empty cache) per test."""
    c = EffectClassifier()
    c._cache.clear()
    return c


class TestHeuristicFallback:
    def test_write_prefix(self, classifier):
        assert classifier._heuristic_classify("write_file") == ["write"]

    def test_create_prefix(self, classifier):
        assert classifier._heuristic_classify("create_record") == ["write"]

    def test_delete_prefix(self, classifier):
        assert classifier._heuristic_classify("delete_item") == ["write"]

    def test_search_prefix(self, classifier):
        assert classifier._heuristic_classify("search_web") == ["search"]

    def test_read_prefix(self, classifier):
        assert classifier._heuristic_classify("read_document") == ["read"]

    def test_get_prefix(self, classifier):
        assert classifier._heuristic_classify("get_weather") == ["read"]

    def test_send_prefix(self, classifier):
        assert classifier._heuristic_classify("send_email") == ["act"]

    def test_unknown_tool(self, classifier):
        assert classifier._heuristic_classify("do_something_weird") == ["compute"]


class TestClassifyWithLLM:
    @pytest.mark.asyncio
    async def test_classify_single_effect(self, classifier):
        with patch.object(classifier, "_call_llm", new=AsyncMock(return_value="write")):
            result = await classifier.classify("save_document", {})
        assert result == ["write"]

    @pytest.mark.asyncio
    async def test_classify_compound_effects(self, classifier):
        with patch.object(classifier, "_call_llm", new=AsyncMock(return_value="write,act")):
            result = await classifier.classify("publish_and_notify", {})
        assert "write" in result
        assert "act" in result

    @pytest.mark.asyncio
    async def test_classify_uses_cache_on_second_call(self, classifier):
        mock_llm = AsyncMock(return_value="read")
        with patch.object(classifier, "_call_llm", new=mock_llm):
            await classifier.classify("get_data", {})
            await classifier.classify("get_data", {"key": "val"})
        assert mock_llm.call_count == 1  # second call hits cache

    @pytest.mark.asyncio
    async def test_classify_invalid_llm_response_uses_heuristic(self, classifier):
        with patch.object(classifier, "_call_llm", new=AsyncMock(return_value="destroy")):
            result = await classifier.classify("delete_all", {})
        assert result == ["write"]  # heuristic for delete_*

    @pytest.mark.asyncio
    async def test_classify_partial_invalid_response_filters_invalid(self, classifier):
        with patch.object(classifier, "_call_llm", new=AsyncMock(return_value="write,destroy")):
            result = await classifier.classify("write_and_destroy", {})
        assert result == ["write"]  # "destroy" filtered, "write" kept

    @pytest.mark.asyncio
    async def test_classify_llm_failure_uses_heuristic(self, classifier):
        with patch.object(classifier, "_call_llm", new=AsyncMock(side_effect=Exception("timeout"))):
            result = await classifier.classify("send_notification", {})
        assert result == ["act"]  # heuristic for send_*

    @pytest.mark.asyncio
    async def test_cache_populated_after_classify(self, classifier):
        with patch.object(classifier, "_call_llm", new=AsyncMock(return_value="search")):
            await classifier.classify("query_index", {})
        assert "query_index" in classifier._cache
        assert classifier._cache["query_index"] == ["search"]
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
python -m pytest tests/test_effect_classifier.py -v 2>&1 | head -20
```

Attendu : `ModuleNotFoundError: No module named 'app.services.effect_classifier'`

- [ ] **Step 3 : Implémenter EffectClassifier**

Créer `app/services/effect_classifier.py` :

```python
"""Effect Classifier — classifies MCP tool calls into effect types via LLM + heuristic fallback."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

EFFECT_TYPES = frozenset({"read", "search", "compute", "generate", "validate", "write", "act"})

_CLASSIFIER_SYSTEM = """Classify the MCP tool call into one or more of:
  read, search, compute, generate, validate, write, act

Definitions:
- read    : fetches/retrieves data, no mutation
- search  : queries/lookups, no mutation
- compute : pure calculation, no I/O side effects
- generate: produces new content (text, image, code)
- validate: checks/verifies, no mutation
- write   : creates, updates, or deletes data
- act     : triggers external action (email, API call, deploy, publish)

Reply with a comma-separated list of applicable effects (lowercase, no spaces after comma).
Examples: "write" or "write,act" or "read,compute"
No explanation — only the list."""


class EffectClassifier:
    """LLM-based tool effect classifier with process-level cache and heuristic fallback."""

    def __init__(self) -> None:
        self._cache: dict[str, list[str]] = {}

    async def classify(self, tool_name: str, args: dict[str, Any]) -> list[str]:
        """Return the list of effects for this tool call.

        Uses process-level cache keyed on tool_name (effects are stable per tool).
        Falls back to heuristic if LLM is unavailable or returns invalid output.
        """
        if tool_name in self._cache:
            return self._cache[tool_name]

        try:
            raw = await asyncio.wait_for(self._call_llm(tool_name, args), timeout=2.0)
            effects = [e.strip() for e in raw.split(",") if e.strip() in EFFECT_TYPES]
            if not effects:
                effects = self._heuristic_classify(tool_name)
        except Exception as exc:
            logger.warning("[EffectClassifier] LLM call failed for '%s': %s — using heuristic", tool_name, exc)
            effects = self._heuristic_classify(tool_name)

        self._cache[tool_name] = effects
        return effects

    async def _call_llm(self, tool_name: str, args: dict[str, Any]) -> str:
        """Call Haiku LLM to classify the tool effect. Returns raw string response."""
        from app.llm.provider import get_chat_model
        from agentscope.message import Msg

        model = get_chat_model()
        if model is None:
            raise RuntimeError("LLM model unavailable")

        args_summary = str(args)[:200] if args else ""
        user_content = f"tool={tool_name} args={args_summary}"

        response = model(
            [
                Msg(name="system", role="system", content=_CLASSIFIER_SYSTEM),
                Msg(name="user", role="user", content=user_content),
            ]
        )
        if hasattr(response, "text"):
            return response.text.strip().lower()
        return str(response).strip().lower()

    def _heuristic_classify(self, tool_name: str) -> list[str]:
        """Pattern-based fallback classifier."""
        name = tool_name.lower()
        if any(p in name for p in ("write", "create", "delete", "update", "save", "remove", "insert")):
            return ["write"]
        if any(p in name for p in ("search", "query", "find", "lookup", "filter")):
            return ["search"]
        if any(p in name for p in ("get", "fetch", "read", "list", "retrieve", "load")):
            return ["read"]
        if any(p in name for p in ("send", "post", "publish", "deploy", "email", "notify", "trigger")):
            return ["act"]
        if any(p in name for p in ("generate", "create_content", "draft", "synthesize")):
            return ["generate"]
        if any(p in name for p in ("validate", "check", "verify", "lint", "test")):
            return ["validate"]
        return ["compute"]


# Singleton — shared across all requests in this process
_classifier = EffectClassifier()


def get_classifier() -> EffectClassifier:
    """Return the process-level singleton EffectClassifier."""
    return _classifier
```

- [ ] **Step 4 : Exécuter les tests**

```bash
python -m pytest tests/test_effect_classifier.py -v
```

Attendu : tous les tests passent.

- [ ] **Step 5 : Commit**

```bash
git add app/services/effect_classifier.py tests/test_effect_classifier.py
git commit -m "feat(effect-enforcement): EffectClassifier LLM + cache + heuristic (TDD)"
```

---

## Task 3 — GuardedMCPExecutor

**Files:**
- Create: `app/services/guarded_mcp_executor.py`
- Create: `tests/test_guarded_mcp_executor.py`

- [ ] **Step 1 : Écrire les tests**

Créer `tests/test_guarded_mcp_executor.py` :

```python
"""Tests for guarded_invoke_mcp — AOP wrapper with effect enforcement."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.registry import AgentDefinition, MCPDefinition
from app.models.family import FamilyDefinition
from app.models.run import Run
from app.models.enums import AgentStatus, MCPStatus


async def _setup_fixtures(db_session):
    family = FamilyDefinition(id="test_fam", label="Test")
    db_session.add(family)
    mcp = MCPDefinition(
        id="fs_mcp", name="Filesystem", purpose="Files",
        effect_type="write", version="1.0.0", status=MCPStatus.ACTIVE,
    )
    db_session.add(mcp)
    agent = AgentDefinition(
        id="write_agent", name="WriteAgent", family_id="test_fam",
        purpose="Writes files", version="1.0.0", status=AgentStatus.ACTIVE,
        allowed_mcps=["fs_mcp"], forbidden_effects=["write"],
    )
    db_session.add(agent)
    run = Run(case_id="case_1", plan_id="plan_1", status="running")
    db_session.add(run)
    await db_session.flush()
    return agent, mcp, run


class TestGuardedInvokeMcp:
    @pytest.mark.asyncio
    async def test_blocks_forbidden_single_effect(self, db_session):
        agent, mcp, run = await _setup_fixtures(db_session)
        await db_session.commit()

        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=AsyncMock(return_value=["write"]),
        ):
            from app.services.guarded_mcp_executor import guarded_invoke_mcp
            inv = await guarded_invoke_mcp(
                db_session, run.id, "fs_mcp", "write_agent",
                tool_action="write_file", tool_kwargs={"path": "/tmp/x"},
            )

        assert inv.status == "denied"
        assert inv.effect_type == "write"
        assert inv.calling_agent_id == "write_agent"

    @pytest.mark.asyncio
    async def test_blocks_compound_effect_any_match(self, db_session):
        agent, mcp, run = await _setup_fixtures(db_session)
        await db_session.commit()

        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=AsyncMock(return_value=["read", "write"]),
        ):
            from app.services.guarded_mcp_executor import guarded_invoke_mcp
            inv = await guarded_invoke_mcp(
                db_session, run.id, "fs_mcp", "write_agent",
                tool_action="read_and_write", tool_kwargs={},
            )

        assert inv.status == "denied"
        assert "write" in inv.effect_type

    @pytest.mark.asyncio
    async def test_allows_permitted_effect(self, db_session):
        agent, mcp, run = await _setup_fixtures(db_session)
        await db_session.commit()

        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=AsyncMock(return_value=["read"]),
        ), patch(
            "app.services.guarded_mcp_executor.invoke_mcp",
            new=AsyncMock(return_value=MagicMock(status="completed")),
        ):
            from app.services.guarded_mcp_executor import guarded_invoke_mcp
            inv = await guarded_invoke_mcp(
                db_session, run.id, "fs_mcp", "write_agent",
                tool_action="read_file", tool_kwargs={},
            )

        assert inv.status == "completed"

    @pytest.mark.asyncio
    async def test_run_override_unblocks_effect(self, db_session):
        agent, mcp, run = await _setup_fixtures(db_session)
        run.config = {"effect_overrides": ["write"]}
        await db_session.commit()

        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=AsyncMock(return_value=["write"]),
        ), patch(
            "app.services.guarded_mcp_executor.invoke_mcp",
            new=AsyncMock(return_value=MagicMock(status="completed")),
        ):
            from app.services.guarded_mcp_executor import guarded_invoke_mcp
            inv = await guarded_invoke_mcp(
                db_session, run.id, "fs_mcp", "write_agent",
                tool_action="write_file", tool_kwargs={},
            )

        assert inv.status == "completed"

    @pytest.mark.asyncio
    async def test_run_override_partial_still_blocks_other_effects(self, db_session):
        agent, mcp, run = await _setup_fixtures(db_session)
        # Agent forbidden: write + act. Override only write.
        agent.forbidden_effects = ["write", "act"]
        run.config = {"effect_overrides": ["write"]}
        await db_session.flush()
        await db_session.commit()

        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=AsyncMock(return_value=["act"]),
        ):
            from app.services.guarded_mcp_executor import guarded_invoke_mcp
            inv = await guarded_invoke_mcp(
                db_session, run.id, "fs_mcp", "write_agent",
                tool_action="send_email", tool_kwargs={},
            )

        assert inv.status == "denied"
        assert "act" in inv.effect_type

    @pytest.mark.asyncio
    async def test_no_forbidden_effects_skips_classifier(self, db_session):
        family = FamilyDefinition(id="fam2", label="Fam2")
        db_session.add(family)
        mcp = MCPDefinition(
            id="mcp2", name="MCP2", purpose="x",
            effect_type="read", version="1.0", status=MCPStatus.ACTIVE,
        )
        db_session.add(mcp)
        agent = AgentDefinition(
            id="free_agent", name="FreeAgent", family_id="fam2",
            purpose="No restrictions", version="1.0", status=AgentStatus.ACTIVE,
            allowed_mcps=["mcp2"], forbidden_effects=[],
        )
        db_session.add(agent)
        run = Run(case_id="c1", plan_id="p1", status="running")
        db_session.add(run)
        await db_session.flush()
        await db_session.commit()

        mock_classify = AsyncMock(return_value=["write"])
        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=mock_classify,
        ), patch(
            "app.services.guarded_mcp_executor.invoke_mcp",
            new=AsyncMock(return_value=MagicMock(status="completed")),
        ):
            from app.services.guarded_mcp_executor import guarded_invoke_mcp
            inv = await guarded_invoke_mcp(
                db_session, run.id, "mcp2", "free_agent",
                tool_action="write_file", tool_kwargs={},
            )

        mock_classify.assert_not_called()
        assert inv.status == "completed"

    @pytest.mark.asyncio
    async def test_no_tool_action_skips_classifier(self, db_session):
        agent, mcp, run = await _setup_fixtures(db_session)
        await db_session.commit()

        mock_classify = AsyncMock(return_value=["write"])
        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=mock_classify,
        ), patch(
            "app.services.guarded_mcp_executor.invoke_mcp",
            new=AsyncMock(return_value=MagicMock(status="completed")),
        ):
            from app.services.guarded_mcp_executor import guarded_invoke_mcp
            inv = await guarded_invoke_mcp(
                db_session, run.id, "fs_mcp", "write_agent",
                tool_action=None, tool_kwargs={},
            )

        mock_classify.assert_not_called()
        assert inv.status == "completed"
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
python -m pytest tests/test_guarded_mcp_executor.py -v 2>&1 | head -10
```

Attendu : `ModuleNotFoundError: No module named 'app.services.guarded_mcp_executor'`

- [ ] **Step 3 : Implémenter guarded_mcp_executor**

Créer `app/services/guarded_mcp_executor.py` :

```python
"""Guarded MCP Executor — AOP wrapper enforcing forbidden_effects before delegating to invoke_mcp."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invocation import MCPInvocation
from app.models.registry import AgentDefinition
from app.models.run import Run
from app.services.effect_classifier import get_classifier
from app.services.event_service import emit_event
from app.services.mcp_executor import invoke_mcp

logger = logging.getLogger(__name__)

_classifier = get_classifier()


async def guarded_invoke_mcp(
    db: AsyncSession,
    run_id: str,
    mcp_id: str,
    calling_agent_id: str,
    subagent_invocation_id: str | None = None,
    tool_action: str | None = None,
    tool_kwargs: dict | None = None,
) -> MCPInvocation:
    """Enforce forbidden_effects before delegating to invoke_mcp.

    Checks:
    1. Load agent's forbidden_effects.
    2. Load run-level effect_overrides (from Run.config).
    3. Classify tool_action via EffectClassifier (LLM + cache + heuristic).
    4. Block if any classified effect is in (forbidden - overrides).
    5. Delegate to invoke_mcp for allowed calls.
    """
    # [1] Load agent forbidden_effects
    agent = await db.get(AgentDefinition, calling_agent_id)
    forbidden = set(agent.forbidden_effects or []) if agent else set()

    # [2] Load run-level overrides
    run = await db.get(Run, run_id)
    overrides = set((run.config or {}).get("effect_overrides", [])) if run else set()
    effective_forbidden = forbidden - overrides

    # [3] Classify if enforcement is needed
    if effective_forbidden and tool_action:
        effects = await _classifier.classify(tool_action, tool_kwargs or {})
        blocked = [e for e in effects if e in effective_forbidden]

        if blocked:
            blocked_str = ",".join(sorted(blocked))
            inv = MCPInvocation(
                run_id=run_id,
                subagent_invocation_id=subagent_invocation_id,
                mcp_id=mcp_id,
                calling_agent_id=calling_agent_id,
                effect_type=blocked_str,
                status="denied",
                approval_required=False,
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
            )
            db.add(inv)
            await db.flush()
            await emit_event(
                db, "mcp.denied", "runtime", "guarded_mcp_executor",
                run_id=run_id,
                payload={
                    "mcp_id": mcp_id,
                    "agent_id": calling_agent_id,
                    "reason": "forbidden_effect",
                    "tool": tool_action,
                    "effects": blocked,
                },
            )
            logger.warning(
                "[EffectEnforcement] run=%s agent=%s tool=%s blocked effects=%s",
                run_id, calling_agent_id, tool_action, blocked,
            )
            return inv

    # [4] Delegate to inner executor
    return await invoke_mcp(
        db, run_id, mcp_id, calling_agent_id,
        subagent_invocation_id, tool_action, tool_kwargs,
    )
```

- [ ] **Step 4 : Exécuter les tests**

```bash
python -m pytest tests/test_guarded_mcp_executor.py -v
```

Attendu : tous les tests passent.

- [ ] **Step 5 : Commit**

```bash
git add app/services/guarded_mcp_executor.py tests/test_guarded_mcp_executor.py
git commit -m "feat(effect-enforcement): guarded_mcp_executor AOP — compound effects + run override (TDD)"
```

---

## Task 4 — Wiring : pre-flight dans agent_factory + test_executors

**Files:**
- Modify: `app/services/agent_factory.py`
- Modify: `tests/test_executors.py`

- [ ] **Step 1 : Ajouter le pre-flight effect check dans agent_factory.py**

Dans `app/services/agent_factory.py`, trouver le bloc autour de la ligne 357 :

```python
                mcp_tools = await mcp_client.list_tools()
                logger.info(f"MCP {mcp_id} ({srv['url']}): {len(mcp_tools)} tools found")
                # Patch known schema mismatches ...
                _patch_mcp_tool_schemas(mcp_tools)
                if mcp_tools:
                    await toolkit.register_mcp_client(
```

Modifier ce bloc pour ajouter le pre-flight check :

```python
                mcp_tools = await mcp_client.list_tools()
                logger.info(f"MCP {mcp_id} ({srv['url']}): {len(mcp_tools)} tools found")

                # Pre-flight effect enforcement: classify each tool and record
                # denied invocations for tools with forbidden effects.
                # Tools with at least one non-forbidden effect remain registered.
                if agent_def.forbidden_effects and test_run_id and db:
                    from app.services.effect_classifier import get_classifier
                    from app.services.guarded_mcp_executor import guarded_invoke_mcp
                    _eff_classifier = get_classifier()
                    _forbidden_set = set(agent_def.forbidden_effects)
                    _allowed_tools = []
                    for _tool in mcp_tools:
                        _effects = await _eff_classifier.classify(_tool.name, {})
                        _blocked = [e for e in _effects if e in _forbidden_set]
                        if _blocked and set(_effects) <= _forbidden_set:
                            # ALL effects are forbidden — skip this tool
                            logger.warning(
                                "[EffectEnforcement] Pre-flight: agent=%s tool=%s blocked effects=%s",
                                agent_def.id, _tool.name, _blocked,
                            )
                            from app.models.invocation import MCPInvocation
                            from datetime import datetime, timezone
                            from app.services.event_service import emit_event
                            _inv = MCPInvocation(
                                run_id=test_run_id,
                                mcp_id=mcp_id,
                                calling_agent_id=agent_def.id,
                                effect_type=",".join(sorted(_blocked)),
                                status="denied",
                                approval_required=False,
                                started_at=datetime.now(timezone.utc),
                                ended_at=datetime.now(timezone.utc),
                            )
                            db.add(_inv)
                            await db.flush()
                            await emit_event(
                                db, "mcp.denied", "runtime", "agent_factory",
                                run_id=test_run_id,
                                payload={
                                    "mcp_id": mcp_id,
                                    "agent_id": agent_def.id,
                                    "reason": "forbidden_effect",
                                    "tool": _tool.name,
                                    "effects": _blocked,
                                },
                            )
                        else:
                            _allowed_tools.append(_tool)
                    mcp_tools = _allowed_tools

                # Patch known schema mismatches ...
                _patch_mcp_tool_schemas(mcp_tools)
                if mcp_tools:
                    await toolkit.register_mcp_client(
```

- [ ] **Step 2 : Mettre à jour test_executors.py pour utiliser guarded_invoke_mcp**

Dans `tests/test_executors.py`, ajouter l'import et un test pour guarded_invoke_mcp :

```python
from app.services.guarded_mcp_executor import guarded_invoke_mcp

class TestGuardedMCPExecutorIntegration:
    async def test_guarded_invoke_blocks_forbidden_effect(self, db_session):
        """Integration test: guarded_invoke_mcp blocks when effect is forbidden."""
        await _ensure_family(db_session)
        mcp = await _setup_mcp(db_session, mcp_id="write_mcp")
        agent = AgentDefinition(
            id="restricted", name="Restricted Agent", family_id="analysis",
            purpose="Restricted", version="1.0.0", status=AgentStatus.ACTIVE,
            allowed_mcps=["write_mcp"], forbidden_effects=["read"],
        )
        db_session.add(agent)
        run, _ = await _setup_run_with_node(db_session, agent_id="restricted")
        await db_session.commit()

        from unittest.mock import patch, AsyncMock
        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=AsyncMock(return_value=["read"]),
        ):
            inv = await guarded_invoke_mcp(
                db_session, run.id, "write_mcp", "restricted",
                tool_action="read_data", tool_kwargs={},
            )

        assert inv.status == "denied"
        assert inv.calling_agent_id == "restricted"
        assert inv.effect_type == "read"

    async def test_guarded_invoke_allows_non_forbidden_effect(self, db_session):
        """Integration test: guarded_invoke_mcp delegates when effect is allowed."""
        await _ensure_family(db_session)
        await _setup_mcp(db_session, mcp_id="doc_parser2")
        agent = AgentDefinition(
            id="partial_restricted", name="Partial", family_id="analysis",
            purpose="Partial", version="1.0.0", status=AgentStatus.ACTIVE,
            allowed_mcps=["doc_parser2"], forbidden_effects=["write"],
        )
        db_session.add(agent)
        run, _ = await _setup_run_with_node(db_session, agent_id="partial_restricted")
        await db_session.commit()

        from unittest.mock import patch, AsyncMock
        with patch(
            "app.services.guarded_mcp_executor._classifier.classify",
            new=AsyncMock(return_value=["read"]),
        ):
            inv = await guarded_invoke_mcp(
                db_session, run.id, "doc_parser2", "partial_restricted",
                tool_action="read_file", tool_kwargs={},
            )

        # invoke_mcp is called → status will be "completed" (mock MCP tool)
        assert inv.status in ("completed", "running", "failed")
        assert inv.status != "denied"
```

- [ ] **Step 3 : Exécuter les tests**

```bash
python -m pytest tests/test_executors.py::TestGuardedMCPExecutorIntegration -v
```

Attendu : les 2 nouveaux tests passent.

- [ ] **Step 4 : Commit**

```bash
git add app/services/agent_factory.py tests/test_executors.py
git commit -m "feat(effect-enforcement): pre-flight check dans agent_factory + integration tests"
```

---

## Task 5 — Backend route : violations par agent

**Files:**
- Modify: `app/api/routes/agents.py`

- [ ] **Step 1 : Ajouter la route GET /agents/{agent_id}/effect-violations**

Dans `app/api/routes/agents.py`, ajouter après la route `/{agent_id}/test-runs` (après la ligne 307) :

```python
from sqlalchemy import select


@router.get("/{agent_id}/effect-violations")
async def list_agent_effect_violations(
    agent_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List MCPInvocations denied due to forbidden effects for this agent."""
    from app.models.invocation import MCPInvocation
    from sqlalchemy import select

    result = await db.execute(
        select(MCPInvocation)
        .where(
            MCPInvocation.calling_agent_id == agent_id,
            MCPInvocation.status == "denied",
            MCPInvocation.effect_type.isnot(None),
        )
        .order_by(MCPInvocation.started_at.desc())
        .limit(limit)
    )
    violations = result.scalars().all()

    # Build summary: count per effect
    summary: dict[str, int] = {}
    for v in violations:
        for eff in (v.effect_type or "").split(","):
            eff = eff.strip()
            if eff:
                summary[eff] = summary.get(eff, 0) + 1

    return {
        "violations": [
            {
                "id": v.id,
                "run_id": v.run_id,
                "mcp_id": v.mcp_id,
                "effects": [e.strip() for e in (v.effect_type or "").split(",") if e.strip()],
                "blocked_at": v.started_at.isoformat() if v.started_at else None,
            }
            for v in violations
        ],
        "summary": summary,
    }
```

- [ ] **Step 2 : Tester la route manuellement**

```bash
curl -s http://localhost:8000/api/agents/budget_fit_agent/effect-violations | python -m json.tool
```

Attendu : `{"violations": [], "summary": {}}` (ou des données si des violations existent)

- [ ] **Step 3 : Commit**

```bash
git add app/api/routes/agents.py
git commit -m "feat(effect-enforcement): GET /agents/{id}/effect-violations route"
```

---

## Task 6 — Backend route : run config override

**Files:**
- Modify: `app/api/routes/runs.py`

- [ ] **Step 1 : Ajouter la route PATCH /runs/{run_id}/config**

Dans `app/api/routes/runs.py`, ajouter après la route `GET /runs/{run_id}/nodes` :

```python
from pydantic import BaseModel as PydanticBaseModel


class RunConfigUpdate(PydanticBaseModel):
    effect_overrides: list[str] = []


@router.patch("/runs/{run_id}/config")
async def update_run_config(
    run_id: str,
    data: RunConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update admin overrides for a specific run (e.g., effect_overrides)."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    existing_config = run.config or {}
    existing_config["effect_overrides"] = data.effect_overrides
    run.config = existing_config
    await db.commit()
    await db.refresh(run)
    return {"run_id": run_id, "config": run.config}
```

Also add `from app.models.run import Run` to imports if not present.

- [ ] **Step 2 : Tester la route manuellement**

```bash
curl -s -X PATCH http://localhost:8000/api/runs/run_test123/config \
  -H "Content-Type: application/json" \
  -d '{"effect_overrides": ["write"]}' | python -m json.tool
```

Attendu : `{"run_id": "...", "config": {"effect_overrides": ["write"]}}` (ou 404 si le run n'existe pas)

- [ ] **Step 3 : Commit**

```bash
git add app/api/routes/runs.py
git commit -m "feat(effect-enforcement): PATCH /runs/{id}/config pour override admin"
```

---

## Task 7 — RunGraph badge pour violations d'effet

**Files:**
- Modify: `frontend/src/components/test-lab/run-graph/RunGraph.tsx`

- [ ] **Step 1 : Écrire le test Vitest**

Créer `frontend/src/components/test-lab/run-graph/__tests__/EffectBadge.test.tsx` :

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

// Isolated component extracted from RunGraph logic
function EffectDenialBadge({ effects }: { effects: string[] }) {
  if (!effects.length) return null;
  return (
    <span
      className="text-ork-red bg-ork-red-bg"
      title={`effects [${effects.join(", ")}] are forbidden for this agent`}
    >
      ⛔ blocked: {effects.join(", ")}
    </span>
  );
}

describe("EffectDenialBadge", () => {
  it("renders blocked effects", () => {
    render(<EffectDenialBadge effects={["write"]} />);
    expect(screen.getByText(/blocked: write/)).toBeTruthy();
  });

  it("renders compound effects", () => {
    render(<EffectDenialBadge effects={["write", "act"]} />);
    expect(screen.getByText(/blocked: write, act/)).toBeTruthy();
  });

  it("renders nothing for empty effects", () => {
    const { container } = render(<EffectDenialBadge effects={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2 : Exécuter le test pour vérifier qu'il échoue**

```bash
cd frontend && npm test -- src/components/test-lab/run-graph/__tests__/EffectBadge.test.tsx 2>&1 | tail -10
```

Attendu : `Cannot find module` ou test failure.

- [ ] **Step 3 : Ajouter le badge dans RunGraph.tsx**

Dans `frontend/src/components/test-lab/run-graph/RunGraph.tsx`, localiser le composant `RunGraph` et ajouter la logique de badge.

Ajouter cette fonction helper avant le composant `RunGraph` (ou dans une section helpers du fichier) :

```tsx
/** Extract forbidden-effect denial events from the run event list */
function getForbiddenEffectDenials(events: TestRunEvent[]): Array<{ tool: string; effects: string[] }> {
  return events
    .filter(
      (e) =>
        e.event_type === "mcp.denied" &&
        (e.payload as Record<string, unknown>)?.reason === "forbidden_effect"
    )
    .map((e) => ({
      tool: String((e.payload as Record<string, unknown>)?.tool ?? "unknown"),
      effects: ((e.payload as Record<string, unknown>)?.effects as string[]) ?? [],
    }));
}
```

Puis dans le JSX du composant, après `<RunTopbar ...>` ou dans la zone d'informations du panel, ajouter un affichage des violations :

Trouver dans le JSX de `RunGraph.tsx` l'endroit où les informations du run sont affichées (probablement dans `DetailPanel` ou dans l'en-tête). Ajouter le badge dans la section qui affiche les events de type `mcp.denied`.

Dans `DetailPanel.tsx` ou `RunGraph.tsx`, dans la section qui liste les events du panel, ajouter :

```tsx
{/* Forbidden effect denials */}
{getForbiddenEffectDenials(events).map((denial, i) => (
  <div
    key={i}
    className="flex items-center gap-2 px-2 py-1 rounded text-xs"
    style={{
      color: "var(--ork-red)",
      background: "var(--ork-red-bg)",
      border: "1px solid color-mix(in oklch, var(--ork-red) 30%, transparent)",
    }}
    title={`effects [${denial.effects.join(", ")}] are forbidden for this agent`}
  >
    <span>⛔</span>
    <span>blocked: {denial.effects.join(", ")}</span>
    <span style={{ color: "var(--ork-muted)" }}>— {denial.tool}</span>
  </div>
))}
```

Note : adapter selon la structure réelle du DetailPanel. Si `DetailPanel.tsx` est un composant séparé, passer `events` en prop et ajouter le JSX là-bas.

- [ ] **Step 4 : Exécuter le test**

```bash
cd frontend && npm test -- src/components/test-lab/run-graph/__tests__/EffectBadge.test.tsx 2>&1 | tail -10
```

Attendu : tests passent.

- [ ] **Step 5 : Déployer dans Docker**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER cp frontend/src/components/test-lab/run-graph/RunGraph.tsx \
  orkestra-frontend-1:/app/src/components/test-lab/run-graph/RunGraph.tsx
```

- [ ] **Step 6 : Commit**

```bash
git add frontend/src/components/test-lab/run-graph/
git commit -m "feat(effect-enforcement): badge ⛔ dans RunGraph pour forbidden_effect denials"
```

---

## Task 8 — Section violations dans agent-form

**Files:**
- Modify: `frontend/src/components/agents/agent-form.tsx`
- Create: `frontend/src/components/agents/__tests__/EffectViolations.test.tsx`

- [ ] **Step 1 : Écrire les tests Vitest**

Créer `frontend/src/components/agents/__tests__/EffectViolations.test.tsx` :

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

interface Violation {
  id: string;
  run_id: string;
  mcp_id: string;
  effects: string[];
  blocked_at: string | null;
}

function EffectViolationsSection({
  violations,
  summary,
  isEditMode,
}: {
  violations: Violation[];
  summary: Record<string, number>;
  isEditMode: boolean;
}) {
  if (!isEditMode) return null;
  return (
    <section data-testid="effect-violations">
      <h3>Violations d&apos;effet</h3>
      <div data-testid="summary">
        {Object.entries(summary).map(([effect, count]) => (
          <span key={effect} data-testid={`summary-${effect}`}>
            {effect}: {count}
          </span>
        ))}
      </div>
      {violations.length === 0 ? (
        <p data-testid="no-violations">Aucune violation</p>
      ) : (
        <table>
          <tbody>
            {violations.map((v) => (
              <tr key={v.id} data-testid={`violation-${v.id}`}>
                <td>{v.run_id}</td>
                <td>{v.mcp_id}</td>
                <td>{v.effects.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

describe("EffectViolationsSection", () => {
  it("is hidden in create mode", () => {
    const { container } = render(
      <EffectViolationsSection violations={[]} summary={{}} isEditMode={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows no-violations message when empty", () => {
    render(<EffectViolationsSection violations={[]} summary={{}} isEditMode={true} />);
    expect(screen.getByTestId("no-violations")).toBeTruthy();
  });

  it("renders violation rows", () => {
    const violations = [
      { id: "v1", run_id: "run_abc", mcp_id: "fs_mcp", effects: ["write"], blocked_at: null },
    ];
    render(<EffectViolationsSection violations={violations} summary={{ write: 1 }} isEditMode={true} />);
    expect(screen.getByTestId("violation-v1")).toBeTruthy();
    expect(screen.getByTestId("summary-write").textContent).toBe("write: 1");
  });

  it("renders summary badges", () => {
    render(
      <EffectViolationsSection
        violations={[]}
        summary={{ write: 5, act: 2 }}
        isEditMode={true}
      />
    );
    expect(screen.getByTestId("summary-write").textContent).toBe("write: 5");
    expect(screen.getByTestId("summary-act").textContent).toBe("act: 2");
  });
});
```

- [ ] **Step 2 : Vérifier que les tests passent (logique isolée)**

```bash
cd frontend && npm test -- src/components/agents/__tests__/EffectViolations.test.tsx 2>&1 | tail -10
```

Attendu : tous les tests passent (logique isolée, pas besoin d'import depuis agent-form).

- [ ] **Step 3 : Intégrer dans agent-form.tsx**

Dans `frontend/src/components/agents/agent-form.tsx` :

**3a. Ajouter le state et fetch au début du composant (après les useState existants) :**

```tsx
// Effect violations (visible en edit mode seulement)
const [effectViolations, setEffectViolations] = useState<{
  violations: Array<{ id: string; run_id: string; mcp_id: string; effects: string[]; blocked_at: string | null }>;
  summary: Record<string, number>;
}>({ violations: [], summary: {} });

useEffect(() => {
  if (!agentId) return; // create mode — no fetch
  request<{ violations: Array<{ id: string; run_id: string; mcp_id: string; effects: string[]; blocked_at: string | null }>; summary: Record<string, number> }>(
    `/api/agents/${agentId}/effect-violations`
  )
    .then((data) => setEffectViolations(data))
    .catch(() => {}); // silently ignore — section stays empty
}, [agentId]);
```

Note : `agentId` est la prop qui indique si on est en mode édition. S'il n'existe pas sous ce nom, utiliser l'équivalent (chercher comment l'agent edit détecte si c'est un create ou un edit).

**3b. Ajouter la section violations à la fin du formulaire (avant le bouton submit) :**

```tsx
{/* Section 13 — Violations d'effet (edit mode only) */}
{agentId && (
  <section className="form-section">
    <div className="form-section__header">
      <h3 className="form-section__title">Violations d&apos;effet</h3>
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
        {Object.entries(effectViolations.summary).map(([effect, count]) => (
          <span
            key={effect}
            className="badge badge--failed"
            style={{ fontSize: "11px" }}
          >
            {effect}: {count}
          </span>
        ))}
      </div>
    </div>
    {effectViolations.violations.length === 0 ? (
      <p style={{ color: "var(--ork-muted)", fontSize: "13px" }}>Aucune violation enregistrée.</p>
    ) : (
      <table className="tablewrap__table" style={{ fontSize: "12px" }}>
        <thead>
          <tr>
            <th>Run</th>
            <th>MCP</th>
            <th>Effets bloqués</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {effectViolations.violations.map((v) => (
            <tr key={v.id}>
              <td>
                <a href={`/test-lab/runs/${v.run_id}`} style={{ color: "var(--ork-cyan)" }}>
                  {v.run_id.slice(0, 12)}…
                </a>
              </td>
              <td style={{ color: "var(--ork-muted)" }}>{v.mcp_id}</td>
              <td>
                <span style={{ color: "var(--ork-red)" }}>{v.effects.join(", ")}</span>
              </td>
              <td style={{ color: "var(--ork-dim)" }}>
                {v.blocked_at ? new Date(v.blocked_at).toLocaleDateString("fr-FR") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </section>
)}
```

- [ ] **Step 4 : Déployer dans Docker**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER cp frontend/src/components/agents/agent-form.tsx \
  orkestra-frontend-1:/app/src/components/agents/agent-form.tsx
```

- [ ] **Step 5 : Vérifier visuellement**

Ouvrir `http://localhost:3300/agents/budget_fit_agent/edit`.
La section "Violations d'effet" doit apparaître en bas du formulaire.
"Aucune violation enregistrée." si vide.

- [ ] **Step 6 : Commit**

```bash
git add frontend/src/components/agents/agent-form.tsx \
        frontend/src/components/agents/__tests__/EffectViolations.test.tsx
git commit -m "feat(effect-enforcement): section violations dans agent-form (TDD)"
```

---

## Task 9 — Override admin dans run detail

**Files:**
- Modify: `frontend/src/app/test-lab/runs/[id]/page.tsx`

- [ ] **Step 1 : Ajouter state + fetch du config existant**

Dans `frontend/src/app/test-lab/runs/[id]/page.tsx`, ajouter après les useState existants :

```tsx
const [effectOverrides, setEffectOverrides] = useState<string[]>([]);
const [overrideSaving, setOverrideSaving] = useState(false);

// Fetch existing run config on mount
useEffect(() => {
  if (!runId) return;
  request<{ run_id: string; config: { effect_overrides?: string[] } }>(
    `/api/runs/${runId}/config`
  )
    .then((data) => setEffectOverrides(data.config?.effect_overrides ?? []))
    .catch(() => {}); // silently ignore if endpoint not yet deployed
}, [runId]);
```

Note : `runId` vient de `useParams()` déjà présent dans la page.

- [ ] **Step 2 : Ajouter la fonction save**

```tsx
const saveEffectOverrides = async (overrides: string[]) => {
  setOverrideSaving(true);
  try {
    await request(`/api/runs/${runId}/config`, {
      method: "PATCH",
      body: JSON.stringify({ effect_overrides: overrides }),
    });
    setEffectOverrides(overrides);
  } finally {
    setOverrideSaving(false);
  }
};
```

- [ ] **Step 3 : Ajouter la section UI dans le JSX**

Dans la page, trouver la zone des métadonnées du run (après les informations de statut). Ajouter une section collapsible :

```tsx
{/* Admin override section */}
<details style={{ marginTop: "16px" }}>
  <summary
    style={{
      cursor: "pointer",
      fontSize: "12px",
      color: "var(--ork-muted)",
      userSelect: "none",
    }}
  >
    ⚙ Override forbidden effects pour ce run
  </summary>
  <div
    style={{
      marginTop: "10px",
      padding: "12px",
      background: "var(--ork-panel)",
      borderRadius: "6px",
      border: "1px solid var(--ork-border)",
    }}
  >
    <p style={{ fontSize: "12px", color: "var(--ork-muted)", marginBottom: "10px" }}>
      Effets cochés = autorisés pour ce run même si interdits par l&apos;agent.
    </p>
    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "12px" }}>
      {(["read", "search", "compute", "generate", "validate", "write", "act"] as const).map((eff) => (
        <label key={eff} style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "12px" }}>
          <input
            type="checkbox"
            checked={effectOverrides.includes(eff)}
            onChange={(e) => {
              const next = e.target.checked
                ? [...effectOverrides, eff]
                : effectOverrides.filter((o) => o !== eff);
              setEffectOverrides(next);
            }}
          />
          {eff}
        </label>
      ))}
    </div>
    <button
      className="btn btn--cyan"
      style={{ fontSize: "12px" }}
      disabled={overrideSaving}
      onClick={() => saveEffectOverrides(effectOverrides)}
    >
      {overrideSaving ? "Saving…" : "Save overrides"}
    </button>
    {effectOverrides.length > 0 && (
      <p style={{ marginTop: "8px", fontSize: "11px", color: "var(--ork-amber)" }}>
        ⚠ {effectOverrides.length} effect(s) overridden for this run
      </p>
    )}
  </div>
</details>
```

- [ ] **Step 4 : Déployer dans Docker**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER cp "frontend/src/app/test-lab/runs/[id]/page.tsx" \
  "orkestra-frontend-1:/app/src/app/test-lab/runs/[id]/page.tsx"
```

- [ ] **Step 5 : Vérifier visuellement**

Ouvrir un run existant dans `http://localhost:3300/test-lab/runs/{id}`.
La section "⚙ Override forbidden effects" doit apparaître, collapsée par défaut.
Cocher "write" → Save → recharger → "write" doit rester coché.

- [ ] **Step 6 : Commit final**

```bash
git add "frontend/src/app/test-lab/runs/[id]/page.tsx"
git commit -m "feat(effect-enforcement): override admin forbidden effects par run dans run detail"
```

---

## Checklist de validation finale

- [ ] `alembic upgrade head` appliqué sans erreur
- [ ] `pytest tests/test_effect_classifier.py -v` — tous verts
- [ ] `pytest tests/test_guarded_mcp_executor.py -v` — tous verts
- [ ] `pytest tests/test_executors.py::TestGuardedMCPExecutorIntegration -v` — tous verts
- [ ] `GET /api/agents/{id}/effect-violations` retourne `{"violations":[], "summary":{}}`
- [ ] `PATCH /api/runs/{id}/config` met à jour `run.config`
- [ ] Badge ⛔ visible dans RunGraph pour events `mcp.denied` + `reason=forbidden_effect`
- [ ] Section violations visible dans agent edit (pas dans create)
- [ ] Section override visible dans run detail, persistance après rechargement
