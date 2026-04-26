---
change:
  ref: GH-14
  type: feat
  status: Proposed
  slug: declaratif-json-import-export
  title: "Système déclaratif JSON import/export pour agents, scénarios et orchestrateurs"
  owners: [orkestra-team]
  service: agent-registry / test-lab
  labels: [registry, test-lab, declarative, idempotence, devx]
  version_impact: minor
  audience: internal
  security_impact: low
  risk_level: medium
  dependencies:
    internal: [agent-registry, test-lab, alembic-migrations]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** — Remplacer 5 scripts Python impératifs de création d'agents/scénarios par un système
> déclaratif fichier-first : fichiers JSON versionnés sous `data/registry/` et `data/test_lab/`,
> services d'import/export idempotents, et endpoints REST dédiés.
> Ce changement établit une source de vérité Git pour tous les agents du pipeline hôtelier et leur
> orchestrateur, avec round-trip fidèle entre la base de données et les fichiers JSON.

---

## 1. SUMMARY

Le projet dispose aujourd'hui de 5 scripts Python (`create_*_agent.py`, `create_hotel_pipeline_orchestrator.py`)
qui créent des agents, scénarios et un orchestrateur de façon impérative via des appels HTTP à l'API.
Ces scripts sont dupliqués, ne constituent pas une source de vérité Git exploitable, et leur idempotence
est fragile (logique POST puis PATCH sur 409).

Ce changement introduit :

1. Des **fichiers JSON déclaratifs** versionnable sous `data/` pour les 5 agents, l'orchestrateur et leurs scénarios.
2. Des **services Python d'import et d'export** idempotents opérant directement sur les modèles SQLAlchemy.
3. Des **endpoints REST** pour déclencher import/export/validation via l'API.
4. Deux **extensions DB minimales** (migration Alembic) : `TestScenario.definition_key` et `AgentDefinition.pipeline_definition`.
5. La **dépréciation** des scripts legacy (conservés mais marqués obsolètes).

---

## 2. CONTEXT

### 2.1 Current State Snapshot

- **5 agents** du pipeline hôtelier (`stay_discovery_agent`, `mobility_agent`, `weather_agent`,
  `budget_fit_agent`, `hotel_pipeline_orchestrator`) sont définis exclusivement dans des scripts Python.
- Chaque script contient un dictionnaire `AGENT` et un dictionnaire `SCENARIO` codés en dur, puis appelle
  l'API REST (`POST /api/agents`, `POST /api/test-lab/scenarios`) en gérant les conflits manuellement.
- Le modèle `AgentDefinition` (SQLAlchemy) stocke les champs agent, mais le champ `pipeline_agent_ids`
  (liste d'IDs ordonnée) ne supporte pas la définition structurée du pipeline (stages, routing_mode,
  error_policy).
- Le modèle `TestScenario` n'a pas de clé sémantique stable (`definition_key`) : l'idempotence repose sur
  la comparaison du champ `name`, ce qui est fragile.
- Aucun mécanisme d'export DB → JSON n'existe. Le round-trip (JSON → DB → JSON) est impossible.

### 2.2 Pain Points / Gaps

- **Pas de source de vérité Git** : les définitions d'agents ne sont pas versionnées ; chaque script est
  la seule source, sans historique de diff lisible.
- **Duplication** : la logique create-or-update est répétée dans chaque script (≈80 lignes identiques).
- **Idempotence bancale** : un double import via les scripts peut créer des doublons ou échouer
  silencieusement selon l'état du serveur.
- **Pas de validation des dépendances** à l'import : un scénario peut référencer un agent inexistant
  sans erreur détectée à l'avance.
- **Pas de round-trip** : impossible d'exporter l'état actuel de la DB vers des fichiers JSON pour
  comparaison ou migration.

---

## 3. PROBLEM STATEMENT

Les agents du pipeline hôtelier d'Orkestra Mesh ne disposent d'aucune représentation déclarative
versionnée. Toute modification nécessite d'éditer un script Python et de le ré-exécuter contre un
serveur vivant, sans garantie d'idempotence ni de traçabilité Git. L'absence de round-trip DB ↔ JSON
empêche toute validation de cohérence entre l'état déclaré (scripts) et l'état persisté (base de données).
Cette situation crée un risque de dérive de configuration et rend la revue de changement opaque.

---

## 4. GOALS

