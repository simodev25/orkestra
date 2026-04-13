# Comprehensive Test Strategy — Orkestra

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Établir une base de tests professionnelle couvrant backend (API + services), frontend (composants + utilitaires) et auth — sans casser l'existant.

**Architecture:** Fix de la fixture `client` (la plus haute valeur : corrige 92 échecs préexistants), puis ajout de tests d'API, de services, et de composants frontend en suivant exactement les patterns déjà en place (conftest.py, vitest.config.ts).

**Tech Stack:** pytest + pytest-asyncio, httpx ASGI, SQLite in-memory, Vitest 4 + jsdom, @testing-library/react

---

## Priorisation

| Priorité | Ce que ça couvre | Valeur |
|---|---|---|
| P0 | Fix conftest + auth tests + runs API + test_lab API | Déblocage immédiat des 92 échecs + couverture routes critiques |
| P1 | agent_registry_service + family/skill services | Services les plus référencés |
| P2 | Frontend @testing-library + api-client + composants UI | Couverture frontend de base |

---

## Structure des fichiers ajoutés/modifiés

```
tests/
  conftest.py                           # MODIFY — add X-API-Key header + unauthed_client
  test_auth.py                          # CREATE — auth middleware dedicated tests
  test_api_runs.py                      # CREATE — runs.py + plans.py API tests
  test_api_test_lab.py                  # CREATE — test_lab.py scenario CRUD API tests
  test_service_agent_registry.py        # CREATE — agent_registry_service unit tests
  test_service_family_skill.py          # CREATE — family_service + skill_service unit tests

frontend/
  package.json                          # MODIFY — add @testing-library/react + user-event
  vitest.config.ts                      # MODIFY — add setupFiles for RTL
  src/test-setup.ts                     # CREATE — RTL setup (cleanup)
  src/lib/__tests__/api-client.test.ts  # CREATE — api-client.ts unit tests
  src/lib/test-lab/__tests__/graph-layout.test.ts  # MODIFY — add buildGraph + calcInitialViewport
  src/components/ui/__tests__/status-badge.test.tsx # CREATE — StatusBadge component tests
  src/components/ui/__tests__/stat-card.test.tsx    # CREATE — StatCard component tests
```

---

## Task 1 — Fix conftest.py : header X-API-Key + fixture unauthed_client

**Valeur :** Corrige 92 tests préexistants qui échouent faute de header. La fixture `client` n'envoie pas le header `X-API-Key` alors que le middleware l'exige par défaut.

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1 : Vérifier que les tests actuels échouent sans header**

```bash
python -m pytest tests/test_api_families.py::test_list_families -v 2>&1 | tail -15
```
Expected: `FAILED` avec une erreur liée à l'auth (401) ou ExceptionGroup.

- [ ] **Step 2 : Modifier conftest.py**

Remplacer le bloc `async def client()` par la version ci-dessous, et ajouter `unauthed_client` juste après :

```python
# tests/conftest.py  — remplacer la fixture client existante et ajouter unauthed_client

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-orkestra-api-key"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthed_client() -> AsyncGenerator[AsyncClient, None]:
    """Client sans header auth — pour tester les comportements 401."""
    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 3 : Vérifier que les tests préexistants passent maintenant**

```bash
python -m pytest tests/test_api_families.py -v 2>&1 | tail -20
```
Expected: tous les tests `test_api_families.py` passent (24 tests green).

- [ ] **Step 4 : Vérifier la suite complète**

```bash
python -m pytest tests/ -q --tb=no 2>&1 | tail -5
```
Expected: beaucoup moins d'échecs qu'avant (les 92 tests préexistants doivent maintenant passer).

- [ ] **Step 5 : Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
git add tests/conftest.py
git commit -m "fix(tests): add X-API-Key header to client fixture, add unauthed_client

Fixes 92 pre-existing test failures caused by missing auth header.
Adds unauthed_client fixture for dedicated auth middleware tests."
```

---

## Task 2 — Tests dédiés au middleware d'authentification

**Valeur :** Documenter et protéger le comportement auth (401 sur clé manquante/invalide, bypass sur chemins publics).

**Files:**
- Create: `tests/test_auth.py`

- [ ] **Step 1 : Créer le fichier de test**

```python
# tests/test_auth.py
"""Tests du middleware ApiKeyMiddleware.

Utilise `unauthed_client` (sans header) pour tester les cas 401,
et `client` (avec header valide) pour confirmer les cas 200.
"""


async def test_missing_api_key_returns_401(unauthed_client):
    resp = await unauthed_client.get("/api/families")
    assert resp.status_code == 401


async def test_wrong_api_key_returns_401(unauthed_client):
    resp = await unauthed_client.get(
        "/api/families", headers={"X-API-Key": "completely-wrong-key"}
    )
    assert resp.status_code == 401


async def test_valid_api_key_returns_200(unauthed_client):
    resp = await unauthed_client.get(
        "/api/families", headers={"X-API-Key": "test-orkestra-api-key"}
    )
    assert resp.status_code == 200


async def test_health_endpoint_is_public(unauthed_client):
    """GET /api/health ne doit pas exiger de clé API."""
    resp = await unauthed_client.get("/api/health")
    assert resp.status_code == 200


async def test_options_preflight_bypasses_auth(unauthed_client):
    """Les requêtes OPTIONS (CORS preflight) ne doivent pas être bloquées."""
    resp = await unauthed_client.options("/api/families")
    assert resp.status_code != 401


async def test_error_body_contains_detail(unauthed_client):
    """La réponse 401 doit inclure un champ 'detail'."""
    resp = await unauthed_client.get("/api/families")
    body = resp.json()
    assert "detail" in body


async def test_valid_client_fixture_passes_auth(client):
    """La fixture client standard (avec header) doit accéder aux routes protégées."""
    resp = await client.get("/api/families")
    assert resp.status_code == 200
```

