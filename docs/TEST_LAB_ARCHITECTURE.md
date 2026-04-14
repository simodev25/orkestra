> **Internal reference document.** This is the v0.2 design document written during development (in French). The user-facing documentation is at [`docs/test-lab.md`](test-lab.md).
>
> This document remains accurate as an implementation reference but is not the primary docs entry point.

# Test Lab -- Documentation Technique Complete

**Version :** v0.2 (post-refactor multi-agent)
**Scope :** Architecture fonctionnelle, code, MCP, data flow, API, UI

---

## Table des matieres

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture fonctionnelle](#2-architecture-fonctionnelle)
3. [Les acteurs (Agents, SubAgents, Orchestrator)](#3-les-acteurs)
4. [Flow d'execution d'un test run](#4-flow-dexecution)
5. [Modeles de donnees](#5-modeles-de-donnees)
6. [API REST](#6-api-rest)
7. [Integration MCP](#7-integration-mcp)
8. [Configuration dynamique (Test Lab Config)](#8-configuration-dynamique)
9. [UI -- Parcours utilisateur](#9-ui)
10. [Observabilite (events, SSE, logs)](#10-observabilite)
11. [Chat interactif avec l'OrchestratorAgent](#11-chat-interactif)
12. [Points de fragilite et ameliorations](#12-fragilite)

---

## 1. Vue d'ensemble

Le **Test Lab** d'Orkestra est un systeme de test d'agents LLM. Il permet de :

1. **Definir des scenarios de test** (input prompt, assertions attendues, tags)
2. **Executer l'agent sous test** en conditions reelles (vrai LLM, vrais tools MCP)
3. **Evaluer le resultat** via un systeme **multi-agent** (OrchestratorAgent + SubAgents specialises)
4. **Persister** les runs, events, verdicts, scores
5. **Discuter** avec l'OrchestratorAgent apres le run pour des follow-ups

### Particularite architecturale

Contrairement a un test framework classique (assertion engines deterministes), le Test Lab est **100% LLM-driven** :

- L'evaluation du verdict est faite par un **JudgeSubAgent** (LLM)
- La generation de scenarios par un **ScenarioSubAgent** (LLM)
- La conformite governance par un **PolicySubAgent** (LLM)
- La proposition de tests de robustesse par un **RobustnessSubAgent** (LLM)
- Le tout coordonne par un **OrchestratorAgent** (ReActAgent) qui decide l'ordre des appels via des tools

Les deterministes (scoring, assertions, diagnostics) existent dans le code (`scoring.py`, `assertion_engine.py`, `diagnostic_engine.py`) mais ne sont **plus appeles** dans le pipeline actuel -- tout passe par les LLMs.

---

## 2. Architecture fonctionnelle

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 14)                        │
│  /test-lab          Test Lab main page (Scenarios list + Chat tab)   │
│  /test-lab/config   SubAgents configuration (models, prompts)        │
│  /test-lab/scenarios/new    Create a scenario                        │
│  /test-lab/scenarios/{id}   View scenario details                    │
│  /test-lab/runs/{id}        View run details + chat with orchestrator│
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST + SSE
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend (port 8200)                    │
│                                                                      │
│   /api/test-lab/scenarios            CRUD scenarios                  │
│   /api/test-lab/scenarios/{id}/run   Launch a run (async task)       │
│   /api/test-lab/runs/{id}            Get run state                   │
│   /api/test-lab/runs/{id}/events     Get all events of a run         │
│   /api/test-lab/runs/{id}/stream     SSE live stream of events       │
│   /api/test-lab/runs/{id}/chat       Chat with OrchestratorAgent     │
│   /api/test-lab/config               GET/PUT dynamic config          │
│                                                                      │
│   Services:                                                          │
│   ├─ scenario_service.py      CRUD on TestScenario                   │
│   ├─ orchestrator_agent.py    Multi-agent runner + chat              │
│   ├─ target_agent_runner.py   Real agent under test execution       │
│   ├─ execution_engine.py      DB write helpers (events, runs)        │
│   ├─ scoring.py               (deterministic, not used in v0.2)      │
│   ├─ assertion_engine.py      (deterministic, not used in v0.2)      │
│   ├─ diagnostic_engine.py     (deterministic, not used in v0.2)      │
│   └─ agent_summary.py         Aggregated test stats per agent        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌─────────────┐  ┌────────────┐  ┌──────────────┐
        │  PostgreSQL  │  │   Redis    │  │  Ollama LLM  │
        │  (scenarios,  │  │  (pub/sub  │  │ (host.docker │
        │   runs,       │  │   for SSE) │  │  .internal)  │
        │   events)     │  │            │  │              │
        └─────────────┘  └────────────┘  └──────────────┘
                                                │
                                                ▼
                                        ┌──────────────┐
                                        │  Obot MCP    │
                                        │  servers     │
                                        │  (via Obot   │
                                        │   catalog)   │
                                        └──────────────┘
```

---

## 3. Les acteurs

### 3.1 Target Agent (l'agent sous test)

C'est **l'agent que tu testes** (ex: `identity_resolution_agent`). Il est defini dans le registre Agents :

- `name`, `purpose`, `family_id`, `skill_ids`, `allowed_mcps`
- `prompt_content` (prompt systeme)
- `llm_provider`, `llm_model` (optionnel, sinon le default platform)
- `forbidden_effects` (contraintes governance)

Son execution reelle passe par :

```python
# app/services/test_lab/target_agent_runner.py

async def run_target_agent(
    db: AsyncSession,
    agent_id: str,
    agent_version: str,
    input_prompt: str,
    timeout_seconds: int,
    max_iterations: int,
) -> TargetAgentResult:
    # 1. Load agent definition from registry
    agent_def = await agent_registry_service.get_agent(db, agent_id)

    # 2. Get MCP tools (Obot + local)
    tools = get_tools_for_agent(agent_def)

    # 3. Create the REAL ReActAgent (AgentScope)
    react_agent = await create_agentscope_agent(
        agent_def, db, tools, max_iters=max_iterations
    )

    # 4. Run it with the scenario input
    response = await asyncio.wait_for(
        react_agent(Msg("user", input_prompt, "user")),
        timeout=timeout_seconds,
    )

    # 5. Return structured result
    return TargetAgentResult(
        status="completed", final_output=...,
        duration_ms=..., iteration_count=...,
        message_history=..., tool_calls=...
    )
```

### 3.2 SubAgents (les evaluateurs LLM)

4 SubAgents specialises, crees **persistants** au debut de chaque run (pas recrees a chaque appel) :

| SubAgent | Role | Config key | Prompt template |
|---|---|---|---|
| **ScenarioSubAgent** | Prepare un plan de test structure | `workers.preparation` | `SCENARIO / SUCCESS_CRITERIA / TEST_INPUT` |
| **JudgeSubAgent** | Evalue la sortie, donne verdict + score + rationale | `workers.verdict` | `VERDICT / SCORE / RATIONALE` |
| **RobustnessSubAgent** | Propose des tests complementaires | `workers.diagnostic` | `FOLLOWUP_TEST / WHY_IT_MATTERS` |
| **PolicySubAgent** | Verifie la conformite governance | `workers.assertion` | `COMPLIANCE / DETAILS` |

Chaque SubAgent est un `ReActAgent` (AgentScope) avec `max_iters=1` (pas de boucle ReAct -- juste un appel LLM direct).

### 3.3 OrchestratorAgent

Le **chef d'orchestre**. C'est aussi un `ReActAgent` (AgentScope) mais avec :

- Un **Toolkit** contenant 8 tools
- Un **system prompt** en francais qui decrit son role et le workflow
- `max_iters=12` (boucle ReAct)
- Model configurable via `config.orchestrator.model`

Il **decide** quel tool appeler, dans quel ordre. Il peut :
- Skipper des etapes
- Rappeler un tool
- Poser des questions de follow-up

Les 8 tools de l'OrchestratorAgent :

```python
# app/services/test_lab/orchestrator_agent.py

def _build_tools_and_subagents(ctx: RunContext) -> list:
    # 1. Read scenario + agent info
    def get_scenario_context() -> ToolResponse: ...

    # 2. Generate test plan (LLM)
    def run_scenario_subagent(task: str) -> ToolResponse:
        res = _run_async(scenario_subagent(Msg("user", task, "user")))
        return ToolResponse(content=text)

    # 3. Execute the REAL agent under test (not simulation)
    def run_target_agent(task: str) -> ToolResponse:
        result = _run_async(_execute())  # calls target_agent_runner
        ctx.target_output = result.final_output
        return ToolResponse(content=...)

    # 4. Evaluate output (LLM judge)
    def run_judge_subagent(analysis_request: str) -> ToolResponse:
        res = _run_async(judge_subagent(Msg("user", analysis_request, "user")))
        # Parse VERDICT/SCORE from response
        ctx.score = ...; ctx.verdict = ...
        return ToolResponse(content=text)

    # 5. Propose follow-up tests
    def run_robustness_subagent(request: str) -> ToolResponse: ...

    # 6. Check policy compliance
    def run_policy_subagent(request: str) -> ToolResponse: ...

    # 7. Read current run state
    def get_run_state() -> ToolResponse: ...

    # 8. Persist to DB (ALWAYS called last)
    def save_run_result(summary: str) -> ToolResponse: ...
```

### 3.4 RunContext (etat partage)

Dataclass Python qui contient tout l'etat d'un run, partage entre tous les tools :

```python
@dataclass
class RunContext:
    run_id: str
    scenario_id: str
    agent_id: str
    agent_label: str
    agent_version: str
    scenario_name: str
    input_prompt: str
    expected_tools: list[str]
    timeout_seconds: int
    max_iterations: int

    # Filled during execution:
    target_output: str          # REAL agent output
    target_status: str          # completed/failed/timeout
    target_duration_ms: int
    target_iteration_count: int
    execution_events: list[dict]

    # Filled by JudgeSubAgent:
    score: float                # 0-100
    verdict: str                # passed/failed/passed_with_warnings
    summary: str                # LLM rationale
```

---

## 4. Flow d'execution

### 4.1 Declenchement

L'utilisateur clique **"RUN SCENARIO"** dans l'UI :

```
Frontend POST /api/test-lab/scenarios/{id}/run
  ↓
API creates a TestRun record (status: queued)
  ↓
asyncio.create_task(run_orchestrated_test(run_id, scenario_id))
  ↓
API returns immediately with run_id (HTTP 200)
```

**Important** : le run s'execute dans le **meme process que l'API FastAPI**, pas dans Celery. C'est pour partager la memoire de l'OrchestratorAgent avec l'endpoint chat.

### 4.2 Pipeline du run

```python
# app/services/test_lab/orchestrator_agent.py::run_orchestrated_test

async def run_orchestrated_test(run_id: str, scenario_id: str):
    # 1. Load scenario + agent from DB
    scenario = await db.get(TestScenario, scenario_id)
    agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)

    # 2. Build RunContext
    ctx = RunContext(run_id=run_id, ...)

    # 3. Build OrchestratorAgent with persistent SubAgents
    orchestrator = build_orchestrator_agent(ctx)

    # 4. Store in memory for chat follow-ups
    _active_orchestrators[run_id] = (orchestrator, ctx)

    # 5. Kick off the orchestrator
    user_msg = Msg("user", f"Lance le test du scenario '{ctx.scenario_name}'...", "user")
    response = await asyncio.wait_for(
        orchestrator(user_msg),
        timeout=ctx.timeout_seconds + 180,
    )

    # 6. Fallback save if orchestrator didn't call save_run_result
    if not ctx.verdict:
        update_run(run_id, status="completed", verdict="unknown", ...)
```

### 4.3 Workflow suivi par l'OrchestratorAgent

L'OrchestratorAgent suit (en general) ce workflow, guide par son system prompt :

```
Iteration 1: OrchestratorAgent thinks "Je vais lire le contexte"
  → tool call: get_scenario_context()
  ← receives: scenario name, agent_id, input_prompt, expected_tools

Iteration 2: "Je vais preparer un plan de test"
  → tool call: run_scenario_subagent("Prepare un test pour...")
  ← ScenarioSubAgent receives prompt, produces SCENARIO/SUCCESS_CRITERIA/TEST_INPUT

Iteration 3: "Je vais executer le vrai agent sous test"
  → tool call: run_target_agent("Resolve SIREN 552032534...")
  ← Calls target_agent_runner.run_target_agent()
    ← Creates REAL AgentScope ReActAgent (with its prompt, tools, MCPs)
    ← Runs it with the scenario input
    ← Returns: final_output, status, duration, message_history
  ← Stored in ctx.target_output, ctx.target_status, etc.

Iteration 4: "Je vais faire juger la sortie"
  → tool call: run_judge_subagent("L'agent a retourne {output}. Evalue-le.")
  ← JudgeSubAgent produces:
    VERDICT: PASS
    SCORE: 95
    RATIONALE: L'agent a correctement...
  ← Parse via regex → ctx.verdict = "passed", ctx.score = 95.0

Iteration 5: "Je vais sauvegarder"
  → tool call: save_run_result("Resume: le test a passe avec 95/100...")
  ← update_run(run_id, status="completed", verdict="passed", score=95.0, ...)

Iteration 6: Produit un resume final structure pour l'utilisateur
```

L'OrchestratorAgent peut aussi appeler `run_policy_subagent` ou `run_robustness_subagent` s'il juge pertinent (guided par le system prompt qui dit "apres un test, propose des follow-ups").

---

## 5. Modeles de donnees

### 5.1 Tables principales

```sql
-- app/models/test_lab.py

CREATE TABLE test_scenarios (
    id VARCHAR(36) PRIMARY KEY,           -- "scn_abc123..."
    name VARCHAR(255),
    description TEXT,
    agent_id VARCHAR(100),                 -- FK vers agents (pas de FK constraint)
    input_prompt TEXT,
    input_payload JSONB,
    allowed_tools JSONB,
    expected_tools JSONB,
    timeout_seconds INTEGER DEFAULT 120,
    max_iterations INTEGER DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    assertions JSONB,                      -- Array of {type, target, expected, critical}
    tags JSONB,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE test_runs (
    id VARCHAR(36) PRIMARY KEY,           -- "trun_abc123..."
    scenario_id VARCHAR(36),
    agent_id VARCHAR(100),
    agent_version VARCHAR(20),
    status VARCHAR(30),                    -- queued/running/completed/failed
    verdict VARCHAR(30),                   -- passed/failed/passed_with_warnings/unknown
    score FLOAT,                           -- 0-100
    duration_ms INTEGER,
    final_output TEXT,                     -- VRAI output du target agent
    summary TEXT,                          -- Resume LLM de l'OrchestratorAgent
    error_message TEXT,
    execution_metadata JSONB,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE test_run_events (
    id VARCHAR(36) PRIMARY KEY,           -- "tevt_abc123..."
    run_id VARCHAR(36),
    event_type VARCHAR(50),                -- run_started/phase_start/subagent_start/subagent_done/run_completed
    phase VARCHAR(50),                     -- orchestration/preparation/runtime/judgment/verdict
    message TEXT,
    details JSONB,                         -- {subagent, prompt, response, verdict, score, ...}
    timestamp TIMESTAMPTZ,
    duration_ms INTEGER,                   -- Latency of the event (LLM call duration)
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE TABLE test_run_assertions (    -- Used by v0.1 deterministic engine
    id VARCHAR(36) PRIMARY KEY,
    run_id VARCHAR(36),
    assertion_type VARCHAR(50),
    target VARCHAR(255),
    expected TEXT,
    actual TEXT,
    passed BOOLEAN,
    critical BOOLEAN,
    message TEXT,
    details JSONB,
    ...
);

CREATE TABLE test_run_diagnostics (   -- Used by v0.1 deterministic engine
    id VARCHAR(36) PRIMARY KEY,
    run_id VARCHAR(36),
    code VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    probable_causes JSONB,
    recommendation TEXT,
    evidence JSONB,
    ...
);

CREATE TABLE test_lab_config (        -- Key-value store for config
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,                            -- JSON-encoded
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

### 5.2 Structure de `test_lab_config`

3 cles principales :

```json
// Key: "orchestrator"
{
  "provider": "ollama",
  "model": "gpt-oss:20b",
  "max_iters": 10
}

// Key: "workers"
{
  "preparation": {
    "prompt": "Tu es un sous-agent de scenarisation...",
    "model": "mistral",  // optional override
    "skills": []
  },
  "assertion": { "prompt": "...", "model": null, "skills": [] },
  "diagnostic": { "prompt": "...", "model": null, "skills": [] },
  "verdict": { "prompt": "...", "model": null, "skills": [] }
}

// Key: "defaults"
{
  "timeout_seconds": 120,
  "max_iterations": 5,
  "retry_count": 0
}
```

---

## 6. API REST

### 6.1 Endpoints principaux

```
# Scenarios CRUD
POST   /api/test-lab/scenarios             Create scenario
GET    /api/test-lab/scenarios             List scenarios (paginated)
GET    /api/test-lab/scenarios/{id}        Get scenario
PATCH  /api/test-lab/scenarios/{id}        Update scenario
DELETE /api/test-lab/scenarios/{id}        Delete scenario

# Run execution
POST   /api/test-lab/scenarios/{id}/run    Launch a run → returns run_id
GET    /api/test-lab/runs                  List runs (paginated, filter by scenario/agent)
GET    /api/test-lab/runs/{id}             Get run state
GET    /api/test-lab/runs/{id}/events      Get all events
GET    /api/test-lab/runs/{id}/assertions  Get assertions (v0.1 only)
GET    /api/test-lab/runs/{id}/diagnostics Get diagnostics (v0.1 only)
GET    /api/test-lab/runs/{id}/report      Composite: run + events + assertions + diagnostics + scenario
GET    /api/test-lab/runs/{id}/stream      SSE live stream of events (via Redis pub/sub)

# Chat with orchestrator
POST   /api/test-lab/runs/{id}/chat        Send a message, returns orchestrator response

# Agent summary
GET    /api/test-lab/agents/{id}/summary   Aggregated stats (pass rate, avg score, etc.)

# Configuration
GET    /api/test-lab/config                Get current config
PUT    /api/test-lab/config                Update config (nested structure)
GET    /api/test-lab/config/skills         List available skills (for SubAgent config)
GET    /api/test-lab/config/models/{provider}  List available models for a provider

# Sessions (interactive chat before any run)
POST   /api/test-lab/sessions              Create a new session
GET    /api/test-lab/sessions/{id}         Get session state
POST   /api/test-lab/sessions/{id}/message Send message to session orchestrator
GET    /api/test-lab/sessions              List active sessions
```

### 6.2 Exemple : lancer un run

```bash
curl -X POST http://localhost:8200/api/test-lab/scenarios/scn_abc/run \
  -H "Content-Type: application/json"

# Response
{
  "id": "trun_xyz",
  "status": "queued",
  "scenario_id": "scn_abc",
  "agent_id": "identity_resolution_agent"
}
```

Le run demarre immediatement en background (via `asyncio.create_task`). Le client peut ensuite :

- **Polling** : `GET /api/test-lab/runs/{id}` toutes les 2s
- **SSE stream** : `GET /api/test-lab/runs/{id}/stream` pour recevoir les events en temps reel
- **Voir les events** : `GET /api/test-lab/runs/{id}/events`

### 6.3 Exemple : chat avec l'orchestrator

```bash
curl -X POST http://localhost:8200/api/test-lab/runs/trun_xyz/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explique pourquoi le verdict est FAIL"}'

# Response
{
  "run_id": "trun_xyz",
  "response": "L'agent a retourne resolved=false car il n'a pas pu acceder a l'API INSEE..."
}
```

L'orchestrator garde sa memoire (conversation + tools calls du run initial) tant que l'API tourne. Apres un restart, il est **rebuildeable** depuis la DB (`_rebuild_orchestrator_from_db`).

---

## 7. Integration MCP

### 7.1 Deux sources d'outils MCP

Un agent sous test peut utiliser des outils MCP de 2 sources :

**Source 1 : Obot catalog** (MCP servers externes)

```python
# app/services/agent_factory.py::create_agentscope_agent()

# Resolve MCP servers from agent's allowed_mcps
mcp_servers = await agent_registry_service.available_mcp_summaries(db)

# Filter by allowed_mcps AND enabled_in_orkestra
for mcp_id in agent_def.allowed_mcps:
    if mcp_id in enabled_mcp_ids:
        # Connect to Obot MCP server via HTTP streamable
        client = HttpStatelessClient(base_url=mcp_url)
        tools_from_mcp = await client.list_tools()
        toolkit.register_tool(tools_from_mcp)
```

**Source 2 : Local Python tools**

```python
# app/services/mcp_tool_registry.py (single source of truth)

def get_local_tools() -> dict:
    tools = {}
    tools["document_parser"] = [parse_document, classify_document]
    tools["consistency_checker"] = [check_consistency, validate_fields]
    tools["search_engine"] = [search_knowledge]
    tools["weather"] = [get_weather]
    return tools
```

### 7.2 Governance : filtrage enabled_in_orkestra

Un MCP doit etre **explicitement active** dans Orkestra meme s'il existe dans Obot :

```python
# app/services/agent_registry_service.py::available_mcp_summaries

async def available_mcp_summaries(db):
    items = await obot_catalog_service.list_catalog_items(db)
    return [
        item for item in items
        if item.orkestra_binding.enabled_in_orkestra  # ← filter
        or item.orkestra_state in ("enabled", "active")
    ]
```

Resultat : le dropdown "MCP autorise" dans l'UI Agent form ne liste que les MCPs actives. Les MCPs Obot existants mais non-enabled dans Orkestra ne sont pas exposes.

### 7.3 Runtime enforcement

Dans `agent_factory.create_agentscope_agent()`, meme si l'agent a `allowed_mcps = ["mcp_a", "mcp_b"]`, on **filtre a nouveau** au runtime :

```python
allowed = set(agent_def.allowed_mcps or [])
for mcp_id, tools in get_local_tools().items():
    if allowed and mcp_id not in allowed:
        continue  # Skip MCP not in allowlist
    for tool in tools:
        toolkit.register(tool)
```

Donc un agent ne peut physiquement pas appeler un outil qu'il n'a pas declare dans `allowed_mcps`, meme si le LLM essaie.

---

## 8. Configuration dynamique

### 8.1 Page `/test-lab/config`

L'UI permet de configurer en live :

- **OrchestratorAgent LLM** : provider + model utilise par le ReActAgent chef d'orchestre
- **SubAgents** (4 cartes expandables) :
  - **ScenarioSubAgent** (key `preparation`) : model + prompt + skills
  - **PolicySubAgent** (key `assertion`) : model + prompt + skills
  - **RobustnessSubAgent** (key `diagnostic`) : model + prompt + skills
  - **JudgeSubAgent** (key `verdict`) : model + prompt + skills
- **Default scenario settings** : timeout, max iterations, retry count

### 8.2 Lecture cote backend

Le code lit la config via `_get_config_sync()` (SQL direct, sync, pour Celery/threading) :

```python
# app/services/test_lab/execution_engine.py

def _get_config_sync() -> dict:
    engine = _get_sync_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT key, value FROM test_lab_config")).fetchall()

    config = {**DEFAULT_CONFIG}
    for r in rows:
        val = json.loads(r[1]) if isinstance(r[1], str) else r[1]
        if isinstance(config[r[0]], dict) and isinstance(val, dict):
            config[r[0]] = {**config[r[0]], **val}
        else:
            config[r[0]] = val
    return config
```

### 8.3 Utilisation dans `_make_model`

Quand un SubAgent est cree, son model est pioche dans la config :

```python
def _make_model(worker_name: str = None) -> OllamaChatModel:
    config = _get_config_sync()

    # Priorite 1: override du worker specifique
    if worker_name and worker_name in config.get("workers", {}):
        model_name = config["workers"][worker_name].get("model")

    # Priorite 2: model default de l'orchestrator
    if not model_name:
        model_name = config.get("orchestrator", {}).get("model", "mistral")

    host = settings.OLLAMA_HOST  # http://host.docker.internal:11434
    return OllamaChatModel(model_name=model_name, host=host, stream=False)
```

**Mapping UI → backend** :

| UI label | config key | Utilise par |
|---|---|---|
| OrchestratorAgent LLM | `orchestrator.model` | `_make_model()` sans argument |
| ScenarioSubAgent | `workers.preparation.model` | `_make_model("preparation")` |
| PolicySubAgent | `workers.assertion.model` | `_make_model("assertion")` |
| RobustnessSubAgent | `workers.diagnostic.model` | `_make_model("diagnostic")` |
| JudgeSubAgent | `workers.verdict.model` | `_make_model("verdict")` |

---

## 9. UI

### 9.1 Parcours utilisateur

```
1. Dashboard → Agents → Select an agent
2. Agent lifecycle panel shows "DESIGNED → TESTED" gate with:
   [+ Create Test Scenario]  [🧪 Open Test Lab]
3. Click "Create Test Scenario" → /test-lab/scenarios/new?agent_id=xxx
4. Fill the form (agent pre-selected), click Create
5. Click "Open Test Lab" → /test-lab (Scenarios tab)
6. Click the scenario → /test-lab/scenarios/scn_xxx
7. Click "RUN SCENARIO" → redirected to /test-lab/runs/trun_xxx
8. Live SSE stream shows events in real time:
   - run_started
   - ScenarioSubAgent starting / done
   - Executing target agent
   - Agent finished: completed
   - JudgeSubAgent starting / done: passed 95/100
   - Test completed
9. Below events, the Chat with OrchestratorAgent section lets you:
   - "Explain why the verdict is passed"
   - "Run a stricter version"
   - "Check policy compliance"
```

### 9.2 Pages principales

| Route | Fichier | Description |
|---|---|---|
| `/test-lab` | `app/test-lab/page.tsx` | 2 tabs: **Interactive Session** + **Scenarios** list |
| `/test-lab/config` | `app/test-lab/config/page.tsx` | Configure OrchestratorAgent + SubAgents |
| `/test-lab/scenarios/new` | `app/test-lab/scenarios/new/page.tsx` | Create scenario (agent dropdown) |
| `/test-lab/scenarios/[id]` | `app/test-lab/scenarios/[id]/page.tsx` | Scenario detail + list of runs |
| `/test-lab/runs/[id]` | `app/test-lab/runs/[id]/page.tsx` | Run detail, live events, chat with orchestrator |

### 9.3 Composant "Interactive Session" (tab on `/test-lab`)

```tsx
// app/test-lab/page.tsx (tab === "interactive")

<ChatUI>
  <AgentSelector />                // Dropdown des agents
  <MessageList>                    // Conversation (user + orchestrator + system)
    {conversation.map(msg => <Message {...msg} />)}
  </MessageList>
  <FollowUpButtons />              // Buttons dynamic (stricter, robustness, policy, rerun)
  <TextInput />                    // Type a message
</ChatUI>

// State flow:
// 1. On mount: POST /api/test-lab/sessions → sessionId
// 2. User types message → POST /api/test-lab/sessions/{id}/message
// 3. Response updates conversation + available_followups
```

Cette interface utilise un **SessionOrchestrator** separe (`app/services/test_lab/session_orchestrator.py`) qui est un layer au-dessus de `run_orchestrated_test`. Un peu redondant avec le chat du run -- prochaine etape : unifier les deux.

---

## 10. Observabilite

### 10.1 Events SSE

Chaque etape du pipeline emet un event via `emit_event()` :

```python
# app/services/test_lab/execution_engine.py

def emit_event(run_id, event_type, phase, message, details=None, duration_ms=None):
    event_id = new_id("tevt_")
    now = datetime.now(timezone.utc)

    # 1. Persist to DB
    engine = _get_sync_engine()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO test_run_events ..."),
            {"id": event_id, "run_id": run_id, ...}
        )

    # 2. Publish to Redis for SSE
    r = redis.from_url(REDIS_URL)
    r.publish(f"test_lab:run:{run_id}", json.dumps({
        "id": event_id,
        "event_type": event_type,
        "phase": phase,
        "message": message,
        "details": details,
        "timestamp": now.isoformat(),
    }))
```

### 10.2 Types d'events emis

| event_type | phase | details |
|---|---|---|
| `run_started` | orchestration | -- |
| `subagent_start` | preparation/judgment/... | `{subagent, prompt}` |
| `subagent_done` | preparation/judgment/... | `{subagent, response, verdict, score, response_length}` |
| `phase_start` | runtime | `{agent_id}` |
| `agent_done` | runtime | `{status, duration_ms}` |
| `run_completed` | verdict | `{verdict, score}` |
| `run_failed` | error | `{error}` |
| `orchestrator_chat` | interactive | `{message preview}` |

### 10.3 Affichage des details dans l'UI

Dans la page run detail, chaque event `subagent_*` a un bouton **"Show details"** qui deplie :

- **Prompt** envoye au LLM (border cyan)
- **Response** LLM complete (border violet)
- Badges : `Prompt`, `LLM`, `verdict/score`
- Duration_ms visible sur l'event

```tsx
// app/test-lab/runs/[id]/page.tsx::EventDetails

if (hasSubagentPrompt) {
  <div className="border-l-2 border-ork-cyan/30 pl-3">
    <p>{d.subagent} — Prompt</p>
    <pre>{d.prompt}</pre>
  </div>
}

if (hasSubagentResponse) {
  <div className="border-l-2 border-ork-purple/30 pl-3">
    <p>{d.subagent} — Response {d.verdict && `(${d.verdict}, ${d.score}/100)`}</p>
    <pre>{d.response}</pre>
    <p>{d.response_length} chars</p>
  </div>
}
```

---

## 11. Chat interactif

### 11.1 Principe

L'OrchestratorAgent est conserve en memoire dans `_active_orchestrators[run_id]` pendant toute la duree de vie du process API. Apres un run, l'utilisateur peut continuer a discuter avec lui.

### 11.2 Memoire partagee

**Question importante** : pourquoi le run s'execute dans le process API et pas dans Celery ?

```python
# app/api/routes/test_lab.py

@router.post("/scenarios/{scenario_id}/run")
async def start_run(...):
    # Run orchestrator in the SAME process as the API so the orchestrator
    # stays in memory and can be reused by the chat endpoint.
    import asyncio as _asyncio
    from app.services.test_lab.orchestrator_agent import run_orchestrated_test
    _asyncio.create_task(run_orchestrated_test(run.id, scenario.id))
    return {...}
```

**Raison** : si le run tourne dans Celery worker (process A) et le chat dans l'API (process B), `_active_orchestrators` est un dict Python **local a un process**. Les deux process ne voient pas le meme dict → chat = "No active orchestrator".

En executant le run dans `asyncio.create_task()` du meme process API, les deux partagent la memoire.

**Contrepartie** : un run long bloque un worker FastAPI (timeout HTTP), et si l'API redemarre, la memoire est perdue.

### 11.3 Rebuild apres restart

```python
async def chat_with_orchestrator(run_id: str, message: str) -> str:
    if run_id in _active_orchestrators:
        # Fast path: orchestrator still in memory
        orchestrator, ctx = _active_orchestrators[run_id]
    else:
        # Rebuild from DB state (after API restart)
        orchestrator, ctx = await _rebuild_orchestrator_from_db(run_id)
        _active_orchestrators[run_id] = (orchestrator, ctx)

    res = await asyncio.wait_for(
        orchestrator(Msg("user", message, "user")),
        timeout=120,
    )
    return _extract_text(res.content)


async def _rebuild_orchestrator_from_db(run_id: str):
    """Rebuild orchestrator from a completed run.
    Pre-populate the RunContext with scores/verdict/output from DB.
    Seed the agent's memory with a 'system' message containing the run context.
    """
    run = await db.get(TestRun, run_id)
    scenario = await db.get(TestScenario, run.scenario_id)
    agent_def = await agent_registry_service.get_agent(db, scenario.agent_id)

    ctx = RunContext(
        run_id=run_id,
        agent_id=scenario.agent_id,
        scenario_name=scenario.name,
        input_prompt=scenario.input_prompt,
        # Pre-populate from previous run:
        target_output=run.final_output,
        target_status=run.status,
        target_duration_ms=run.duration_ms,
        score=run.score,
        verdict=run.verdict,
        summary=run.summary,
    )

    orchestrator = build_orchestrator_agent(ctx)

    # Seed memory with context
    context_msg = Msg("system",
        f"Un test a deja ete execute... Verdict: {ctx.verdict}, Score: {ctx.score}/100...",
        "system")
    await orchestrator.memory.add(context_msg)

    return orchestrator, ctx
```

L'orchestrator rebuilde perd sa conversation precedente mais recoit un **system message** avec toutes les infos du run, ce qui lui permet de repondre intelligemment aux questions.

---

## 12. Points de fragilite et ameliorations

### 12.1 Problemes actuels

**1. Parsing regex fragile**
Le JudgeSubAgent doit respecter le format `VERDICT: X / SCORE: N`. Si le LLM repond en freestyle, `score = 0` et `verdict = ""`.

Fix possible : utiliser un prompt avec JSON schema strict (`response_format={"type": "json_object"}`) ou forcer un outil structured output.

**2. Context overflow Ollama**
Le target agent peut produire 5000+ chars de sortie, ce qui explose le context window des petits modeles. On a tronque a 800 chars dans `run_target_agent` mais c'est arbitraire.

Fix possible : truncation adaptative basee sur le context window du model, ou chunking + summarization.

**3. Memoire non persistante**
Si l'API redemarre, les conversations en memoire sont perdues. On rebuild depuis la DB mais la conversation complete est perdue.

Fix possible : pickler la memoire AgentScope dans Redis/DB apres chaque message.

**4. Run bloque le process API**
`asyncio.create_task` n'est pas vraiment en background -- si le process plante, le run est perdu.

Fix possible : retourner a Celery mais avec un broker pour l'orchestrator state (Redis avec shared memory).

**5. Pas de retry**
Si Ollama 500, le run echoue. Pas de retry automatique.

Fix possible : wrapper avec tenacity ou exponential backoff.

**6. Scoring pas reproducible**
Deux runs identiques peuvent donner des scores differents car le LLM n'est pas deterministe.

Fix possible : temperature=0 dans la config Ollama du JudgeSubAgent.

### 12.2 Deterministes pas utilises

`scoring.py`, `assertion_engine.py`, `diagnostic_engine.py` existent mais ne sont pas appeles dans le flow actuel. A decision :

- **Option A** : les supprimer, full LLM
- **Option B** : les reactiver en **parallele** -- garder un score LLM (interprete) ET un score deterministe (assertions) dans le meme run. Donne un ancre factuel.

### 12.3 Unification chat

Il y a deux systemes de chat :
1. **Interactive Session** (`/test-lab` tab) -- utilise `session_orchestrator.py`
2. **Run Chat** (`/test-lab/runs/{id}`) -- utilise `orchestrator_agent.py::chat_with_orchestrator`

Ils font la meme chose avec des codes differents. A fusionner.

---

## Annexe A : Fichiers cle

```
app/
├── api/routes/test_lab.py                  API endpoints
├── api/routes/test_lab_session.py          Session-based chat (separate system)
├── models/test_lab.py                       SQLAlchemy ORM
├── schemas/test_lab.py                      Pydantic schemas
├── schemas/test_lab_session.py              Session state schemas
├── services/
│   ├── test_lab/
│   │   ├── orchestrator_agent.py            ★ Main: multi-agent runner
│   │   ├── target_agent_runner.py           ★ Real agent execution
│   │   ├── execution_engine.py              DB helpers + emit_event
│   │   ├── scoring.py                       (legacy, unused)
│   │   ├── assertion_engine.py              (legacy, unused)
│   │   ├── diagnostic_engine.py             (legacy, unused)
│   │   ├── agent_summary.py                 Agent stats aggregator
│   │   ├── scenario_service.py              CRUD scenarios
│   │   ├── session_orchestrator.py          Session-based chat (separate)
│   │   └── subagents.py                     Legacy subagent helpers
│   ├── agent_factory.py                     Creates real AgentScope agents
│   ├── agent_registry_service.py            Agent CRUD + MCP resolution
│   └── mcp_tool_registry.py                 Single source of truth for MCPs
└── tasks/test_lab.py                         Celery task (now mostly unused)

frontend/src/app/test-lab/
├── page.tsx                                  Main (Interactive + Scenarios tabs)
├── config/page.tsx                           Config UI (OrchestratorAgent + SubAgents)
├── scenarios/new/page.tsx                    Create scenario form
├── scenarios/[id]/page.tsx                   Scenario detail
└── runs/[id]/page.tsx                        Run detail + chat with orchestrator

scripts/
├── orchestrateur_chat.py                     Standalone CLI (prototype, not connected)
├── create_identity_agent.py                  Seed identity agent + scenario via API
└── create_test_lab_tables.py                 Seed scenarios via API
```

---

## Annexe B : Commandes utiles

```bash
# Start all services
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker compose up -d

# Seed an agent + scenarios
python scripts/create_identity_agent.py --promote
python scripts/create_test_lab_tables.py

# View run events live
curl -N http://localhost:8200/api/test-lab/runs/trun_xxx/stream

# Launch a run
curl -X POST http://localhost:8200/api/test-lab/scenarios/scn_xxx/run

# Chat with orchestrator
curl -X POST http://localhost:8200/api/test-lab/runs/trun_xxx/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explique le verdict"}'

# Check config
curl http://localhost:8200/api/test-lab/config | python3 -m json.tool

# Update config (full nested structure)
curl -X PUT http://localhost:8200/api/test-lab/config \
  -H "Content-Type: application/json" \
  -d '{
    "orchestrator": {"provider": "ollama", "model": "mistral", "max_iters": 10},
    "workers": {
      "preparation": {"model": "gpt-oss:20b", "prompt": "..."},
      "verdict": {"model": "mistral", "prompt": "..."}
    }
  }'

# View Docker logs
docker compose logs api --tail=50 -f
docker compose logs celery-worker --tail=50 -f
```

---

*Document genere le 2026-04-09. Version Test Lab : v0.2 (multi-agent LLM-driven).*