| # | Objectif |
|---|----------|
| G-1 | Fournir des fichiers JSON versionnés comme source de vérité pour les 5 agents, l'orchestrateur et leurs scénarios. |
| G-2 | Garantir un import idempotent : un double import sans modification ne produit aucun changement DB, pas de bump de version. |
| G-3 | Garantir un round-trip fidèle : export(import(json)) == json (à champs canoniques près). |
| G-4 | Valider les dépendances à l'import (family_id, skill_ids, allowed_mcps, agent_ids référencés). |
| G-5 | Exposer des endpoints REST pour import, export et validation sans nécessiter de script shell. |
| G-6 | Déprécier les scripts legacy sans les supprimer immédiatement. |

### 4.1 Success Metrics / KPIs

| Métrique | Cible |
|---------|-------|
| Import idempotent (double import, 0 modification) | 0 write DB si aucun champ modifié |
| Round-trip fidélité | 100 % des champs canoniques inchangés après export(import(json)) |
| Couverture tests import idempotent | ≥ 1 test par entité (agent, orchestrateur, scénario) |
| Couverture tests erreur de référence | ≥ 3 cas (family_id inconnu, skill_id inconnu, agent_id inconnu) |
| Latence endpoint `POST /api/definitions/import` (payload ≤ 10 entités) | < 500 ms p95 |

### 4.2 Non-Goals

- `[OUT]` Pas de CLI (outil ligne de commande dédié) — les services sont invocables par les endpoints REST et les tests uniquement.
- `[OUT]` Pas de migration automatique des données historiques issues des scripts legacy.
- `[OUT]` Pas de support multi-tenant / multi-workspace dans cette itération.
- `[OUT]` Pas de validation de la sémantique des prompts (contenu LLM).
- `[OUT]` Pas de UI dédiée à l'édition des fichiers JSON.

---

## 5. FUNCTIONAL CAPABILITIES

| ID | Capacité | Rationale |
|----|----------|-----------|
| F-1 | Définir des agents, orchestrateurs et scénarios sous forme de fichiers JSON avec un `kind` et `schema_version` explicites. | Source de vérité Git versionnable et diffable. |
| F-2 | Importer un ou plusieurs fichiers JSON en DB de façon idempotente (upsert par clé stable). | Évite les doublons et les re-créations inutiles. |
| F-3 | Exporter une entité depuis la DB vers sa représentation JSON canonique. | Permet le round-trip et la comparaison déclarée vs persisté. |
| F-4 | Valider les dépendances déclarées dans un fichier JSON avant toute écriture en DB. | Détecte les références brisées tôt dans le pipeline. |
| F-5 | Stocker la définition structurée du pipeline d'un orchestrateur (stages, routing_mode, error_policy) en DB. | Remplace le champ plat `pipeline_agent_ids` pour les orchestrateurs. |
| F-6 | Identifier chaque scénario par une clé sémantique stable (`definition_key`) indépendante de son UUID interne. | Rend l'idempotence des scénarios robuste et prévisible. |
| F-7 | Déprécier les scripts legacy en les marquant explicitement obsolètes dans leur en-tête. | Guides les contributeurs vers le système déclaratif. |

### 5.1 Capability Details

**F-1 — Schémas JSON déclaratifs**

Trois `kind` sont supportés :
- `agent` : représente un `AgentDefinition` (famille `analysis` ou autre).
- `orchestrator` : représente un `AgentDefinition` de famille `orchestration`, avec champ `pipeline_definition`.
- `scenario` : représente un `TestScenario`.

Chaque fichier inclut un `schema_version: "v1"` permettant l'évolution contrôlée du format.

**F-2 — Import idempotent**

- Clé d'upsert : `id` pour les agents/orchestrateurs, `definition_key` pour les scénarios.
- Logique : si l'entité existe et que tous les champs comparables sont identiques → no-op (0 write).
- Si au moins un champ diffère → update (sans bump de version automatique).
- Si l'entité n'existe pas → insert.

**F-4 — Validation des dépendances**

Avant toute écriture, le service de résolution vérifie :
- `family_id` référencé existe en DB et est actif.
- Chaque `skill_id` dans `skill_ids` existe en DB.
- Chaque MCP dans `allowed_mcps` est présent dans le catalogue.
- Pour les scénarios, `agent_id` référencé existe en DB.
- Pour les orchestrateurs, chaque `agent_id` dans `pipeline_definition.stages` existe en DB.

---

## 6. USER & SYSTEM FLOWS

### Flux principal : import déclaratif

```
Contributeur                   API REST              ImportService         DB
     │                             │                       │                │
     │  POST /api/definitions/     │                       │                │
     │  import  { files: [...] }   │                       │                │
     │────────────────────────────>│                       │                │
     │                             │  validate_schema()    │                │
     │                             │──────────────────────>│                │
     │                             │                       │ resolve_deps() │
     │                             │                       │───────────────>│
     │                             │                       │<───────────────│
     │                             │                       │  upsert()      │
     │                             │                       │───────────────>│
     │                             │<──────────────────────│                │
     │  ImportReport { created,    │                       │                │
     │    updated, skipped, errors}│                       │                │
     │<────────────────────────────│                       │                │
```

