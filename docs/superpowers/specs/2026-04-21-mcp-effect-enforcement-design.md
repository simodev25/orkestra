# MCP Effect Enforcement — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rendre `forbidden_effects` réellement exécutoire — chaque tool call MCP est classifié par un LLM (Haiku) avant exécution, bloqué si l'effet est interdit pour l'agent, avec badge rouge visible dans le RunGraph.

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

Le problème : `forbidden_effects` informe le LLM mais ne bloque rien. Un tool `write_file` s'exécute même si l'agent a `forbidden_effects: ["write"]`. L'enforcement existant (`allowed_mcps`) montre le pattern exact à reproduire.

---

## Architecture

```
Agent Run (test-lab ou production)
  → guarded_invoke_mcp(tool_action, tool_kwargs, agent, ...)
      │
      ├─ [1] AllowlistCheck       → allowed_mcps (existant, inchangé)
      ├─ [2] EffectClassifier     → Haiku : "write" | "read" | ... (cache tool_name→effect)
      ├─ [3] EnforcementCheck     → compare vs agent.forbidden_effects
      │       ├─ forbidden → MCPInvocation(status="denied", effect_type=<classified>)
      │       └─ allowed  → invoke_mcp() existant
      └─ [4] Résultat → DB → RunGraph badge si status="denied" + effect_type
```

---

## Composants

### 1. `app/services/effect_classifier.py` — NEW

Micro-service de classification LLM avec cache process-level.

**Interface :**
```python
class EffectClassifier:
    async def classify(self, tool_name: str, args: dict) -> str
```

**Comportement :**
- Cache `Dict[str, str]` keyed sur `tool_name` — l'effet d'un tool est stable (pas de TTL)
- Appel Haiku via `get_chat_model()` de `app/llm/provider.py`
- Prompt système strict : 7 effets possibles, réponse 1 mot
- Timeout 2s → fallback heuristique si LLM indisponible
- Fallback heuristique : pattern matching sur `tool_name` (`write_*`/`create_*`/`delete_*` → `write`, `get_*`/`fetch_*`/`read_*` → `read`, `search_*`/`query_*` → `search`, défaut → `compute`)

**Prompt classifier :**
```
System: Classify the tool call into exactly one of:
  read, search, compute, generate, validate, write, act
- read    : fetches/retrieves data, no mutation
- search  : queries/lookups, no mutation
- compute : pure calculation, no I/O side effects
- generate: produces new content (text, image, code)
- validate: checks/verifies, no mutation
- write   : creates, updates, or deletes data
- act     : triggers external action (email, API call, deploy)
Reply with exactly one lowercase word.

User: tool={tool_name} args={args_summary_200chars}
```

**Singleton :** `_classifier = EffectClassifier()` exporté — partagé entre tous les runs du process.

---

### 2. `app/services/guarded_mcp_executor.py` — NEW

Wrapper AOP autour de `invoke_mcp()`.

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
) -> MCPInvocation
```

Même signature que `invoke_mcp()` — drop-in replacement.

**Logique :**
```python
async def guarded_invoke_mcp(...) -> MCPInvocation:
    # [1] AllowlistCheck — déjà dans invoke_mcp, pas dupliqué ici

    # [2] Récupérer l'agent et ses forbidden_effects
    agent = await db.get(AgentDefinition, calling_agent_id)
    forbidden = set(agent.forbidden_effects or []) if agent else set()

    # [3] Classifier si forbidden_effects configurés
    if forbidden and tool_action:
        effect = await _classifier.classify(tool_action, tool_kwargs or {})
        if effect in forbidden:
            inv = MCPInvocation(
                run_id=run_id,
                subagent_invocation_id=subagent_invocation_id,
                mcp_id=mcp_id,
                effect_type=effect,           # effet classifié
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
                                 "effect": effect,
                             })
            return inv

    # [4] Délègue au moteur existant
    return await invoke_mcp(db, run_id, mcp_id, calling_agent_id,
                            subagent_invocation_id, tool_action, tool_kwargs)
```

**Point d'injection :** Remplacer `invoke_mcp` par `guarded_invoke_mcp` dans le(s) service(s) appelant. Chercher `from app.services.mcp_executor import invoke_mcp` dans le codebase.

---

### 3. Frontend — Badge dans RunGraph

**Fichier :** `frontend/src/components/test-lab/run-graph/RunGraph.tsx`

Les tool calls apparaissent dans les events `mcp.denied` avec `payload.reason = "forbidden_effect"`. Le RunGraph doit afficher un badge rouge sur les nœuds concernés.

**Logique :**
- Filtrer les events `mcp.denied` où `payload.reason === "forbidden_effect"`
- Sur le nœud runtime (ou le sous-nœud tool call si présent), afficher un badge :
  ```
  ⛔ blocked: {effect}
  ```
- Couleur : `--ork-red` / `--ork-red-bg` (cohérent avec le design system)
- Tooltip : `"effect '{effect}' is forbidden for this agent"`

**Distinction visuelle :**
- `reason: "not in agent allowlist"` → badge gris "denied"
- `reason: "forbidden_effect"` → badge rouge "blocked: {effect}"

---

## Tests

### Unit — `effect_classifier.py`

| Test | Description |
|------|-------------|
| `test_classify_known_tool` | `classify("write_file", {})` → `"write"` |
| `test_classify_uses_cache` | 2ème appel → pas d'appel LLM (mock vérifie 1 seul call) |
| `test_classify_fallback_on_llm_failure` | LLM timeout → heuristique retourne `"write"` pour `write_doc` |
| `test_classify_fallback_unknown_tool` | Tool inconnu → `"compute"` (défaut) |
| `test_classify_invalid_llm_response` | LLM retourne `"destroy"` (invalide) → fallback heuristique |

### Unit — `guarded_mcp_executor.py`

| Test | Description |
|------|-------------|
| `test_blocks_forbidden_effect` | Agent avec `forbidden_effects=["write"]`, tool classifié `write` → status `"denied"` |
| `test_allows_permitted_effect` | Agent avec `forbidden_effects=["write"]`, tool classifié `read` → délègue à `invoke_mcp` |
| `test_no_forbidden_effects_configured` | `forbidden_effects=[]` → délègue directement, pas d'appel classifier |
| `test_emit_event_on_block` | Vérifie que `mcp.denied` avec `reason="forbidden_effect"` est émis |
| `test_allowlist_check_still_works` | `allowed_mcps` enforcement reste fonctionnel (via `invoke_mcp` interne) |
| `test_no_tool_action_skips_classifier` | `tool_action=None` → pas de classification, délègue directement |

### Integration

| Test | Description |
|------|-------------|
| `test_full_run_forbidden_write` | Run complet avec agent `forbidden_effects=["write"]` + tool `write_file` → invocation `denied` en DB |
| `test_full_run_allowed_read` | Run complet avec agent `forbidden_effects=["write"]` + tool `read_file` → invocation `completed` |

### Frontend Component

| Test | Description |
|------|-------------|
| `test_badge_shown_for_blocked_effect` | Event `mcp.denied` + `reason=forbidden_effect` → badge rouge visible |
| `test_badge_not_shown_for_allowlist_deny` | Event `mcp.denied` + `reason=not in agent allowlist` → badge gris, pas rouge |

---

## Non-inclus (YAGNI)

- Soft enforcement (log-only) en prod — l'enforcement est toujours bloquant
- Gestion des effets composés (un tool avec deux effets simultanés)
- Interface d'admin pour override par run
- Historique des violations dans l'onglet agent edit (peut être ajouté plus tard)
