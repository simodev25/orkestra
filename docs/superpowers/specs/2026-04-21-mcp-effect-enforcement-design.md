# MCP Effect Enforcement — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rendre `forbidden_effects` réellement exécutoire — chaque tool call MCP est classifié par un LLM (Haiku) avant exécution (avec support des effets composés), bloqué si l'effet est interdit pour l'agent, overridable par run par un admin, avec badge rouge dans le RunGraph et historique des violations dans l'agent edit.

**Contrainte principale :** Ne pas modifier `mcp_executor.py` — le moteur reste pur. L'enforcement s'ajoute en amont via un wrapper AOP.

---

## Contexte : état actuel

| Couche | État |
|--------|------|
| UI `forbidden_effects` checkboxes | ✅ Présent (agent-form.tsx) |
| Stockage DB `forbidden_effects` (JSONB) | ✅ Présent (AgentDefinition) |
| Injection dans prompt système | ✅ Présent (prompt_builder.py) — guidance seulement |
| Enforcement à l'exécution | ❌ Absent |
| `allowed_mcps` enforcement | ✅ Présent dans `invoke_mcp()` — modèle à suivre |
| `mcp.effect_type` | ✅ Présent sur MCPDefinition — niveau MCP server (grossier) |

Le problème : `forbidden_effects` informe le LLM mais ne bloque rien. Un tool `write_file` s'exécute même si l'agent a `forbidden_effects: ["write"]`.

---

## Architecture

```
Agent Run (test-lab ou production)
  → guarded_invoke_mcp(tool_action, tool_kwargs, agent, run_config, ...)
      │
      ├─ [1] AllowlistCheck       → allowed_mcps (existant, inchangé)
      ├─ [2] EffectClassifier     → Haiku : ["write", "act"] (liste, cache tool_name→effects)
      ├─ [3] RunOverrideCheck     → run_config.effect_overrides peut débloquer certains effets
      ├─ [4] EnforcementCheck     → any(e in forbidden_effects for e in effects) ?
      │       ├─ forbidden → MCPInvocation(status="denied", effect_type=<effets bloqués>)
      │       └─ allowed  → invoke_mcp() existant
      └─ [5] Résultat → DB → RunGraph badge + historique violations
```

---

## Composant 1 — `app/services/effect_classifier.py` (NEW)

Micro-service de classification LLM avec support effets composés et cache process-level.

**Interface :**
```python
class EffectClassifier:
    async def classify(self, tool_name: str, args: dict) -> list[str]
    # Retourne une liste : ["write"] ou ["write", "act"] ou ["read"]
```

**Cache :** `Dict[str, list[str]]` keyed sur `tool_name` — stable, pas de TTL.

**Prompt classifier :**
```
System: Classify the tool call into one or more of:
  read, search, compute, generate, validate, write, act
- read    : fetches/retrieves data, no mutation
- search  : queries/lookups, no mutation
- compute : pure calculation, no I/O side effects
- generate: produces new content (text, image, code)
- validate: checks/verifies, no mutation
- write   : creates, updates, or deletes data
- act     : triggers external action (email, API call, deploy)
Reply with a comma-separated list of applicable effects, e.g. "write" or "write,act".
No explanation, only the list.

User: tool={tool_name} args={args_summary_200chars}
```

**Parsing de la réponse :**
```python
raw = llm_response.strip().lower()
effects = [e.strip() for e in raw.split(",") if e.strip() in EFFECT_TYPES]
if not effects:
    effects = _heuristic_classify(tool_name)  # fallback
```

**Fallback heuristique (si LLM échoue ou timeout 2s) :**
```python
def _heuristic_classify(tool_name: str) -> list[str]:
    name = tool_name.lower()
    if any(p in name for p in ("write", "create", "delete", "update", "save")):
        return ["write"]
    if any(p in name for p in ("search", "query", "find", "lookup")):
        return ["search"]
    if any(p in name for p in ("get", "fetch", "read", "list")):
        return ["read"]
    if any(p in name for p in ("send", "post", "publish", "deploy", "email")):
        return ["act"]
    return ["compute"]  # défaut conservateur
```

**Singleton exporté :** `_classifier = EffectClassifier()` — partagé entre tous les runs du process.

---

## Composant 2 — `app/services/guarded_mcp_executor.py` (NEW)

Wrapper AOP autour de `invoke_mcp()`. Même signature, drop-in replacement.