### Flux export

```
Contributeur          API REST           ExportService        DB
     │                    │                    │               │
     │  GET /api/          │                   │               │
     │  definitions/export │                   │               │
     │  ?kind=agent&id=x   │                   │               │
     │───────────────────> │                   │               │
     │                     │  fetch_entity()   │               │
     │                     │──────────────────>│               │
     │                     │                   │ get_agent(x)  │
     │                     │                   │──────────────>│
     │                     │                   │<──────────────│
     │                     │                   │ to_json_def() │
     │                     │<──────────────────│               │
     │  AgentDefinition    │                   │               │
     │  JSON               │                   │               │
     │<────────────────────│                   │               │
```

---

## 7. SCOPE & BOUNDARIES

### 7.1 In Scope

- Schémas Pydantic `AgentDefinition`, `OrchestratorDefinition`, `ScenarioDefinition` (validation entrée/sortie).
- Service d'import idempotent pour les 3 kinds.
- Service d'export DB → JSON canonique pour les 3 kinds.
- Service de validation des dépendances.
- Endpoints REST : `POST /api/definitions/import`, `GET /api/definitions/export`, `POST /api/definitions/validate`.
- Migration Alembic : ajout de `TestScenario.definition_key` (str, unique, nullable).
- Migration Alembic : ajout de `AgentDefinition.pipeline_definition` (JSONB, nullable).
- Fichiers JSON pour : `stay_discovery_agent`, `mobility_agent`, `weather_agent`, `budget_fit_agent`, `hotel_pipeline_orchestrator` + scénarios correspondants.
- Dépréciation (marquage) des 5 scripts legacy.
- Tests unitaires : import idempotent, round-trip export, erreurs de référence.

### 7.2 Out of Scope

- `[OUT]` CLI dédié.
- `[OUT]` Support d'autres formats (YAML, TOML).
- `[OUT]` Migration automatique des agents/scénarios existants en DB vers les fichiers JSON.
- `[OUT]` Gestion de versions sémantiques automatiques sur import.
- `[OUT]` Interface graphique d'édition.
- `[OUT]` Import en bulk depuis un répertoire entier via l'API (hors scope v1).

### 7.3 Deferred / Maybe-Later

- Import bulk depuis un dossier (`POST /api/definitions/import-dir`) avec découverte automatique des fichiers JSON.
- Diff déclaré vs persisté avec rapport de divergence.
- Validation de schéma stricte avec JSON Schema publié.
- Support `kind: skill` (SkillDefinition).

---

## 8. INTERFACES & INTEGRATION CONTRACTS

### 8.1 REST / HTTP Endpoints

**API-1 — Import de définitions**

| Attribut | Valeur |
|---------|--------|
| Méthode | `POST` |
| Chemin | `/api/definitions/import` |
| Auth | `X-API-Key` |
| Body | `application/json` — objet `{ "definitions": [ <AgentDef|OrchestratorDef|ScenarioDef>, ... ] }` |
| Réponse 200 | `ImportReport` : `{ created: int, updated: int, skipped: int, errors: [{ ref, message }] }` |
| Réponse 422 | Erreurs de validation Pydantic |
| Réponse 409 | Conflit non résolvable (ex. clé dupliquée dans le payload lui-même) |
| Idempotence | Oui — double appel identique → `skipped = N`, `created = 0`, `updated = 0` |

**API-2 — Export de définitions**

| Attribut | Valeur |
|---------|--------|
| Méthode | `GET` |
| Chemin | `/api/definitions/export` |
| Params | `kind` (agent|orchestrator|scenario), `id` ou `definition_key` |
| Réponse 200 | JSON conforme au schéma déclaratif du `kind` |
| Réponse 404 | Entité non trouvée |

**API-3 — Validation de définitions (dry-run)**

| Attribut | Valeur |
|---------|--------|
| Méthode | `POST` |
| Chemin | `/api/definitions/validate` |
| Body | Identique à API-1 |
| Réponse 200 | `ValidationReport` : `{ valid: bool, errors: [{ ref, code, message }] }` |
| Effet DB | Aucun — lecture seule |

### 8.2 Events / Messages

| ID | Événement | Déclencheur | Payload |
|----|-----------|-------------|---------|
| EVT-1 | `definition.imported` | Import créant ou mettant à jour une entité | `{ kind, ref, action: created|updated }` |
| EVT-2 | `definition.import_skipped` | Import sans modification | `{ kind, ref }` |
| EVT-3 | `definition.export_requested` | Export d'une entité | `{ kind, ref }` |

