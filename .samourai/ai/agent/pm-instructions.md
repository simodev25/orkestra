# PM Instructions — Orkestra

> Ce fichier configure le comportement de `@pm` pour ce projet.
> Il ne répète pas le lifecycle standard Samourai — voir `.samourai/core/governance/conventions/change-lifecycle.md`.
> La langue de travail est le **français** (choix verrouillé).

---

## Configuration Tracker

| Paramètre | Valeur |
|-----------|--------|
| Type | GitHub Issues |
| Propriétaire | `simodev25` |
| Dépôt | `orkestra` |
| URL | `https://github.com/simodev25/orkestra` |
| Accès | `gh` CLI (authentifié, compte `simodev25`) |

---

## Mapping États Workflow

GitHub Issues utilise des **labels** pour le workflow (pas de transition IDs).

| Phase Samourai | Label GitHub | Notes |
|----------------|-------------|-------|
| En attente de démarrage | *(aucun label spécifique)* | Issue ouverte, priorité backlog |
| Livraison démarrée | `change` | Ajouté quand `@pm` prend en charge |
| En cours | `in-progress` | Ajouté au début de `delivery` |
| En review | `review` | Ajouté lors de `review_fix` |
| Bloqué | `blocked` | Ajouté si bloqueur identifié |
| Livré | `delivered` | Ajouté à `pr_creation`, issue fermée |

---

## Taxonomie des Labels

Labels minimaux requis :

| Label | Usage |
|-------|-------|
| `change` | Toute issue en cours de livraison Samourai |
| `in-progress` | Livraison active |
| `review` | En phase `review_fix` |
| `blocked` | Bloqueur identifié |
| `delivered` | PR créée, en attente de merge humain |
| `type:bug` | Correction de bug |
| `type:feature` | Nouvelle fonctionnalité |
| `type:refactor` | Refactoring sans changement fonctionnel |
| `type:doc` | Documentation uniquement |
| `priority:critical` | Bloquant production |
| `priority:high` | Important, livrable sprint actuel |
| `priority:low` | Nice-to-have |

---

## Source de Vérité du Backlog

Le backlog est dans **GitHub Issues** : `https://github.com/simodev25/orkestra/issues`

`@pm` interroge les issues via `gh` CLI :
```bash
# Issues ouvertes (toutes)
gh issue list --repo simodev25/orkestra --state open

# Issues en cours de livraison
gh issue list --repo simodev25/orkestra --label "change" --state open

# Issue prioritaire
gh issue list --repo simodev25/orkestra --state open --label "priority:critical"
```

---

## Conventions

| Convention | Valeur |
|------------|--------|
| `workItemRef` | `GH-<numéro>` — ex: `GH-12` |
| Branche | `<type>/GH-<numéro>/<slug>` — ex: `feat/GH-12/agent-versioning` |
| Commit | Conventional Commits — ex: `feat(registry): add agent versioning` |
| Dossier change | `.samourai/docai/changes/YYYY-MM/YYYY-MM-DD--GH-<n>--<slug>/` |

---

## Mode Projet

| Paramètre | Valeur |
|-----------|--------|
| Mode | Build — livraison de features actives |
| Âge | Nouveau (<1 an) |
| Équipe | Solo |
| Complexité | Élevée |

## Règles de Backlog & Priorisation (Build)

- Prioriser par valeur métier × risque de livraison.
- Aucun ticket n'entre en livraison sans : titre, critères d'acceptance (AC), périmètre, et au moins une vérification de dépendances.
- Préférer les incréments livrables petits — découper tout ticket estimé > 3 jours.
- Signaler immédiatement les breaking changes ; ils nécessitent un ticket de migration séparé.

## Règles spécifiques Orkestra

- Avant toute orchestration : lire `docs/architecture.md` et `docs/operating-model.md`.
- Les sujets suivants nécessitent **confirmation humaine** avant délégation :
  - Toute modification de `app/state_machines/` (lifecycle state machine)
  - Toute modification de `app/services/audit_service.py` (table append-only)
  - Toute modification de `app/services/secret_service.py` (secrets chiffrés)
  - Tout changement de schéma DB (`app/models/`) — migration Alembic obligatoire
- Disambiguation terminologique : dans chaque ticket ambigu, clarifier si "agent" désigne un `AgentDefinition` Orkestra (enregistrement DB) ou un agent OpenCode (`@pm`, `@coder`…).

## Références Qualité

Avant de créer la PR (`pr_creation`), `@runner` doit confirmer :

```bash
# Tests
pytest tests/ -v

# Lint
ruff check app/ && ruff format app/ --check

# Si schéma modifié
alembic upgrade head
```

## Workflow PR

- `@pm` est seul développeur — aucune approbation externe requise.
- `@pr-manager` crée la PR via `gh pr create`.
- `@pm` assigne la PR à `simodev25` (auteur = reviewer humain).
- `@pm` s'arrête après création de la PR — le merge est manuel.
- `@reviewer` fonctionne en mode **advisory** (FAIL n'est pas bloquant pour le merge).