**Interface :**
```python
async def guarded_invoke_mcp(
    db: AsyncSession,
    run_id: str,
    mcp_id: str,
    calling_agent_id: str,
    subagent_invocation_id: str | None = None,
    tool_action: str | None = None,
    tool_kwargs: dict | None = None,
    run_effect_overrides: list[str] | None = None,  # depuis Run.config
) -> MCPInvocation
```

**Logique complète :**
```python
async def guarded_invoke_mcp(...) -> MCPInvocation:
    # [1] AllowlistCheck — déjà dans invoke_mcp, pas dupliqué ici

    # [2] Récupérer forbidden_effects de l'agent
    agent = await db.get(AgentDefinition, calling_agent_id)
    forbidden = set(agent.forbidden_effects or []) if agent else set()

    # [3] Classifier si forbidden_effects configurés
    if forbidden and tool_action:
        effects = await _classifier.classify(tool_action, tool_kwargs or {})

        # [4] Run-level override : retire les effets autorisés pour ce run
        overrides = set(run_effect_overrides or [])
        effective_forbidden = forbidden - overrides
        blocked = [e for e in effects if e in effective_forbidden]

        if blocked:
            inv = MCPInvocation(
                run_id=run_id,
                subagent_invocation_id=subagent_invocation_id,
                mcp_id=mcp_id,
                calling_agent_id=calling_agent_id,      # nouveau champ
                effect_type=",".join(blocked),           # effets bloqués
                status="denied",
                approval_required=False,
            )
            db.add(inv)
            await db.flush()
            await emit_event(db, "mcp.denied", "runtime", "guarded_mcp_executor",
                             run_id=run_id,
                             payload={
                                 "mcp_id": mcp_id,
                                 "agent_id": calling_agent_id,
                                 "reason": "forbidden_effect",
                                 "effects": blocked,
                             })
            return inv

    # [5] Délègue au moteur existant
    return await invoke_mcp(db, run_id, mcp_id, calling_agent_id,
                            subagent_invocation_id, tool_action, tool_kwargs)
```

---

## Composant 3 — Migrations DB

### 3a. `MCPInvocation` — ajouter `calling_agent_id`

```python
# app/models/invocation.py
calling_agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
```

Permet de retrouver les violations par agent sans jointure complexe.

### 3b. `Run` — ajouter `config`

```python
# app/models/run.py
config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
# Structure attendue : {"effect_overrides": ["write", "act"]}
```

---

## Composant 4 — Interface admin override par run

### Backend : `GET/PATCH /api/runs/{run_id}/config`

```python
# PATCH body
{"effect_overrides": ["write"]}
# Stocké dans Run.config
```

`guarded_invoke_mcp` charge `run.config.get("effect_overrides", [])` et le passe en `run_effect_overrides`.

### Frontend : section dans le run detail (test-lab)

Dans la page de détail d'un run (`/test-lab/runs/{run_id}`), une section admin collapsée :

```
⚙ Override forbidden effects for this run   [admin only]
☐ read  ☐ search  ☐ compute  ☐ generate  ☐ validate  ☑ write  ☐ act
[Save overrides]
```

- Visible uniquement si l'utilisateur est admin
- Effets cochés = autorisés pour ce run même si interdits par l'agent
- Sauvegarde via `PATCH /api/runs/{run_id}/config`
- Badge d'avertissement : "⚠ 2 forbidden effects overridden for this run"

---

## Composant 5 — Badge RunGraph

**Fichier :** `frontend/src/components/test-lab/run-graph/RunGraph.tsx`

Les events `mcp.denied` avec `payload.reason === "forbidden_effect"` déclenchent un badge sur le nœud runtime concerné.

**Rendu :**
```
⛔ blocked: write, act
```
- Couleur : `--ork-red` / `--ork-red-bg`
- Tooltip : `"effects [write, act] are forbidden for agent {agent_id}"`

**Distinction visuelle avec allowlist deny :**
- `reason: "not in agent allowlist"` → badge gris "denied"
- `reason: "forbidden_effect"` → badge rouge "blocked: {effects}"

---

## Composant 6 — Historique violations dans l'agent edit

### Backend : `GET /api/agents/{agent_id}/effect-violations`

Nouvelle route dans `app/api/routes/agents.py` :

```python
# Response schema
{
  "violations": [
    {
      "run_id": "run_xxx",
      "mcp_id": "filesystem",
      "effects": ["write"],
      "blocked_at": "2026-04-21T10:00:00Z"
    }
  ],
  "summary": {"write": 5, "act": 2}
}
```

Query :
```python
MCPInvocation
  WHERE calling_agent_id = agent_id
  AND status = "denied"
  AND effect_type IS NOT NULL
ORDER BY started_at DESC
LIMIT 50
```