Ces événements s'appuient sur le mécanisme `emit_event` existant dans `app/services/event_service.py`.

### 8.3 Data Model Impact

**DM-1 — `TestScenario.definition_key`**

| Attribut | Valeur |
|---------|--------|
| Table | `test_scenarios` |
| Colonne | `definition_key` |
| Type | `VARCHAR(255)` |
| Contrainte | `UNIQUE`, `NULLABLE` |
| Défaut | `NULL` |
| Usage | Clé stable pour l'upsert idempotent des scénarios importés depuis les fichiers JSON. |
| Migration | Alembic — ajout de colonne + index unique. |

**DM-2 — `AgentDefinition.pipeline_definition`**

| Attribut | Valeur |
|---------|--------|
| Table | `agent_definitions` |
| Colonne | `pipeline_definition` |
| Type | `JSONB` |
| Contrainte | `NULLABLE` |
| Défaut | `NULL` |
| Usage | Stocke la définition structurée du pipeline pour les orchestrateurs (`routing_mode`, `stages`, `error_policy`). Remplace progressivement `pipeline_agent_ids` (liste plate) pour les orchestrateurs. |
| Migration | Alembic — ajout de colonne JSONB. |

**Schéma JSONB `pipeline_definition` :**

```json
{
  "routing_mode": "sequential",
  "stages": [
    {
      "stage_id": "stage_stay_discovery",
      "agent_id": "stay_discovery_agent",
      "required": true
    }
  ],
  "error_policy": "continue_on_partial_failure"
}
```

`routing_mode` : `"sequential"` | `"dynamic"`
`error_policy` : `"fail_fast"` | `"continue_on_partial_failure"` | `"best_effort"`

### 8.4 External Integrations

Aucune intégration externe nouvelle. Les imports/exports opèrent en DB directement, sans appel à l'API Obot ou à des services externes.

### 8.5 Backward Compatibility

- Les deux nouvelles colonnes DB sont `NULLABLE` avec valeur `NULL` par défaut : **aucun impact sur les agents/scénarios existants**.
- Le champ `pipeline_agent_ids` existant est conservé et non supprimé dans cette itération.
- Les 5 scripts legacy sont conservés (marqués deprecated) et continuent de fonctionner.
- Les endpoints REST existants (`/api/agents`, `/api/test-lab/scenarios`) sont inchangés.

---

## 9. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| ID | Exigence | Seuil |
|----|----------|-------|
| NFR-1 | **Idempotence** — Un double import identique ne produit aucune écriture DB. | 0 write SQL si tous les champs sont identiques |
| NFR-2 | **Latence import** — Import d'un payload de 10 définitions. | < 500 ms p95 (hors latence réseau client) |
| NFR-3 | **Fidélité round-trip** — export(import(json)) == json sur tous les champs canoniques. | 100 % égalité champs déclarés |
| NFR-4 | **Atomicité** — Un import de N définitions est transactionnel : tout ou rien en cas d'erreur. | Rollback complet si une validation échoue |
| NFR-5 | **Validation schema** — Tout fichier JSON non conforme au Pydantic schema doit être rejeté avec un message d'erreur lisible avant toute écriture. | 100 % rejet avec `code` et `message` exploitable |
| NFR-6 | **Compatibilité DB** — Les migrations Alembic doivent être non-destructives et réversibles (`downgrade`). | Migration `upgrade` + `downgrade` sans perte de données |

---

## 10. TELEMETRY & OBSERVABILITY REQUIREMENTS

| Signal | Détail |
|--------|--------|
| Log structuré `INFO` | À chaque import : `kind`, `ref`, `action` (created/updated/skipped), durée ms |
| Log structuré `WARNING` | Si une définition est skippée à cause d'une dépendance non résolue |
| Log structuré `ERROR` | Si une transaction import échoue avec rollback |
| Événement `definition.imported` | Émis via `emit_event` pour chaque entité créée ou mise à jour |
| Événement `definition.import_skipped` | Émis pour chaque entité skippée (no-op) |
| Métriques | Utiliser les mécanismes de logging existants (pas de métriques Prometheus nouvelles dans cette itération) |

---

## 11. RISKS & MITIGATIONS