- [ ] **Step 2 : Lancer les tests**

```bash
python -m pytest tests/test_auth.py -v 2>&1 | tail -15
```
Expected: `7 passed`.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_auth.py
git commit -m "test(auth): add dedicated ApiKeyMiddleware tests (401, public paths, CORS)"
```

---

## Task 3 — Tests API : runs.py + plans.py

**Valeur :** Les routes runs/plans orchestrent l'exécution centrale. Zero test aujourd'hui.

**Files:**
- Create: `tests/test_api_runs.py`

- [ ] **Step 1 : Créer le fichier de test**

```python
# tests/test_api_runs.py
"""Tests API pour les routes runs.py et plans.py.

Architecture de test :
- Smoke tests (listes vides, 404 sur ID inexistant) → sans seed DB
- Lifecycle tests → seed minimal via db_session (Run + RunNode + Plan directs)
"""
import pytest
from sqlalchemy import select

from app.models.enums import RunStatus, RunNodeStatus, RunNodeType, PlanStatus, CaseStatus
from app.models.run import Run, RunNode
from app.models.plan import OrchestrationPlan
from app.models.case import Case


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _seed_case(db_session, case_id: str = "case_test") -> Case:
    """Insère un Case minimal en état PLANNING."""
    case = Case(
        id=case_id,
        request_id="req_test",
        case_type="operational",
        business_context="Test context",
        status=CaseStatus.PLANNING,
    )
    db_session.add(case)
    await db_session.flush()
    return case


