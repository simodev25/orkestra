# Orkestra — Instructions Agents

## Ce qu'est ce dépôt

Orkestra Mesh est une plateforme de registry et de test lab pour agents IA.
Elle permet de définir, versionner, et tester des agents IA avec des métadonnées structurées
et une machine à états lifecycle. Ce n'est **pas** un système de déploiement.

Quatre préoccupations principales :
1. **Agent Registry** — CRUD + versioning + machine à états lifecycle (`draft → active → archived`)
2. **MCP Integration** — synchronisation du catalog Obot, binding par agent
3. **Test Lab** — scénarios de test exécutés contre de vrais agents (LLM + MCP réels), évaluation non-déterministe
4. **Gouvernance** — audit append-only, approval workflows, effect classification

## Stack technique

| Couche | Technologie |
|--------|-------------|
| API | FastAPI 0.115+, Python 3.12, SQLAlchemy 2.0 (async) |
| Base de données | PostgreSQL 16, AsyncPG, Alembic (migrations) |
| Queue async | Celery + Redis (uniquement Test Lab) |
| LLM runtime | AgentScope ReActAgent + Ollama / OpenAI-compatible |
| MCP tools | Catalog Obot (externe) |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Observabilité | OpenTelemetry + Prometheus + Grafana + Tempo |
| Qualité | Ruff (lint+format, line-length=100), Pytest + pytest-asyncio, Vitest |
| Infrastructure | Docker + docker-compose |

## Règles de travail

- Lire ce fichier avant de modifier quoi que ce soit dans ce projet.
- Les agents doivent **toujours communiquer en français**.
- Garder les changements dans le périmètre demandé — ne pas étendre le scope sans validation.
- Ne jamais lire, afficher, stocker ou copier des secrets.
- Proposer avant toute action destructive ou externe.
- Tout changement de schéma DB (`app/models/`) = nouvelle migration Alembic obligatoire.
- Stack Python **async uniquement** : `async with` sessions, jamais de sessions sync.

## Terminologie critique (disambiguation)

| Terme dans ce repo | Signification Orkestra | À ne pas confondre avec |
|--------------------|----------------------|-------------------------|
| `agent` | Enregistrement `AgentDefinition` en base | Agent OpenCode (`@pm`, `@coder`…) |
| `skill` | Bloc de prompt injecté dans un agent Orkestra | Skill OpenCode |
| `lifecycle` | Machine à états `draft→active→archived` | Cycle CI/CD |
| `mcp` | Protocole MCP (outils) OU catalog Obot | — |
| `runner` | Tâche Celery du Test Lab | Agent OpenCode `@runner` |
| `registry` | Sous-système Agent Registry d'Orkestra | Registry Python/npm |

## Zones critiques — protection obligatoire

⛔ Ces zones nécessitent **confirmation humaine** avant toute modification :
- `app/state_machines/` — transitions lifecycle
- `app/services/audit_service.py` — table append-only
- `app/services/secret_service.py` — secrets Fernet-chiffrés
- `app/services/effect_classifier.py` — gouvernance des effets
- `app/models/` — tout changement = migration Alembic

## Commandes de vérification

```bash
# Tests rapides (sans DB)
pytest tests/ -v -k "not integration and not e2e"

# Suite complète
pytest tests/ -v

# Lint + format
ruff check app/ && ruff format app/

# Migration DB (après changement de schéma)
alembic revision --autogenerate -m "description"
alembic upgrade head

# Stack complète
docker-compose up
```

## Chemins Samourai

- Documentation projet : `.samourai/docai/`
- État local (git-ignoré) : `.samourai/ai/local/`
- Configuration agents : `.samourai/ai/agent/`
- Fichiers temporaires : `.samourai/tmpai/`
- Profil projet : `.samourai/ai/agent/project-profile.md`

## Références clés

- Vue d'ensemble : `README.md`
- Architecture : `docs/architecture.md`
- Concepts domaine : `docs/concepts.md`
- Modèle opérationnel : `docs/operating-model.md`
- Test Lab : `docs/test-lab.md` + `docs/TEST_LAB_ARCHITECTURE.md`
- Tests : `tests/`
- Frontend : `frontend/src/app/`

## Profil opérationnel

Le profil de complexité de ce projet est défini dans `.samourai/ai/agent/project-profile.md`.
Tous les agents doivent l'appliquer lors du planning, de l'implémentation, des corrections,
de la review, et du reporting final.