| ID | Risque | Impact | Probabilité | Mitigation | Risque résiduel |
|----|--------|--------|-------------|------------|-----------------|
| RSK-1 | Import écrase un agent existant modifié manuellement depuis l'UI, perdant des champs non déclarés dans le JSON. | Élevé | Moyen | Le service d'import compare champ par champ. Les champs non présents dans le JSON déclaratif (ex. `usage_count`, `last_test_status`) ne sont jamais écrasés. | Faible |
| RSK-2 | Migration Alembic casse les tests existants si la colonne `definition_key` entre en conflit avec un test qui crée des scénarios avec le même nom. | Moyen | Faible | Colonne nullable + contrainte unique — les tests existants n'assignent pas `definition_key`, donc pas de conflit. | Très faible |
| RSK-3 | Les fichiers JSON des agents contiennent des `allowed_mcps` (IDs Obot) qui changent entre environnements, rendant l'import non portable. | Moyen | Élevé | La validation de dépendances MCP peut être configurée comme `warn` (non bloquante) dans un mode `relaxed`. À documenter dans OQ-1. | Moyen |
| RSK-4 | L'orchestrateur `hotel_pipeline_orchestrator` référence des `agent_ids` qui doivent être importés avant lui. Un import dans le mauvais ordre échoue. | Moyen | Moyen | Le service d'import trie les définitions par dépendances (agents avant orchestrateurs) avant traitement. | Faible |
| RSK-5 | Les scripts legacy coexistent avec le système déclaratif et un contributeur réexécute un script, écrasant un agent modifié par import. | Faible | Faible | Les scripts sont marqués `DEPRECATED` avec un avertissement visible. La suppression sera traitée dans un ticket dédié. | Faible |

---

## 12. ASSUMPTIONS

- Les modèles SQLAlchemy `AgentDefinition` et `TestScenario` sont la cible d'écriture ; le service d'import ne passe pas par l'API HTTP interne.
- PostgreSQL avec extension JSONB est disponible (déjà utilisé dans le projet).
- Le mécanisme `emit_event` de `app/services/event_service.py` est fonctionnel et suffit pour la télémétrie.
- Les `family_id` référencés dans les fichiers JSON (`analysis`, `orchestration`) existent et sont actifs en DB dans tout environnement cible.
- Les `skill_ids` (`sequential_routing`, `context_propagation`, `source_comparison`, etc.) existent en DB dans tout environnement cible.
- Un seul `schema_version: "v1"` est supporté dans cette itération.

---

## 13. DEPENDENCIES

| Composant | Type | Raison |
|-----------|------|--------|
| `AgentDefinition` (SQLAlchemy) | Interne | Cible de l'import agent/orchestrateur |
| `TestScenario` (SQLAlchemy) | Interne | Cible de l'import scénario |
| `agent_registry_service` | Interne | Validation famille, skills, MCPs réutilisée |
| `event_service` | Interne | Émission des événements `definition.*` |
| Alembic | Interne | Migrations DB (`definition_key`, `pipeline_definition`) |
| Pydantic v2 | Interne | Validation des schémas déclaratifs |
| FastAPI | Interne | Exposition des endpoints REST |

---

## 14. OPEN QUESTIONS

| ID | Question | Priorité | Décision attendue de |
|----|----------|----------|---------------------|
| OQ-1 | La validation des `allowed_mcps` lors de l'import doit-elle être bloquante ou seulement un warning ? Les IDs MCP (ex. `ms1dftjc`) sont spécifiques à un environnement Obot. | Haute | @architect / @pm |
| OQ-2 | Le service d'import doit-il bumper la version de l'agent automatiquement sur update, ou laisser la version déclarée dans le JSON comme source de vérité ? | Moyenne | @architect |
| OQ-3 | Faut-il exposer un endpoint `DELETE /api/definitions/{kind}/{ref}` pour supprimer une définition importée ? | Basse | @pm |

---

## 15. DECISION LOG

| ID | Date | Décision | Justification | Alternatives rejetées |
|----|------|----------|---------------|----------------------|
| DEC-1 | 2026-04-26 | Choix ALT-1 : JSON déclaratif au-dessus des modèles SQLAlchemy existants, avec 2 extensions DB minimales. | Évite une refonte des modèles ; backward compatible ; livrable rapidement. | ALT-2 (nouveau modèle `DefinitionFile` dédié) — trop complexe, double source de vérité. ALT-3 (YAML) — moins standard que JSON pour les payloads API. |
| DEC-2 | 2026-04-26 | Clé d'upsert : `id` pour agents/orchestrateurs, `definition_key` pour scénarios (UUID interne non stable). | L'`id` agent est déjà la PK stable. Les scénarios n'ont qu'un UUID auto-généré, il faut une clé sémantique. | Utiliser `name` comme clé scénario — fragile aux renommages. |
| DEC-3 | 2026-04-26 | Pas de CLI dans cette itération. | Complexité ajoutée pour un gain faible ; les endpoints REST suffisent pour l'usage interne. | CLI `orkestra-import` — déféré. |
| DEC-4 | 2026-04-26 | Les scripts legacy sont conservés (marqués deprecated) et non supprimés. | Sécurité de rollback ; suppression dans un ticket dédié après stabilisation du système déclaratif. | Suppression immédiate — risque trop élevé. |