async def _seed_plan(db_session, case_id: str = "case_test", plan_id: str = "plan_test") -> OrchestrationPlan:
    """Insère un Plan minimal en état VALIDATED."""
    plan = OrchestrationPlan(
        id=plan_id,
        case_id=case_id,
        status=PlanStatus.VALIDATED,
        created_by="test",
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


async def _seed_run(
    db_session,
    run_id: str = "run_test",
    case_id: str = "case_test",
    plan_id: str = "plan_test",
    status: str = RunStatus.CREATED,
) -> Run:
    """Insère un Run minimal."""
    run = Run(id=run_id, case_id=case_id, plan_id=plan_id, status=status)
    db_session.add(run)
    await db_session.flush()
    return run


async def _seed_run_node(db_session, run_id: str = "run_test") -> RunNode:
    node = RunNode(
        run_id=run_id,
        node_type=RunNodeType.SUBAGENT,
        node_ref="agent_test",
        status=RunNodeStatus.PENDING,
        depends_on=[],
        order_index=0,
    )
    db_session.add(node)
    await db_session.flush()
    return node


# ── Smoke tests ────────────────────────────────────────────────────────────────

async def test_list_runs_returns_200_empty(client):
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_run_nonexistent_returns_404(client):
    resp = await client.get("/api/runs/nonexistent_run")
    assert resp.status_code == 404


async def test_get_run_nodes_nonexistent_run(client):
    resp = await client.get("/api/runs/nonexistent_run/nodes")
    # Retourne une liste vide (pas de nodes pour un run inexistant)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_start_run_nonexistent_returns_400(client):
    resp = await client.post("/api/runs/nonexistent_run/start")
    assert resp.status_code == 400


async def test_cancel_run_nonexistent_returns_400(client):
    resp = await client.post("/api/runs/nonexistent_run/cancel")
    assert resp.status_code == 400


# ── Run lifecycle via seed DB ─────────────────────────────────────────────────

async def test_get_run_returns_correct_data(client, db_session):
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await _seed_run(db_session)
    await db_session.commit()

    resp = await client.get("/api/runs/run_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "run_test"
    assert data["case_id"] == "case_test"
    assert data["plan_id"] == "plan_test"
    assert data["status"] == "created"


async def test_list_runs_filter_by_case_id(client, db_session):
    await _seed_case(db_session, "case_a")
    await _seed_plan(db_session, "case_a", "plan_a")
    await _seed_run(db_session, "run_a", "case_a", "plan_a")

    await _seed_case(db_session, "case_b")
    await _seed_plan(db_session, "case_b", "plan_b")
    await _seed_run(db_session, "run_b", "case_b", "plan_b")
    await db_session.commit()

    resp = await client.get("/api/runs?case_id=case_a")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert "run_a" in ids
    assert "run_b" not in ids


async def test_get_run_nodes_returns_seeded_node(client, db_session):
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await _seed_run(db_session)
    await _seed_run_node(db_session)
    await db_session.commit()

    resp = await client.get("/api/runs/run_test/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) == 1
    assert nodes[0]["run_id"] == "run_test"
    assert nodes[0]["node_ref"] == "agent_test"
    assert nodes[0]["status"] == "pending"


async def test_cancel_run_transitions_to_cancelled(client, db_session):
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await _seed_run(db_session, status=RunStatus.RUNNING)
    await db_session.commit()

    resp = await client.post("/api/runs/run_test/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


# ── Plans smoke tests ─────────────────────────────────────────────────────────

async def test_get_plan_nonexistent_returns_404(client):
    resp = await client.get("/api/plans/nonexistent_plan")
    assert resp.status_code == 404


async def test_get_plan_returns_correct_data(client, db_session):
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await db_session.commit()

    resp = await client.get("/api/plans/plan_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "plan_test"
    assert data["case_id"] == "case_test"
    assert data["status"] == "validated"
```

- [ ] **Step 2 : Lancer les tests**

```bash
python -m pytest tests/test_api_runs.py -v 2>&1 | tail -25
```
Expected: tous les tests passent.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_api_runs.py
git commit -m "test(api): add runs.py and plans.py API tests (smoke + lifecycle)"
```

---

## Task 4 — Tests API : test_lab.py (scenarios CRUD + lancement de run)

**Valeur :** Le Test Lab est la feature la plus active. Les routes de scénario n'ont que des tests E2E (non les routes individuelles en isolation).

**Files:**
- Create: `tests/test_api_test_lab.py`

- [ ] **Step 1 : Créer le fichier de test**

```python
# tests/test_api_test_lab.py
"""Tests API pour les routes /api/test-lab (scenarios CRUD + run launch).

Pattern :
- Smoke tests sans données → vérifier les codes de retour de base
- CRUD complet → create / get / patch / delete
- Run launch → mock run_orchestrated_test pour éviter l'appel LLM
"""
from unittest.mock import patch, AsyncMock
import pytest


HEADERS = {"X-API-Key": "test-orkestra-api-key"}

MINIMAL_SCENARIO = {
    "name": "Test Scenario",
    "agent_id": "agent_under_test",
    "input_prompt": "Resolve entity for ACME Corp",
    "assertions": [],
}


# ── Smoke tests ────────────────────────────────────────────────────────────────

async def test_list_scenarios_empty(client):
    resp = await client.get("/api/test-lab/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["total"] == 0


async def test_get_scenario_nonexistent_returns_404(client):
    resp = await client.get("/api/test-lab/scenarios/nonexistent")
    assert resp.status_code == 404


async def test_delete_scenario_nonexistent_returns_404(client):
    resp = await client.delete("/api/test-lab/scenarios/nonexistent")
    assert resp.status_code == 404


async def test_list_runs_empty(client):
    resp = await client.get("/api/test-lab/runs")
    assert resp.status_code == 200


async def test_get_run_nonexistent_returns_404(client):
    resp = await client.get("/api/test-lab/runs/nonexistent")
    assert resp.status_code == 404


# ── Scenario CRUD ─────────────────────────────────────────────────────────────

async def test_create_scenario_minimal(client):
    resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Scenario"
    assert data["agent_id"] == "agent_under_test"
    assert "id" in data


async def test_create_scenario_returns_id_with_prefix(client):
    resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    assert resp.status_code == 201
    assert resp.json()["id"].startswith("scn_")


async def test_get_scenario_after_create(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/test-lab/scenarios/{scenario_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == scenario_id


async def test_list_scenarios_after_create(client):
    await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    await client.post("/api/test-lab/scenarios", json={**MINIMAL_SCENARIO, "name": "Scenario 2"})

    resp = await client.get("/api/test-lab/scenarios")
    assert resp.json()["total"] >= 2


async def test_list_scenarios_filter_by_agent_id(client):
    await client.post("/api/test-lab/scenarios", json={**MINIMAL_SCENARIO, "agent_id": "agent_a"})
    await client.post("/api/test-lab/scenarios", json={**MINIMAL_SCENARIO, "agent_id": "agent_b"})

    resp = await client.get("/api/test-lab/scenarios?agent_id=agent_a")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["agent_id"] == "agent_a" for item in items)


async def test_update_scenario_name(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/test-lab/scenarios/{scenario_id}",
        json={"name": "Updated Name"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Name"


async def test_delete_scenario_returns_204(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/test-lab/scenarios/{scenario_id}")
    assert del_resp.status_code == 204


async def test_get_deleted_scenario_returns_404(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]
    await client.delete(f"/api/test-lab/scenarios/{scenario_id}")

    get_resp = await client.get(f"/api/test-lab/scenarios/{scenario_id}")
    assert get_resp.status_code == 404


async def test_create_scenario_with_assertions(client):
    payload = {
        **MINIMAL_SCENARIO,
        "assertions": [
            {"type": "tool_called", "target": "search_tool", "critical": True}
        ],
    }
    resp = await client.post("/api/test-lab/scenarios", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["assertions"]) == 1
    assert data["assertions"][0]["type"] == "tool_called"


# ── Run launch (mocked) ────────────────────────────────────────────────────────

async def test_launch_run_creates_run_record(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    with patch(
        "app.services.test_lab.orchestrator_agent.run_orchestrated_test",
        new_callable=AsyncMock,
    ):
        run_resp = await client.post(f"/api/test-lab/scenarios/{scenario_id}/run")

    assert run_resp.status_code == 200
    data = run_resp.json()
    assert "run_id" in data
    assert data["run_id"].startswith("trun_")


async def test_launch_run_on_nonexistent_scenario_returns_404(client):
    resp = await client.post("/api/test-lab/scenarios/nonexistent/run")
    assert resp.status_code == 404
```

- [ ] **Step 2 : Lancer les tests**

```bash
python -m pytest tests/test_api_test_lab.py -v 2>&1 | tail -30
```
Expected: tous passent.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_api_test_lab.py
git commit -m "test(api): add test_lab.py scenario CRUD and run launch API tests"
```

---

## Task 5 — Tests service : agent_registry_service

**Valeur :** Le service le plus référencé du projet — CRUD d'agents, enrichissement, stats. Aucun test aujourd'hui.

**Files:**
- Create: `tests/test_service_agent_registry.py`

- [ ] **Step 1 : Créer le fichier de test**

```python
# tests/test_service_agent_registry.py
"""Tests unitaires pour agent_registry_service.

Utilise la DB in-memory via db_session.
Chaque test est isolé : setup_db (autouse) recrée le schéma.
"""
import pytest

from app.schemas.agent import AgentCreate, AgentUpdate, AgentStatusUpdate
from app.schemas.family import FamilyCreate
from app.services import agent_registry_service, family_service
from app.models.enums import AgentStatus, Criticality, CostProfile


# ── Fixtures ───────────────────────────────────────────────────────────────────

async def _create_family(db_session, family_id: str = "test_family") -> None:
    data = FamilyCreate(id=family_id, label="Test Family")
    await family_service.create_family(db_session, data)
    await db_session.commit()


def _agent_payload(**overrides) -> AgentCreate:
    return AgentCreate(
        id=overrides.get("id", "agent_test"),
        name=overrides.get("name", "Test Agent"),
        family_id=overrides.get("family_id", "test_family"),
        purpose=overrides.get("purpose", "Test purpose"),
        **{k: v for k, v in overrides.items() if k not in ("id", "name", "family_id", "purpose")},
    )


# ── create_agent ───────────────────────────────────────────────────────────────

async def test_create_agent_returns_agent(db_session):
    await _create_family(db_session)
    agent = await agent_registry_service.create_agent(db_session, _agent_payload())
    assert agent.id == "agent_test"
    assert agent.name == "Test Agent"
    assert agent.family_id == "test_family"
    assert agent.status == AgentStatus.DRAFT


async def test_create_agent_defaults_criticality_medium(db_session):
    await _create_family(db_session)
    agent = await agent_registry_service.create_agent(db_session, _agent_payload())
    assert agent.criticality == Criticality.MEDIUM


async def test_create_agent_duplicate_id_raises(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()
    with pytest.raises(Exception):
        await agent_registry_service.create_agent(db_session, _agent_payload())


async def test_create_agent_unknown_family_raises(db_session):
    with pytest.raises(ValueError, match="family"):
        await agent_registry_service.create_agent(
            db_session, _agent_payload(family_id="nonexistent_family")
        )


# ── get_agent ─────────────────────────────────────────────────────────────────

async def test_get_agent_returns_agent(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    agent = await agent_registry_service.get_agent(db_session, "agent_test")
    assert agent is not None
    assert agent.id == "agent_test"


async def test_get_agent_nonexistent_returns_none(db_session):
    agent = await agent_registry_service.get_agent(db_session, "nonexistent")
    assert agent is None


# ── list_agents ────────────────────────────────────────────────────────────────

async def test_list_agents_returns_all(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a1", name="Agent 1"))
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a2", name="Agent 2"))
    await db_session.commit()

    agents, total = await agent_registry_service.list_agents(db_session)
    assert total >= 2
    ids = [a.id for a in agents]
    assert "a1" in ids
    assert "a2" in ids


async def test_list_agents_filter_by_family(db_session):
    await _create_family(db_session, "fam_a")
    await _create_family(db_session, "fam_b")
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a1", family_id="fam_a"))
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a2", family_id="fam_b"))
    await db_session.commit()

    agents, total = await agent_registry_service.list_agents(db_session, family="fam_a")
    assert total == 1
    assert agents[0].id == "a1"


async def test_list_agents_filter_by_status(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a_draft", status=AgentStatus.DRAFT))
    await db_session.commit()

    agents, total = await agent_registry_service.list_agents(db_session, status="draft")
    assert total >= 1
    assert all(a.status == AgentStatus.DRAFT for a in agents)


async def test_list_agents_empty(db_session):
    agents, total = await agent_registry_service.list_agents(db_session)
    assert total == 0
    assert agents == []


# ── update_agent ───────────────────────────────────────────────────────────────

async def test_update_agent_name(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    updated = await agent_registry_service.update_agent(
        db_session, "agent_test", AgentUpdate(name="Updated Name")
    )
    assert updated.name == "Updated Name"


async def test_update_agent_nonexistent_raises(db_session):
    with pytest.raises(ValueError):
        await agent_registry_service.update_agent(
            db_session, "nonexistent", AgentUpdate(name="x")
        )


# ── update_agent_status ────────────────────────────────────────────────────────

async def test_update_agent_status_draft_to_designed(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    updated = await agent_registry_service.update_agent_status(
        db_session, "agent_test", AgentStatus.DESIGNED, "ready for design"
    )
    assert updated.status == AgentStatus.DESIGNED


# ── delete_agent ───────────────────────────────────────────────────────────────

async def test_delete_agent_removes_it(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    await agent_registry_service.delete_agent(db_session, "agent_test")
    await db_session.commit()

    agent = await agent_registry_service.get_agent(db_session, "agent_test")
    assert agent is None


# ── enrich_agent ───────────────────────────────────────────────────────────────

async def test_enrich_agent_includes_family(db_session):
    await _create_family(db_session)
    agent = await agent_registry_service.create_agent(db_session, _agent_payload())
    await db_session.commit()

    enriched = await agent_registry_service.enrich_agent(db_session, agent)
    assert isinstance(enriched, dict)
    assert enriched["id"] == "agent_test"


# ── get_registry_stats ─────────────────────────────────────────────────────────

async def test_get_registry_stats_zero_initially(db_session):
    stats = await agent_registry_service.get_registry_stats(db_session)
    assert stats.total_agents == 0


async def test_get_registry_stats_counts_agents(db_session):
    await _create_family(db_session)
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a1"))
    await agent_registry_service.create_agent(db_session, _agent_payload(id="a2"))
    await db_session.commit()

    stats = await agent_registry_service.get_registry_stats(db_session)
    assert stats.total_agents == 2
```

- [ ] **Step 2 : Lancer les tests**

```bash
python -m pytest tests/test_service_agent_registry.py -v 2>&1 | tail -30
```
Expected: tous passent.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_service_agent_registry.py
git commit -m "test(services): add agent_registry_service unit tests (CRUD + status + stats)"
```

---

## Task 6 — Tests service : family_service + skill_service

**Valeur :** Les familles et skills sont les fondations du catalog. Aucun test de service direct aujourd'hui.

**Files:**
- Create: `tests/test_service_family_skill.py`

- [ ] **Step 1 : Lire les signatures de skill_service**

```bash
grep -n "^async def\|^def " /Users/mbensass/projetPreso/multiAgents/orkestra/app/services/skill_service.py | head -20
```

- [ ] **Step 2 : Créer le fichier de test**

```python
# tests/test_service_family_skill.py
"""Tests unitaires pour family_service et skill_service.

Les tests de famille couvrent : CRUD, versioning, archivage, suppression.
Les tests de skill couvrent : CRUD, association famille.
"""
import pytest

from app.schemas.family import FamilyCreate, FamilyUpdate
from app.schemas.skill import SkillCreate, SkillUpdate
from app.services import family_service, skill_service
from app.models.enums import FamilyStatus


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


async def test_get_family_returns_family(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fam3", label="F3"))
    await db_session.commit()

    fam = await family_service.get_family(db_session, "fam3")
    assert fam is not None
    assert fam.id == "fam3"


async def test_get_family_nonexistent_returns_none(db_session):
    fam = await family_service.get_family(db_session, "does_not_exist")
    assert fam is None


async def test_list_families_returns_all(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fa", label="FA"))
    await family_service.create_family(db_session, FamilyCreate(id="fb", label="FB"))
    await db_session.commit()

    items, total = await family_service.list_families(db_session)
    assert total >= 2


async def test_update_family_label(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fam_upd", label="Old Label"))
    await db_session.commit()

    updated = await family_service.update_family(
        db_session, "fam_upd", FamilyUpdate(label="New Label")
    )
    assert updated.label == "New Label"


async def test_update_family_nonexistent_raises(db_session):
    with pytest.raises(ValueError):
        await family_service.update_family(
            db_session, "nonexistent", FamilyUpdate(label="x")
        )


async def test_archive_family_changes_status(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fam_arc", label="Arc"))
    await db_session.commit()

    archived = await family_service.archive_family(db_session, "fam_arc")
    assert archived.status == FamilyStatus.archived


async def test_is_family_active_returns_true(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fam_act", label="Act"))
    await db_session.commit()

    result = await family_service.is_family_active(db_session, "fam_act")
    assert result is True


async def test_is_family_active_returns_false_after_archive(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fam_inact", label="Inact"))
    await db_session.commit()
    await family_service.archive_family(db_session, "fam_inact")
    await db_session.commit()

    result = await family_service.is_family_active(db_session, "fam_inact")
    assert result is False


async def test_get_family_detail_includes_skills(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fam_det", label="Det"))
    await db_session.commit()

    detail = await family_service.get_family_detail(db_session, "fam_det")
    assert detail is not None
    assert "skills" in detail


async def test_get_family_history_empty_initially(db_session):
    await family_service.create_family(db_session, FamilyCreate(id="fam_hist", label="Hist"))
    await db_session.commit()

    history = await family_service.get_family_history(db_session, "fam_hist")
    assert isinstance(history, list)


# ═══════════════════════════════ skill_service ════════════════════════════════

async def _make_skill_payload(skill_id: str = "skill_test", **overrides) -> SkillCreate:
    from app.schemas.skill import SkillCreate
    return SkillCreate(
        id=skill_id,
        label=overrides.get("label", "Test Skill"),
        category=overrides.get("category", "analysis"),
        description=overrides.get("description", "A test skill"),
    )


async def test_create_skill_basic(db_session):
    data = await _make_skill_payload()
    skill = await skill_service.create_skill(db_session, data)
    assert skill.id == "skill_test"
    assert skill.label == "Test Skill"


async def test_get_skill_returns_skill(db_session):
    data = await _make_skill_payload(skill_id="sk_get")
    await skill_service.create_skill(db_session, data)
    await db_session.commit()

    skill = await skill_service.get_skill(db_session, "sk_get")
    assert skill is not None
    assert skill.id == "sk_get"


async def test_get_skill_nonexistent_returns_none(db_session):
    skill = await skill_service.get_skill(db_session, "nonexistent_skill")
    assert skill is None


async def test_list_skills_returns_all(db_session):
    await skill_service.create_skill(db_session, await _make_skill_payload("sk1"))
    await skill_service.create_skill(db_session, await _make_skill_payload("sk2"))
    await db_session.commit()

    skills, total = await skill_service.list_skills(db_session)
    assert total >= 2


async def test_update_skill_label(db_session):
    await skill_service.create_skill(db_session, await _make_skill_payload("sk_upd"))
    await db_session.commit()

    from app.schemas.skill import SkillUpdate
    updated = await skill_service.update_skill(db_session, "sk_upd", SkillUpdate(label="Updated"))
    assert updated.label == "Updated"


async def test_delete_skill_removes_it(db_session):
    await skill_service.create_skill(db_session, await _make_skill_payload("sk_del"))
    await db_session.commit()

    await skill_service.delete_skill(db_session, "sk_del")
    await db_session.commit()

    skill = await skill_service.get_skill(db_session, "sk_del")
    assert skill is None
```

- [ ] **Step 3 : Vérifier les signatures de SkillCreate/SkillUpdate**

```bash
grep -n "class SkillCreate\|class SkillUpdate\|class SkillOut" /Users/mbensass/projetPreso/multiAgents/orkestra/app/schemas/skill.py | head -10
```

Ajuster les champs du payload `_make_skill_payload()` si nécessaire (category, description).

- [ ] **Step 4 : Lancer les tests**

```bash
python -m pytest tests/test_service_family_skill.py -v 2>&1 | tail -30
```
Expected: tous passent.

- [ ] **Step 5 : Commit**

```bash
git add tests/test_service_family_skill.py
git commit -m "test(services): add family_service and skill_service unit tests"
```

---

## Task 7 — Frontend : installer @testing-library/react + setup RTL

**Valeur :** Actuellement aucun test de composant React n'est possible (package absent). Cette task débloque les Tasks 8-10.

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vitest.config.ts`
- Create: `frontend/src/test-setup.ts`

- [ ] **Step 1 : Installer les packages**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npm install -D @testing-library/react @testing-library/user-event @testing-library/jest-dom
```
Expected: packages ajoutés dans `devDependencies`.

- [ ] **Step 2 : Créer le fichier de setup RTL**

```typescript
// frontend/src/test-setup.ts
import '@testing-library/jest-dom';
```

- [ ] **Step 3 : Modifier vitest.config.ts pour pointer sur setupFiles**

```typescript
// frontend/vitest.config.ts  — version complète
import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    include: [
      'src/**/__tests__/**/*.test.ts',
      'src/**/__tests__/**/*.test.tsx',
      'src/**/*.test.ts',
      'src/**/*.test.tsx',
    ],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
});
```

- [ ] **Step 4 : Vérifier que les tests existants passent toujours**

```bash
npm test 2>&1 | tail -10
```
Expected: `18 passed`.

- [ ] **Step 5 : Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/src/test-setup.ts
git commit -m "test(frontend): install @testing-library/react and configure vitest setupFiles"
```

---

## Task 8 — Frontend : tests unitaires api-client.ts

**Valeur :** Le client API est utilisé par toutes les pages. Aucun test. Risque réel sur la gestion d'erreurs.

**Files:**
- Create: `frontend/src/lib/__tests__/api-client.test.ts`

- [ ] **Step 1 : Créer le fichier de test**

```typescript
// frontend/src/lib/__tests__/api-client.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { request, ApiError } from '../api-client';

// Helpers pour mocker fetch
function mockFetch(status: number, body: unknown, ok = status < 400) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
  });
}

describe('ApiError', () => {
  it('should have name ApiError', () => {
    const err = new ApiError(404, 'Not found');
    expect(err.name).toBe('ApiError');
  });

  it('should expose status and message', () => {
    const err = new ApiError(422, 'Validation error');
    expect(err.status).toBe(422);
    expect(err.message).toBe('Validation error');
  });

  it('should be instanceof Error', () => {
    const err = new ApiError(500, 'Server error');
    expect(err).toBeInstanceOf(Error);
  });
});

describe('request()', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('returns parsed JSON on 200', async () => {
    global.fetch = mockFetch(200, { id: 'abc', name: 'Test' });
    const result = await request<{ id: string; name: string }>('/api/agents');
    expect(result).toEqual({ id: 'abc', name: 'Test' });
  });

  it('returns undefined on 204', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.reject(new Error('No body')),
    });
    const result = await request('/api/agents/test');
    expect(result).toBeUndefined();
  });

  it('throws ApiError with string detail on 404', async () => {
    global.fetch = mockFetch(404, { detail: 'Agent not found' }, false);
    await expect(request('/api/agents/nonexistent')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'Agent not found',
    });
  });

  it('throws ApiError with joined message on validation error (array detail)', async () => {
    global.fetch = mockFetch(422, {
      detail: [
        { msg: 'field required', loc: ['body', 'name'] },
        { msg: 'too short', loc: ['body', 'id'] },
      ],
    }, false);
    const err = await request('/api/agents').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toContain('field required');
    expect(err.message).toContain('too short');
  });

  it('falls back to statusText when body has no detail', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({}),
    });
    const err = await request('/api/crash').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe('Internal Server Error');
  });

  it('sends Content-Type application/json', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('/api/test');
    const [, opts] = mockFn.mock.calls[0];
    expect(opts.headers['Content-Type']).toBe('application/json');
  });

  it('merges custom headers', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('/api/test', { headers: { 'X-Custom': 'value' } });
    const [, opts] = mockFn.mock.calls[0];
    expect(opts.headers['X-Custom']).toBe('value');
    expect(opts.headers['Content-Type']).toBe('application/json');
  });

  it('sends absolute URL as-is', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('https://external.api.com/resource');
    const [url] = mockFn.mock.calls[0];
    expect(url).toBe('https://external.api.com/resource');
  });

  it('prepends API_BASE to relative paths', async () => {
    const mockFn = mockFetch(200, {});
    global.fetch = mockFn;
    await request('/api/families');
    const [url] = mockFn.mock.calls[0];
    expect(url).toContain('/api/families');
  });
});
```

- [ ] **Step 2 : Lancer les tests**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend && npm test 2>&1 | tail -15
```
Expected: `27+ passed` (18 existants + 9+ nouveaux).

