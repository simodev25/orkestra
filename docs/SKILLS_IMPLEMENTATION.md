# Skill Registry — Implémentation Orkestra

## Vue d'ensemble

`skills.seed.json` est désormais la **source de vérité** pour les skills du projet. Le chargement est réalisé au démarrage de l'application via le lifespan FastAPI. Les agents référencent les skills par `skill_id` uniquement ; Orkestra résout automatiquement les métadonnées complètes au moment du bootstrap ou de la mise à jour d'un agent.

---

## 1. Où le seed est chargé

### Point d'entrée : `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Orkestra {settings.APP_VERSION} starting")
    try:
        skill_registry_service.load_skills()   # ← charge le seed ici
    except Exception as exc:
        logger.error(f"Failed to load skills.seed.json: {exc}")
        raise
    yield
```

Le seed est chargé **une seule fois**, avant que l'API ne traite des requêtes. Si le JSON est absent ou invalide, l'application refuse de démarrer.

---

## 2. Comment les skills sont résolus dans les agents

### Registre mémoire : `app/services/skill_registry_service.py`

```python
_registry: dict[str, SkillSeedEntry] = {}   # skill_id → entrée validée
```

Fonctions clés :

| Fonction | Rôle |
|---|---|
| `load_skills()` | Lit `config/skills.seed.json`, valide, peuple `_registry` |
| `resolve_skills(skill_ids)` | Retourne `(resolved: list[SkillRef], unresolved: list[str])` |
| `build_skills_content(skill_ids)` | Génère le JSON collant pour `AgentDefinition.skills_content` |

### Branchement dans `agent_registry_service`

- **`validate_agent_definition`** — vérifie que chaque `skill_id` déclaré par un agent existe dans le registre. Erreur claire si un agent déclare un skill inconnu.
- **`_apply_create_payload`** — si `skills_content` n'est pas fourni explicitement, il est auto-généré à partir du seed via `build_skills_content`.
- **`update_agent`** — même logique : quand `skills` est modifié, `skills_content` est recalculé.
- **`enrich_agent_skills`** — au moment de retourner un agent via l'API, attaches `skills_resolved` avec les métadonnées complètes.

### Structure finale d'un agent résolu

```json
{
  "id": "requirements_analyst",
  "name": "Requirements Analyst",
  "skills": ["user_need_reformulation", "requirements_extraction"],
  "skills_resolved": [
    {
      "skill_id": "user_need_reformulation",
      "label": "User Need Reformulation",
      "category": "preparation",
      "skills_content": {
        "description": "Transform a raw user request...",
        "behavior_templates": ["Reformulate the user request..."],
        "output_guidelines": ["Always preserve semantic fidelity..."]
      }
    }
  ]
}
```

> `skills_resolved` est un attribut transient (non persisté en base) — la vérité reste dans `skills.seed.json`.

---

## 3. Comment l'UI récupère les données

### Nouveau router : `GET /api/skills/with-agents`

```json
GET /api/skills/with-agents

[
  {
    "skill_id": "user_need_reformulation",
    "label": "User Need Reformulation",
    "category": "preparation",
    "description": "Transform a raw user request...",
    "agents": [
      { "agent_id": "requirements_analyst", "label": "Requirements Analyst" }
    ]
  }
]
```

Ce endpoint agrège :
- Les métadonnées du seed (via `skill_registry_service`)
- Les agents qui référencent chaque `skill_id` (via `agent_registry_service.list_agents`)

### Endpoints disponibles

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/api/skills` | Liste plate de tous les skills |
| `GET` | `/api/skills/{skill_id}` | Détail d'un skill |
| `GET` | `/api/skills/with-agents` | Skills + agents qui les utilisent |

---

## 4. Schémas ajoutés (`app/schemas/skill.py`)

| Schéma | Usage |
|---|---|
| `SkillSeedEntry` | Validation d'une entrée du JSON seed |
| `SkillSeedPayload` | Validation du root du JSON |
| `SkillContent` | Contenu consommé par les agents (`description`, `behavior_templates`, `output_guidelines`) |
| `SkillRef` | Skill minimal inclus dans `AgentOut.skills_resolved` |
| `SkillOut` | Skill exposé par l'API `/api/skills` |
| `AgentSummary` | Agent minimal pour `SkillWithAgents.agents` |
| `SkillWithAgents` | Vue agrégée skill → agents pour l'UI |

---

## 5. Fichiers modifiés et créés

| Fichier | Action | Raison |
|---|---|---|
| `app/schemas/skill.py` | **Créé** | Nouveaux schémas Pydantic pour skills |
| `app/services/skill_registry_service.py` | **Créé** | Loader, registre mémoire, résolution |
| `app/api/routes/skills.py` | **Créé** | Nouveaux endpoints REST pour l'UI |
| `app/schemas/agent.py` | Modifié | Ajout de `skills_resolved: Optional[list[SkillRef]]` sur `AgentOut` |
| `app/services/agent_registry_service.py` | Modifié | Validation des skill_ids, auto-generation `skills_content`, `enrich_agent_skills()` |
| `app/main.py` | Modifié | Import du router skills, chargement au startup |
| `tests/test_skill_registry.py` | **Créé** | 14 tests unitaires |

---

## 6. Validation du seed

`_validate_entries` détecte à froid :

- `skill_id` manquant ou vide
- `skill_id` dupliqué dans le fichier
- `label`, `category`, `description` vides
- `behavior_templates` ou `output_guidelines` vides

L'application refuse de démarrer si le seed est invalide.