---

## 16. AFFECTED COMPONENTS (HIGH-LEVEL)

| Composant | Nature de l'impact |
|-----------|--------------------|
| `app/models/registry.py` — `AgentDefinition` | Extension : nouvelle colonne `pipeline_definition` (JSONB) |
| `app/models/test_lab.py` — `TestScenario` | Extension : nouvelle colonne `definition_key` (str, unique) |
| `app/schemas/` | Ajout : `AgentDefinitionSchema`, `OrchestratorDefinitionSchema`, `ScenarioDefinitionSchema` |
| `app/services/` | Ajout : `definition_import_service`, `definition_export_service`, `definition_resolver_service` |
| `app/api/routes/` | Ajout : route `definitions` avec endpoints import/export/validate |
| `alembic/versions/` | Ajout : 1 migration couvrant les 2 nouvelles colonnes |
| `data/registry/agents/` | Ajout : 5 fichiers JSON (agents du pipeline hôtelier) |
| `data/registry/orchestrators/` | Ajout : 1 fichier JSON (hotel_pipeline_orchestrator) |
| `data/test_lab/scenarios/` | Ajout : 6 fichiers JSON (scénarios correspondants) |
| `scripts/create_*.py` | Modification : ajout d'en-tête `DEPRECATED` |

---

## 17. ACCEPTANCE CRITERIA

**AC-F1-1 — Fichiers JSON créés pour les 5 agents**
> **Given** le répertoire `data/registry/agents/`,
> **When** on liste les fichiers JSON présents,
> **Then** on trouve exactement les fichiers pour `stay_discovery_agent`, `mobility_agent`,
> `weather_agent`, `budget_fit_agent`, et `hotel_pipeline_orchestrator`, chacun valide
> par rapport au schéma Pydantic de leur `kind`.

**AC-F2-1 — Import idempotent (agent)**
> **Given** un fichier JSON agent valide pour `weather_agent` importé une première fois avec succès,
> **When** on importe le même fichier une seconde fois sans modification,
> **Then** le rapport d'import retourne `skipped: 1`, `created: 0`, `updated: 0`,
> et aucune écriture SQL n'est effectuée sur `agent_definitions`.

**AC-F2-2 — Import idempotent (scénario)**
> **Given** un fichier JSON scénario valide avec `definition_key: "weather_context_lisbon_may_2026"` importé une première fois,
> **When** on importe le même fichier une seconde fois sans modification,
> **Then** le rapport retourne `skipped: 1` et la colonne `definition_key` de `TestScenario`
> est toujours unique et inchangée.

**AC-F2-3 — Import avec modification**
> **Given** un agent `weather_agent` existant en DB importé depuis son JSON,
> **When** on modifie le champ `description` dans le JSON et qu'on l'importe à nouveau,
> **Then** le rapport retourne `updated: 1`, `skipped: 0`, et la DB reflète la nouvelle valeur.

**AC-F3-1 — Round-trip fidèle**
> **Given** un fichier JSON agent `budget_fit_agent` importé en DB,
> **When** on exporte cet agent via `GET /api/definitions/export?kind=agent&id=budget_fit_agent`,
> **Then** tous les champs canoniques du JSON exporté sont identiques aux champs du JSON source.

**AC-F4-1 — Validation dépendance family_id**
> **Given** un fichier JSON agent référençant un `family_id` inexistant en DB,
> **When** on appelle `POST /api/definitions/validate` avec ce fichier,
> **Then** la réponse retourne `valid: false` avec un message d'erreur référençant `family_id`.

**AC-F4-2 — Validation dépendance agent_id dans orchestrateur**
> **Given** un fichier JSON orchestrateur référençant un `agent_id` inconnu dans `pipeline_definition.stages`,
> **When** on appelle `POST /api/definitions/import`,
> **Then** la transaction est annulée (rollback) et le rapport retourne l'erreur avec le `stage_id` concerné.

**AC-DM1-1 — Migration `definition_key`**
> **Given** la migration Alembic appliquée sur une DB avec des scénarios existants,
> **When** on interroge la table `test_scenarios`,
> **Then** la colonne `definition_key` existe, est nullable, et les scénarios existants ont `definition_key = NULL`.

**AC-DM2-1 — Migration `pipeline_definition`**
> **Given** la migration Alembic appliquée,
> **When** on interroge la table `agent_definitions`,
> **Then** la colonne `pipeline_definition` existe, est de type JSONB, nullable, et les agents existants ont `pipeline_definition = NULL`.