- [ ] **Step 3 : Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
git add frontend/src/lib/__tests__/api-client.test.ts
git commit -m "test(frontend): add api-client.ts unit tests (ApiError, request success/error paths)"
```

---

## Task 9 — Frontend : tests buildGraph + calcInitialViewport

**Valeur :** `buildGraph()` est la fonction la plus complexe de graph-layout.ts (dagre layout, node/edge construction). Actuellement 0 test dessus.

**Files:**
- Modify: `frontend/src/lib/test-lab/__tests__/graph-layout.test.ts`

- [ ] **Step 1 : Appliquer le diff — ajouter les blocs describe manquants en fin de fichier**

Ajouter après le dernier `describe` existant (à la fin du fichier) :

```typescript
import { buildGraph, calcInitialViewport } from '../graph-layout';
import type { TestRunEvent, TestRun } from '../types';

// ── buildGraph() ───────────────────────────────────────────────────────────────

function makeRun(overrides: Partial<TestRun> = {}): TestRun {
  return {
    id: 'trun_test',
    scenario_id: 'scn_test',
    agent_id: 'identity_resolution_agent',
    status: 'completed',
    verdict: 'passed',
    score: 100,
    duration_ms: 1200,
    final_output: null,
    iteration_count: 2,
    error_message: null,
    created_at: '2026-04-13T10:00:00Z',
    updated_at: '2026-04-13T10:00:01Z',
    ...overrides,
  } as TestRun;
}