### Frontend : nouvelle section dans `agent-form.tsx`

Section "Violations d'effet" (section 13, visible uniquement en mode édition, pas création) :

```
Violations d'effet                    write: 5  act: 2

run_abc123  filesystem  write, act  2026-04-21 10:00
run_def456  filesystem  write       2026-04-20 15:30
...
```

- Table avec colonnes : run_id (lien vers le run), MCP, effets bloqués, date
- Badges de résumé par effet en haut
- Chargé via `GET /api/agents/{agent_id}/effect-violations`
- Message "Aucune violation" si vide

---

## Tests

### Unit — `effect_classifier.py`

| Test | Description |
|------|-------------|
| `test_classify_single_effect` | `classify("write_file", {})` → `["write"]` |
| `test_classify_compound_effect` | `classify("search_and_save", {})` → `["search", "write"]` |
| `test_classify_uses_cache` | 2ème appel → pas d'appel LLM (mock vérifie 1 seul call) |
| `test_classify_fallback_on_llm_failure` | LLM timeout → heuristique retourne `["write"]` pour `write_doc` |
| `test_classify_fallback_unknown_tool` | Tool inconnu → `["compute"]` (défaut) |
| `test_classify_invalid_llm_response` | LLM retourne `"destroy"` → fallback heuristique |
| `test_classify_partial_invalid_response` | LLM retourne `"write,destroy"` → `["write"]` (filtre invalides) |

### Unit — `guarded_mcp_executor.py`

| Test | Description |
|------|-------------|
| `test_blocks_forbidden_single_effect` | `forbidden=["write"]`, tool → `["write"]` → denied |
| `test_blocks_forbidden_compound_effect` | `forbidden=["act"]`, tool → `["write","act"]` → denied (any match) |
| `test_allows_permitted_effect` | `forbidden=["write"]`, tool → `["read"]` → délègue |
| `test_run_override_unblocks_effect` | `forbidden=["write"]`, `run_overrides=["write"]` → délègue |
| `test_run_override_partial` | `forbidden=["write","act"]`, `run_overrides=["write"]`, tool → `["act"]` → denied |
| `test_no_forbidden_effects_configured` | `forbidden=[]` → délègue directement, pas d'appel classifier |
| `test_emit_event_on_block` | `mcp.denied` avec `reason="forbidden_effect"` + `effects` émis |
| `test_calling_agent_id_stored` | `MCPInvocation.calling_agent_id` rempli sur denied |
| `test_allowlist_check_still_works` | `allowed_mcps` enforcement toujours fonctionnel |
| `test_no_tool_action_skips_classifier` | `tool_action=None` → pas de classification, délègue |

### Unit — `GET /api/agents/{id}/effect-violations`

| Test | Description |
|------|-------------|
| `test_violations_returns_only_agent_violations` | Ne retourne pas les violations d'autres agents |
| `test_violations_summary_counts` | Summary agrège correctement par effet |
| `test_violations_empty` | Retourne `{"violations": [], "summary": {}}` si aucune |

### Integration

| Test | Description |
|------|-------------|
| `test_full_run_forbidden_write` | Run + agent `forbidden=["write"]` + tool `write_file` → invocation `denied` en DB |
| `test_full_run_allowed_read` | Run + agent `forbidden=["write"]` + tool `read_file` → invocation `completed` |
| `test_full_run_with_override` | Run + `config.effect_overrides=["write"]` + tool `write_file` → invocation `completed` |
| `test_compound_effect_partial_block` | Tool → `["read","write"]`, `forbidden=["write"]` → denied avec `effect_type="write"` |

### Frontend Component

| Test | Description |
|------|-------------|
| `test_badge_shown_for_blocked_effect` | Event `mcp.denied` + `reason=forbidden_effect` → badge rouge |
| `test_badge_shows_compound_effects` | `effects=["write","act"]` → badge affiche "blocked: write, act" |
| `test_badge_not_shown_for_allowlist_deny` | `reason=not in agent allowlist` → badge gris, pas rouge |
| `test_violations_section_shown_in_edit_mode` | Section visible en mode édition |
| `test_violations_section_hidden_in_create_mode` | Section absente en mode création |
| `test_violations_table_renders` | Table affiche run_id, mcp, effets, date |

---

## Non-inclus (YAGNI)

- Soft enforcement (log-only) — l'enforcement est toujours bloquant
- Notifications temps réel sur violation (peut être ajouté via WebSocket plus tard)
- Export CSV des violations