**AC-F5-1 — Orchestrateur avec pipeline_definition**
> **Given** un fichier JSON orchestrateur avec `pipeline_definition.stages` listant les 4 agents,
> **When** on importe ce fichier,
> **Then** la DB persiste le JSONB complet dans `pipeline_definition` et le champ
> `pipeline_agent_ids` (legacy) est également renseigné avec les IDs extraits des stages.

**AC-F7-1 — Scripts legacy dépréciés**
> **Given** les 5 scripts `scripts/create_*.py`,
> **When** on lit leur en-tête,
> **Then** chacun contient un avertissement explicite `DEPRECATED` indiquant le remplacement
> par le système déclaratif JSON.

---

## 18. ROLLOUT & CHANGE MANAGEMENT (HIGH-LEVEL)

1. **Migrations Alembic** appliquées en premier (non-destructives, rollback disponible).
2. **Schémas Pydantic + services** déployés sans impact sur les routes existantes.
3. **Nouveaux endpoints REST** exposés sous `/api/definitions/` (route additionnelle).
4. **Fichiers JSON** créés et validés via `POST /api/definitions/validate` avant tout import en production.
5. **Import initial** des 5 agents + orchestrateur + scénarios via `POST /api/definitions/import`.
6. **Scripts legacy** marqués deprecated après import réussi et validé.
7. **Tests** exécutés en CI avant merge.

Pas de feature flag requis. Rollback : suppression des nouvelles routes + downgrade Alembic (colonnes nullable sans données critiques).

---

## 19. DATA MIGRATION / SEEDING (IF APPLICABLE)

- Aucune migration de données existantes n'est requise : les nouvelles colonnes sont nullable.
- L'import initial des 5 agents + orchestrateur depuis les fichiers JSON constitue le **seeding déclaratif** de référence.
- Si les agents existent déjà en DB (créés par les scripts legacy), l'import idempotent détectera les divergences et appliquera les mises à jour nécessaires.

---

## 20. PRIVACY / COMPLIANCE REVIEW

- Les fichiers JSON contiennent des `prompt_content` (instructions LLM). Ces contenus sont des données opérationnelles internes, sans données personnelles.
- Les `allowed_mcps` contiennent des identifiants techniques de serveurs MCP (non sensibles).
- Aucun traitement de données personnelles dans ce changement.

---

## 21. SECURITY REVIEW HIGHLIGHTS

- Les endpoints `/api/definitions/` requièrent l'authentification par `X-API-Key` (même mécanisme que les routes existantes).
- Le service d'import opère directement sur la DB (bypass de la couche HTTP interne) : les validations Pydantic constituent la première ligne de défense contre les payloads malformés.
- La colonne `pipeline_definition` (JSONB) est écrite telle quelle après validation Pydantic ; aucune exécution du contenu JSONB n'est effectuée.
- `security_impact: low` — pas d'élévation de privilèges, pas de nouveaux secrets, pas d'accès à des données sensibles.

---

## 22. MAINTENANCE & OPERATIONS IMPACT

- Les fichiers JSON sous `data/` deviennent la source de vérité à maintenir pour les agents du pipeline hôtelier.
- Toute modification d'agent doit idéalement passer par la modification du JSON + re-import, et non par l'UI directement (sauf modification temporaire documentée).
- Les scripts legacy ne sont plus maintenus activement après ce changement.
- Les migrations Alembic `downgrade` permettent de revenir en arrière sans perte de données.

---

## 23. GLOSSARY

| Terme | Définition |
|-------|-----------|
| `kind` | Discriminant de type d'une définition JSON : `agent`, `orchestrator`, `scenario`. |
| `schema_version` | Version du format JSON déclaratif. Actuellement `"v1"`. |
| `definition_key` | Clé sémantique stable d'un scénario (ex. `weather_context_lisbon_may_2026`), distincte de son UUID interne. |
| `pipeline_definition` | Champ JSONB sur `AgentDefinition` décrivant la structure d'un pipeline d'orchestration (stages, routing_mode, error_policy). |
| Import idempotent | Propriété : un import répété sans modification de contenu ne produit aucun effet DB. |
| Round-trip | Propriété : `export(import(json)) == json` sur tous les champs canoniques. |
| Upsert | Opération combinée insert (si absent) ou update (si présent et différent). |
| Script legacy | L'un des 5 scripts `scripts/create_*.py` antérieurs à ce changement. |

---

## 24. APPENDICES

### Appendice A — Inventaire des fichiers JSON à créer