function makeEvent(
  event_type: string,
  phase: string,
  timestamp = '2026-04-13T10:00:00.000Z',
  details: Record<string, unknown> = {},
): TestRunEvent {
  return {
    id: `ev_${event_type}`,
    run_id: 'trun_test',
    event_type,
    phase,
    message: null,
    details,
    timestamp,
  } as unknown as TestRunEvent;
}

describe('buildGraph()', () => {
  it('always includes orchestrator node', () => {
    const { nodes } = buildGraph([], makeRun(), []);
    expect(nodes.some((n) => n.id === 'orchestrator')).toBe(true);
  });

  it('nodes get non-zero positions from dagre', () => {
    const events = [
      makeEvent('orchestrator_started', 'orchestrator'),
      makeEvent('phase_started', 'preparation'),
    ];
    const { nodes } = buildGraph(events, makeRun(), []);
    const orch = nodes.find((n) => n.id === 'orchestrator')!;
    expect(typeof orch.position.x).toBe('number');
    expect(typeof orch.position.y).toBe('number');
  });

  it('creates edge from tool_call event to target phase', () => {
    const events = [
      makeEvent('orchestrator_tool_call', 'orchestrator', '2026-04-13T10:00:00Z', {
        tool_name: 'prepare_test_scenario',
      }),
      makeEvent('phase_started', 'preparation'),
    ];
    const { edges } = buildGraph(events, makeRun(), []);
    expect(edges.some((e) => e.source === 'orchestrator' && e.target === 'preparation')).toBe(true);
  });

  it('does not duplicate edges for repeated tool calls', () => {
    const events = [
      makeEvent('orchestrator_tool_call', 'orchestrator', '2026-04-13T10:00:00Z', {
        tool_name: 'execute_target_agent',
      }),
      makeEvent('orchestrator_tool_call', 'orchestrator', '2026-04-13T10:00:01Z', {
        tool_name: 'execute_target_agent',
      }),
      makeEvent('phase_started', 'runtime'),
    ];
    const { edges } = buildGraph(events, makeRun(), []);
    const runtimeEdges = edges.filter((e) => e.target === 'runtime');
    expect(runtimeEdges.length).toBe(1);
  });

  it('falls back to sequential edges when no tool call events', () => {
    const events = [
      makeEvent('orchestrator_started', 'orchestrator'),
      makeEvent('phase_started', 'preparation'),
    ];
    const { edges } = buildGraph(events, makeRun(), []);
    expect(edges.length).toBeGreaterThan(0);
  });

  it('runtime node uses run.agent_id as label', () => {
    const events = [makeEvent('phase_started', 'runtime')];
    const { nodes } = buildGraph(events, makeRun({ agent_id: 'chat_agent' }), []);
    const runtime = nodes.find((n) => n.id === 'runtime');
    expect(runtime?.data.subLabel).toBe('chat_agent');
  });

  it('report node includes verdict and score', () => {
    const events = [makeEvent('report_phase_started', 'report')];
    const { nodes } = buildGraph(events, makeRun({ verdict: 'passed', score: 95 }), []);
    const report = nodes.find((n) => n.id === 'report');
    expect(report?.data.verdict).toBe('passed');
    expect(report?.data.score).toBe(95);
  });

  it('maps verdict phase to report node', () => {
    const events = [
      makeEvent('phase_started', 'verdict'),
    ];
    const { nodes } = buildGraph(events, makeRun(), []);
    // 'verdict' phase maps to 'report' bucket — should not create separate node
    const verdictNode = nodes.find((n) => n.id === 'verdict');
    expect(verdictNode).toBeUndefined();
  });
});

// ── calcInitialViewport() ──────────────────────────────────────────────────────

describe('calcInitialViewport()', () => {
  it('returns default when nodes array is empty', () => {
    const vp = calcInitialViewport([], 800, 600);
    expect(vp).toEqual({ x: 0, y: 0, zoom: 1 });
  });

  it('zoom does not exceed 1.5', () => {
    const nodes = [{ id: 'n', position: { x: 0, y: 0 }, width: 10, height: 10 }] as any;
    const vp = calcInitialViewport(nodes, 2000, 2000);
    expect(vp.zoom).toBeLessThanOrEqual(1.5);
  });

  it('zoom is greater than 0', () => {
    const nodes = [
      { id: 'a', position: { x: 0, y: 0 }, width: 210, height: 108 },
      { id: 'b', position: { x: 340, y: 0 }, width: 210, height: 108 },
    ] as any;
    const vp = calcInitialViewport(nodes, 1280, 720);
    expect(vp.zoom).toBeGreaterThan(0);
  });

  it('centers the graph — x and y are finite numbers', () => {
    const nodes = [
      { id: 'n', position: { x: 100, y: 50 }, width: 210, height: 108 },
    ] as any;
    const vp = calcInitialViewport(nodes, 1280, 720);
    expect(Number.isFinite(vp.x)).toBe(true);
    expect(Number.isFinite(vp.y)).toBe(true);
  });
});
```

- [ ] **Step 2 : Lancer les tests**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend && npm test 2>&1 | tail -10
```
Expected: `45+ passed`.