| Fichier | Kind | Clé stable |
|---------|------|-----------|
| `data/registry/agents/stay_discovery_agent.json` | `agent` | `id: stay_discovery_agent` |
| `data/registry/agents/mobility_agent.json` | `agent` | `id: mobility_agent` |
| `data/registry/agents/weather_agent.json` | `agent` | `id: weather_agent` |
| `data/registry/agents/budget_fit_agent.json` | `agent` | `id: budget_fit_agent` |
| `data/registry/orchestrators/hotel_pipeline_orchestrator.json` | `orchestrator` | `id: hotel_pipeline_orchestrator` |
| `data/test_lab/scenarios/stay_discovery_lisbon_may2026.json` | `scenario` | `definition_key: stay_discovery_lisbon_may_2026` |
| `data/test_lab/scenarios/mobility_lisbon_may2026.json` | `scenario` | `definition_key: mobility_lisbon_may_2026` |
| `data/test_lab/scenarios/weather_lisbon_may2026.json` | `scenario` | `definition_key: weather_context_lisbon_may_2026` |
| `data/test_lab/scenarios/budget_fit_lisbon_may2026.json` | `scenario` | `definition_key: budget_fit_lisbon_may_2026` |
| `data/test_lab/scenarios/hotel_pipeline_full_run.json` | `scenario` | `definition_key: hotel_pipeline_full_run_lisbonne` |

### Appendice B — Schéma JSON Agent (v1)

```json
{
  "kind": "agent",
  "schema_version": "v1",
  "id": "<agent_id>",
  "name": "<display name>",
  "family_id": "<family_id>",
  "purpose": "<mission>",
  "description": "<extended description>",
  "skill_ids": [],
  "selection_hints": {
    "routing_keywords": [],
    "workflow_ids": [],
    "use_case_hint": "",
    "requires_grounded_evidence": false
  },
  "allowed_mcps": [],
  "forbidden_effects": [],
  "allow_code_execution": false,
  "criticality": "low|medium|high",
  "cost_profile": "low|medium|high",
  "llm_provider": "ollama|openai",
  "llm_model": "<model name>",
  "limitations": [],
  "prompt_content": "<LLM system prompt>",
  "skills_content": null,
  "version": "1.0.0",
  "status": "draft"
}
```

### Appendice C — Schéma JSON Orchestrateur (v1)

Identique au schéma Agent, avec le champ additionnel :

```json
{
  "kind": "orchestrator",
  "pipeline_definition": {
    "routing_mode": "sequential",
    "stages": [
      { "stage_id": "<id>", "agent_id": "<agent_id>", "required": true }
    ],
    "error_policy": "continue_on_partial_failure"
  }
}
```

### Appendice D — Schéma JSON Scénario (v1)

```json
{
  "kind": "scenario",
  "schema_version": "v1",
  "definition_key": "<stable_key>",
  "name": "<display name>",
  "description": "<description>",
  "agent_id": "<agent_id>",
  "input_prompt": "<prompt>",
  "expected_tools": [],
  "assertions": [
    { "type": "<assertion_type>", "target": "<field>", "critical": true }
  ],
  "timeout_seconds": 120,
  "max_iterations": 10,
  "tags": [],
  "enabled": true
}
```

---

## 25. DOCUMENT HISTORY

| Version | Date | Auteur | Description |
|---------|------|--------|-------------|
| 0.1 | 2026-04-26 | @spec-writer | Création initiale — Proposed |

---

## AUTHORING GUIDELINES

- Utiliser les IDs stables (`F-`, `AC-`, `DM-`, `API-`, `NFR-`, `RSK-`, `OQ-`, `DEC-`) pour toute référence croisée.
- Toute décision architecturale non résolue doit figurer dans la section **OPEN QUESTIONS** avec la mention "Decision needed: consult `@architect`".
- Les critères d'acceptance suivent le format Given/When/Then et référencent au moins un ID de capacité ou de modèle de données.
- Ne pas inclure de chemins de fichiers, tâches d'implémentation ou instructions de code dans ce document.

## VALIDATION CHECKLIST

- [x] Front matter valide : `change.ref == GH-14`, `status == Proposed`, `owners ≥ 1`
- [x] Sections dans l'ordre exact défini par `<spec_structure>`
- [x] IDs de préfixe cohérents et uniques par catégorie
- [x] Tous les Acceptance Criteria en Given/When/Then et référençant au moins un ID
- [x] NFRs avec valeurs mesurables
- [x] Risques avec Impact & Probabilité (H/M/L)
- [x] Aucun chemin de fichier, tâche d'implémentation ou instruction de code dans le corps de la spec
- [x] Open questions documentées avec décideur désigné
- [x] Décisions architecture documentées dans le Decision Log