- [ ] **Step 3 : Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
git add frontend/src/lib/test-lab/__tests__/graph-layout.test.ts
git commit -m "test(frontend): add buildGraph and calcInitialViewport tests"
```

---

## Task 10 — Frontend : tests composants UI (StatusBadge + StatCard)

**Valeur :** Composants utilisés sur toutes les pages. Aucun test. Risque de régression sur mapping de couleurs.

**Files:**
- Create: `frontend/src/components/ui/__tests__/status-badge.test.tsx`
- Create: `frontend/src/components/ui/__tests__/stat-card.test.tsx`

- [ ] **Step 1 : Créer le dossier et le test StatusBadge**

```bash
mkdir -p /Users/mbensass/projetPreso/multiAgents/orkestra/frontend/src/components/ui/__tests__
```

```tsx
// frontend/src/components/ui/__tests__/status-badge.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../status-badge';

describe('StatusBadge', () => {
  it('renders the status text', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByRole('status')).toHaveTextContent('running');
  });

  it('replaces underscores with spaces', () => {
    render(<StatusBadge status="waiting_review" />);
    expect(screen.getByRole('status')).toHaveTextContent('waiting review');
  });

  it('has accessible aria-label with readable status', () => {
    render(<StatusBadge status="passed_with_warnings" />);
    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      'Status: passed with warnings',
    );
  });

  it('applies known-status CSS class (not default fallback)', () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByRole('status');
    // completed = bg-ork-green — ensure not the default dim class
    expect(badge.className).not.toContain('bg-ork-dim');
    expect(badge.className).toContain('ork-green');
  });

  it('applies default fallback class for unknown status', () => {
    render(<StatusBadge status="totally_unknown_status" />);
    const badge = screen.getByRole('status');
    expect(badge.className).toContain('bg-ork-dim');
  });

  it('renders "failed" in red class', () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByRole('status').className).toContain('ork-red');
  });

  it('renders "running" in cyan class', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByRole('status').className).toContain('ork-cyan');
  });

  it('renders "pending" in amber class', () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByRole('status').className).toContain('ork-amber');
  });
});
```

- [ ] **Step 2 : Créer le test StatCard**

```tsx
// frontend/src/components/ui/__tests__/stat-card.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatCard } from '../stat-card';

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard label="Total Agents" value={42} />);
    expect(screen.getByText('Total Agents')).toBeDefined();
    expect(screen.getByText('42')).toBeDefined();
  });

  it('renders sub text when provided', () => {
    render(<StatCard label="Agents" value={5} sub="active in prod" />);
    expect(screen.getByText('active in prod')).toBeDefined();
  });

  it('does not render sub element when sub is omitted', () => {
    render(<StatCard label="Agents" value={5} />);
    expect(screen.queryByText(/active/)).toBeNull();
  });

  it('applies cyan border by default', () => {
    const { container } = render(<StatCard label="L" value="V" />);
    const panel = container.firstChild as HTMLElement;
    expect(panel.className).toContain('ork-cyan');
  });

  it('applies green border when accent=green', () => {
    const { container } = render(<StatCard label="L" value="V" accent="green" />);
    const panel = container.firstChild as HTMLElement;
    expect(panel.className).toContain('ork-green');
  });

  it('applies red border when accent=red', () => {
    const { container } = render(<StatCard label="L" value="V" accent="red" />);
    const panel = container.firstChild as HTMLElement;
    expect(panel.className).toContain('ork-red');
  });

  it('renders string value correctly', () => {
    render(<StatCard label="Status" value="healthy" />);
    expect(screen.getByText('healthy')).toBeDefined();
  });
});
```

- [ ] **Step 3 : Lancer tous les tests frontend**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend && npm test 2>&1 | tail -15
```
Expected: `60+ passed`.

- [ ] **Step 4 : Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
git add frontend/src/components/ui/__tests__/
git commit -m "test(frontend): add StatusBadge and StatCard component tests"
```

---

## Task 11 — Vérification finale + rapport de couverture

- [ ] **Step 1 : Lancer la suite backend complète**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```
Expected: beaucoup plus de tests passent qu'avant (cible : <10 échecs résiduels, tous préexistants ou liés à dépendances externes).

- [ ] **Step 2 : Lancer la suite frontend complète**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend && npm test 2>&1 | tail -10
```
Expected: `60+ passed`.

- [ ] **Step 3 : Documenter les gaps résiduels**

Lister dans un commentaire de commit les tests intentionnellement non couverts :
- Streaming SSE Redis (nécessite infra Redis + refactor DI)
- RunGraph animé (setTimeout/RAF non testables sans refactor)
- agentscope LLM direct (service externe)
- Celery tasks (broker isolé nécessaire)

- [ ] **Step 4 : Commit final**

```bash
git add -A
git commit -m "test: complete comprehensive test strategy — tasks 1-10 done

Backend: auth tests, runs/plans API, test_lab API, agent_registry_service,
family_service, skill_service. Frontend: @testing-library/react setup,
api-client tests, buildGraph/calcInitialViewport, StatusBadge, StatCard."
```

---

## Gap Report (volontairement exclus)

| Zone | Raison d'exclusion | Ce qui serait nécessaire |
|---|---|---|
| SSE streaming /runs/{id}/stream | Redis réel requis | Refactor DI pour injecter publisher mockable |
| RunGraph animé (setTimeout/RAF) | RAF = browser API uniquement | Refactor vers AnimationController injectable |
| agentscope / LLM calls | Service externe non mockable sans DI | Abstract LLMClient protocol + mock |
| Celery tasks (test_lab.py) | Broker isolé requis | Celery eager mode ou pytest-celery |
| AgentForm multi-step (cascading fetch) | Fetch calls enchaînés complexes | MSW (Mock Service Worker) pour intercept réseau |
| E2E Playwright / Cypress | Non installé | Playwright ou Cypress + backend seedé |

---

## Commandes d'exécution

```bash
# Backend — tous les tests
python -m pytest tests/ -q

# Backend — sous-ensemble ciblé
python -m pytest tests/test_auth.py tests/test_api_runs.py tests/test_api_test_lab.py -v

# Backend — avec couverture
python -m pytest tests/ --cov=app --cov-report=term-missing -q

# Frontend — run unique
cd frontend && npm test

# Frontend — watch mode
cd frontend && npm run test:watch

# Frontend — sous-ensemble
cd frontend && npx vitest run src/lib/__tests__/

# Tout lancer depuis la racine
python -m pytest tests/ -q && cd frontend && npm test
```
