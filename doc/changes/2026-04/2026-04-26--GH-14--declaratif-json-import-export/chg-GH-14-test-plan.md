---
id: chg-GH-14-test-plan
status: Proposed
created: 2026-04-26T00:00:00Z
last_updated: 2026-04-26T00:00:00Z
owners:
  - orkestra-team
service: agent-registry / test-lab
labels:
  - registry
  - test-lab
  - declarative
  - idempotence
  - devx
links:
  change_spec: doc/changes/2026-04/2026-04-26--GH-14--declaratif-json-import-export/chg-GH-14-spec.md
  implementation_plan: null
  testing_strategy: .ai/rules/testing-strategy.md
version_impact: minor
summary: >-
  Plan de test pour GH-14 : import/export JSON déclaratif (agents, orchestrateurs, scénarios),
  validation des dépendances, endpoints REST et migrations DB associées, avec focus sur idempotence,
  round-trip et atomicité.
---

# Test Plan - Système déclaratif JSON import/export pour agents, scénarios et orchestrateurs

## 1. Scope and Objectives

**Objectifs** (réf. spec GH-14) :

- Vérifier la conformité des schémas Pydantic pour `kind: agent|orchestrator|scenario` (F-1, NFR-5).
- Garantir l’**import idempotent** (no-op si contenu identique) et l’**upsert** robuste (F-2, NFR-1).
- Garantir le **round-trip** fidèle DB → JSON → DB (F-3, NFR-3).
- Valider les dépendances avant écriture (family_id, agent_id en scénario, agent_id en pipeline stages) (F-4).
- Valider les endpoints REST import/export/validate et leurs codes d’erreur (API-1..3).
- Vérifier l’impact modèle de données et migrations (`definition_key`, `pipeline_definition`) (DM-1, DM-2, NFR-6).
- Confirmer l’atomicité transactionnelle à l’import (NFR-4).

**Hors scope** : CLI dédiée, UI, import bulk d’un répertoire, validation sémantique des prompts (cf. spec section Out of Scope).

## 2. References

- Change spec : `doc/changes/2026-04/2026-04-26--GH-14--declaratif-json-import-export/chg-GH-14-spec.md`
- Implementation plan : non fourni (lien `null`)
- Testing strategy : `.ai/rules/testing-strategy.md`

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| ID | Sujet | Couverture | TC(s) |
|---|---|---|---|
| F-1 | Schémas JSON déclaratifs (`kind`, `schema_version`) | Covered | TC-DEFS-001, TC-DEFS-002 |
| F-2 | Import idempotent / upsert | Covered | TC-DEFS-003, TC-DEFS-004, TC-DEFS-005, TC-DEFS-006 |
| F-3 | Export DB → JSON canonique + round-trip | Covered | TC-DEFS-007, TC-DEFS-008 |
| F-4 | Validation des dépendances avant écriture | Covered | TC-DEFS-009, TC-DEFS-010, TC-DEFS-011 |
| F-5 | Persist `pipeline_definition` orchestrateur + legacy `pipeline_agent_ids` | Covered | TC-DEFS-012 |
| F-6 | Scénarios identifiés par `definition_key` (upsert stable) | Covered | TC-DEFS-004, TC-DEFS-006 |
| F-7 | Scripts legacy marqués `DEPRECATED` | Covered | TC-DEFS-016 |

| AC ID | Critère | Couverture | TC(s) |
|---|---|---|---|
| AC-F1-1 | Fichiers JSON agents présents et valides | Covered | TC-DEFS-001 |
| AC-F2-1 | Import idempotent (agent) + 0 write DB | Covered | TC-DEFS-003 |
| AC-F2-2 | Import idempotent (scénario) + `definition_key` stable | Covered | TC-DEFS-004 |
| AC-F2-3 | Import avec modification (update) | Covered | TC-DEFS-005 |
| AC-F3-1 | Round-trip fidèle (agent) via export endpoint | Covered | TC-DEFS-008 |
| AC-F4-1 | `family_id` invalide → validation bloquante | Covered | TC-DEFS-009 |
| AC-F4-2 | Orchestrateur: `agent_id` inconnu dans stages → rollback + erreur contextualisée | Covered | TC-DEFS-011 |
| AC-DM1-1 | Migration `definition_key` (nullable, existants à NULL) | Covered | TC-DEFS-014 |
| AC-DM2-1 | Migration `pipeline_definition` (JSONB nullable) | Covered | TC-DEFS-015 |
| AC-F5-1 | Import orchestrateur persiste JSONB + renseigne `pipeline_agent_ids` | Covered | TC-DEFS-012 |
| AC-F7-1 | Scripts legacy contiennent avertissement `DEPRECATED` | Covered | TC-DEFS-016 |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| ID | Interface | Couverture | TC(s) |
|---|---|---|---|
| API-1 | `POST /api/definitions/import` | Covered | TC-DEFS-003, TC-DEFS-004, TC-DEFS-005, TC-DEFS-011, TC-DEFS-013 |
| API-2 | `GET /api/definitions/export` | Covered | TC-DEFS-008, TC-DEFS-013 |
| API-3 | `POST /api/definitions/validate` (dry-run) | Covered | TC-DEFS-009, TC-DEFS-010, TC-DEFS-013 |
| EVT-1 | `definition.imported` | Covered (vérif. émission) | TC-DEFS-013 |
| EVT-2 | `definition.import_skipped` | Covered (vérif. émission) | TC-DEFS-013 |
| EVT-3 | `definition.export_requested` | Covered (vérif. émission) | TC-DEFS-013 |
| DM-1 | `TestScenario.definition_key` | Covered | TC-DEFS-006, TC-DEFS-014 |
| DM-2 | `AgentDefinition.pipeline_definition` | Covered | TC-DEFS-012, TC-DEFS-015 |

### 3.3 Non-Functional Coverage (NFR-#)

| ID | Exigence | Couverture | TC(s) |
|---|---|---|---|
| NFR-1 | Idempotence (0 write SQL si identique) | Covered | TC-DEFS-003, TC-DEFS-004 |
| NFR-2 | Latence import (≤10 defs, p95 < 500ms) | TODO (mesure perf à stabiliser en CI) | TC-DEFS-017 |
| NFR-3 | Fidélité round-trip champs canoniques | Covered | TC-DEFS-008 |
| NFR-4 | Atomicité transactionnelle (tout ou rien) | Covered | TC-DEFS-011 |
| NFR-5 | Rejet schéma non conforme avant écriture | Covered | TC-DEFS-002, TC-DEFS-013 |
| NFR-6 | Migrations non destructives + downgrade | Covered (smoke) | TC-DEFS-014, TC-DEFS-015 |

## 4. Test Types and Layers

Conformément à `.ai/rules/testing-strategy.md` :

- **Unit** (`tests/unit/`) : schémas Pydantic, transformations JSON canonique (sans I/O).
- **Integration** (`tests/integration/` et/ou `tests/services/`) : DB réelle (SQLite in-memory ou fixture PostgreSQL), services import/export/résolution, endpoints FastAPI via `httpx.TestClient`.
- **Performance / manuel** : mesure simple de latence import (NFR-2) hors CI si nécessaire.

## 5. Test Scenarios

### 5.1 Scenario Index

| TC-ID | Titre | Types | Priorité | Composant(s) principal(aux) | Related IDs |
|---|---|---|---|---|---|
| TC-DEFS-001 | Validation des JSON déclaratifs attendus (inventaire minimal) | Unit | High | `app/schemas/definitions.py` | F-1, AC-F1-1 |
| TC-DEFS-002 | Rejet schéma JSON invalide (422) avant toute écriture | Integration | High | `app/api/routes/definitions.py` | NFR-5, API-1 |
| TC-DEFS-003 | Import idempotent agent = no-op (0 write DB) | Integration | High | `definition_import_service` | F-2, AC-F2-1, NFR-1 |
| TC-DEFS-004 | Import idempotent scénario via `definition_key` | Integration | High | `definition_import_service` | F-2, AC-F2-2, DM-1, NFR-1 |
| TC-DEFS-005 | Import update : 1 update, pas de bump inutile | Integration | High | `definition_import_service` | AC-F2-3, F-2 |
| TC-DEFS-006 | `definition_key` dupliqué → upsert correct (pas d’erreur) | Integration | High | `definition_import_service` | DM-1, F-2 |
| TC-DEFS-007 | Export JSON canonique (agent) | Integration | Medium | `definition_export_service` | F-3 |
| TC-DEFS-008 | Round-trip agent : export → réimport → identique | Integration | High | import+export services + route export | F-3, AC-F3-1, NFR-3 |
| TC-DEFS-009 | `family_id` invalide → validation bloque l’import | Integration | High | `definition_resolver_service` | F-4, AC-F4-1 |
| TC-DEFS-010 | Scénario référence agent_id inexistant → erreur claire | Integration | High | `definition_resolver_service` | F-4 |
| TC-DEFS-011 | Orchestrateur stage avec agent_id manquant → rollback + erreur contextualisée | Integration | High | resolver+import service | AC-F4-2, NFR-4 |
| TC-DEFS-012 | Orchestrateur : `pipeline_definition` valide persisté + legacy list dérivée | Integration | High | import service + DB model | F-5, AC-F5-1, DM-2 |
| TC-DEFS-013 | Endpoints REST : import/export/validate + événements | Integration | Medium | `app/api/routes/definitions.py` | API-1..3, EVT-1..3 |
| TC-DEFS-014 | Migration DM-1 : `definition_key` existe, nullable, unique, downgrade ok | Manual | Medium | Alembic | AC-DM1-1, NFR-6 |
| TC-DEFS-015 | Migration DM-2 : `pipeline_definition` JSONB nullable, downgrade ok | Manual | Medium | Alembic | AC-DM2-1, NFR-6 |
| TC-DEFS-016 | Scripts legacy : présence de l’avertissement `DEPRECATED` | Manual | Low | `scripts/create_*.py` | AC-F7-1 |
| TC-DEFS-017 | NFR-2 : latence import (10 defs) p95 < 500 ms | Performance | Low | endpoints import | NFR-2 |

### 5.2 Scenario Details

#### TC-DEFS-001 - Validation des JSON déclaratifs attendus (inventaire minimal)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-1, AC-F1-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/test_definitions_schemas_validation.py`
**Tags**: @backend

**Preconditions**:

- Disponibilité des exemples JSON déclaratifs (au minimum 1 agent, 1 orchestrateur, 1 scénario) conformes au format v1 décrit en spec.

**Steps**:

1. Charger un JSON `kind: agent` valide et le valider via les schémas Pydantic.
2. Charger un JSON `kind: orchestrator` valide incluant `pipeline_definition` et le valider.
3. Charger un JSON `kind: scenario` valide incluant `definition_key` et le valider.

**Expected Outcome**:

- Les 3 objets passent la validation Pydantic.
- Les champs discriminants (`kind`, `schema_version`) sont requis et correctement interprétés.

**Notes / Clarifications**:

- Cette vérification couvre la partie « chacun valide par rapport au schéma Pydantic » de AC-F1-1.

#### TC-DEFS-002 - Rejet schéma JSON invalide (422) avant toute écriture

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: API-1, NFR-5
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_definitions_api_schema_validation.py`
**Tags**: @api, @backend

**Preconditions**:

- API FastAPI disponible via `TestClient`.
- DB de test isolée (fixture).

**Steps**:

1. Appeler `POST /api/definitions/import` avec un payload contenant une définition invalide (ex. `kind` manquant ou `schema_version` invalide).
2. Vérifier le statut HTTP.
3. Vérifier qu’aucune entité correspondante n’a été créée/modifiée en DB.

**Expected Outcome**:

- HTTP 422 avec un message d’erreur lisible.
- Aucune écriture DB liée à l’import.

#### TC-DEFS-003 - Import idempotent agent = no-op (0 write DB)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, AC-F2-1, NFR-1, API-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_import_service_idempotent_agent.py`
**Tags**: @backend

**Preconditions**:

- Un JSON agent valide (ex. `id: weather_agent`).

**Steps**:

1. Importer le JSON agent (service ou endpoint).
2. Ré-importer exactement le même JSON.
3. Examiner le rapport d’import.
4. Vérifier l’absence de modifications DB lors du second import (no-op), conformément aux mécanismes de test/fixtures du projet.

**Expected Outcome**:

- Second import : `skipped = 1`, `created = 0`, `updated = 0`.
- Aucun write SQL sur `agent_definitions` pendant le second import.

#### TC-DEFS-004 - Import idempotent scénario via `definition_key`

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, AC-F2-2, DM-1, NFR-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_import_service_idempotent_scenario.py`
**Tags**: @backend

**Preconditions**:

- Un agent référencé existant (ou inclus dans le même batch import si supporté).
- Un JSON scénario valide avec `definition_key` stable.

**Steps**:

1. Importer le scénario.
2. Ré-importer exactement le même scénario.
3. Vérifier que l’unicité et la valeur de `definition_key` restent inchangées.

**Expected Outcome**:

- Second import : `skipped = 1`.
- `definition_key` reste unique et identique.

#### TC-DEFS-005 - Import update : 1 update, pas de bump inutile

**Scenario Type**: Edge Case
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, AC-F2-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_import_service_update_agent.py`
**Tags**: @backend

**Preconditions**:

- Un agent importé une première fois depuis un JSON.

**Steps**:

1. Modifier un champ modifiable et comparable (ex. `description`) dans le JSON agent.
2. Importer à nouveau.
3. Examiner le rapport d’import.
4. Vérifier la valeur en DB.
5. Vérifier qu’aucun « bump de version » n’a été appliqué de manière non nécessaire (la version reste contrôlée par la source déclarative / non modifiée dans ce test).

**Expected Outcome**:

- Rapport : `updated = 1`, `skipped = 0`.
- La DB reflète la nouvelle valeur du champ modifié.
- Pas de changement de version si le champ `version` n’a pas été modifié dans le JSON.

#### TC-DEFS-006 - `definition_key` dupliqué → upsert correct (pas d’erreur)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-2, DM-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_import_service_upsert_definition_key.py`
**Tags**: @backend

**Preconditions**:

- Un scénario déjà présent en DB avec un `definition_key` donné.

**Steps**:

1. Importer un JSON scénario avec le même `definition_key` mais un champ modifié (ex. `description`).
2. Vérifier que l’opération se traduit par un update (et non une création dupliquée, et sans erreur de contrainte).

**Expected Outcome**:

- Le scénario existant est mis à jour.
- Aucune erreur liée au caractère unique de `definition_key`.

#### TC-DEFS-007 - Export JSON canonique (agent)

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-3, API-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_export_service_agent.py`
**Tags**: @backend

**Preconditions**:

- Un agent présent en DB (créé via import ou fixture).

**Steps**:

1. Exporter l’agent via le service d’export (ou endpoint).
2. Vérifier que le JSON exporté respecte le schéma v1 et inclut les champs canoniques attendus.

**Expected Outcome**:

- JSON exporté conforme au schéma déclaratif (agent).
- Les champs canoniques reflètent l’état DB.

#### TC-DEFS-008 - Round-trip agent : export → réimport → identique

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F3-1, NFR-3, API-2, API-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_definitions_round_trip_agent.py`
**Tags**: @api, @backend

**Preconditions**:

- Un JSON agent source stable (ex. `budget_fit_agent`) prêt à être importé.

**Steps**:

1. Importer l’agent source.
2. Exporter cet agent via `GET /api/definitions/export?kind=agent&id=<id>`.
3. Réimporter le JSON exporté.
4. Réexporter l’agent.
5. Comparer les champs canoniques entre le JSON source et le JSON exporté (et/ou exporté après réimport).

**Expected Outcome**:

- Les champs canoniques du JSON exporté sont identiques au JSON source (à champs canoniques près conformément à la spec).
- Le réimport du JSON exporté est idempotent (skipped / pas d’effet).

#### TC-DEFS-009 - `family_id` invalide → validation bloque l’import

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, AC-F4-1, API-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_resolver_service_family_id.py`
**Tags**: @backend

**Preconditions**:

- DB ne contient pas la famille cible (ou la famille est marquée inactive) pour le test.

**Steps**:

1. Soumettre une définition agent avec un `family_id` inexistant à `POST /api/definitions/validate`.
2. Soumettre la même définition à `POST /api/definitions/import`.

**Expected Outcome**:

- Validation : `valid = false` avec un message référençant explicitement `family_id`.
- Import : rejet (erreur) et aucune écriture DB.

#### TC-DEFS-010 - Scénario référence agent_id inexistant → erreur claire

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, API-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_resolver_service_scenario_agent_ref.py`
**Tags**: @backend

**Preconditions**:

- Aucun agent avec `id = <agent_id_inexistant>` en DB.

**Steps**:

1. Appeler `POST /api/definitions/validate` avec un JSON scénario référant `agent_id` inexistant.

**Expected Outcome**:

- `valid = false`.
- Message d’erreur clair indiquant la référence `agent_id` manquante (et idéalement la clé du scénario concerné).

#### TC-DEFS-011 - Orchestrateur stage avec agent_id manquant → rollback + erreur contextualisée

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, AC-F4-2, NFR-4, API-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_definition_import_atomicity_orchestrator_missing_agent.py`
**Tags**: @backend, @api

**Preconditions**:

- DB contient au moins une définition valide importable dans le même batch (pour prouver l’absence d’effet partiel).
- Un JSON orchestrateur dont `pipeline_definition.stages` contient au moins un stage avec `agent_id` inexistant.

**Steps**:

1. Appeler `POST /api/definitions/import` avec un batch incluant (a) une définition valide et (b) l’orchestrateur invalide.
2. Vérifier la réponse d’erreur.
3. Vérifier en DB qu’aucune des définitions du batch n’a été persistée (rollback complet).

**Expected Outcome**:

- Import échoue avec une erreur contenant le `stage_id` concerné.
- Aucun effet partiel en DB (atomicité).

#### TC-DEFS-012 - Orchestrateur : `pipeline_definition` valide persisté + legacy list dérivée

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-1, DM-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_definition_import_service_orchestrator_pipeline_definition.py`
**Tags**: @backend

**Preconditions**:

- Les agents référencés par les stages existent en DB.
- Un JSON orchestrateur valide avec `pipeline_definition` (routing_mode, stages, error_policy).

**Steps**:

1. Importer l’orchestrateur.
2. Relire l’entité en DB.

**Expected Outcome**:

- `pipeline_definition` est persisté tel que déclaré (structure et valeurs).
- `pipeline_agent_ids` (legacy) est renseigné avec les IDs extraits des stages, dans l’ordre attendu.

#### TC-DEFS-013 - Endpoints REST : import/export/validate + événements

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: API-1, API-2, API-3, EVT-1, EVT-2, EVT-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_definitions_api_endpoints_and_events.py`
**Tags**: @api, @backend

**Preconditions**:

- Client API configuré avec `X-API-Key` valide.
- Mécanisme `emit_event` observable (via spy/mock ou capture d’appel selon conventions du repo).

**Steps**:

1. Appeler `POST /api/definitions/validate` avec une définition valide et vérifier `valid = true`.
2. Appeler `POST /api/definitions/import` avec la même définition et vérifier `created`/`updated`.
3. Réappeler `POST /api/definitions/import` avec le même payload et vérifier `skipped`.
4. Appeler `GET /api/definitions/export` pour la ressource importée.
5. Vérifier que les événements attendus ont été émis :
   - création/mise à jour → `definition.imported` (EVT-1)
   - no-op → `definition.import_skipped` (EVT-2)
   - export → `definition.export_requested` (EVT-3)

**Expected Outcome**:

- Codes HTTP et payloads conformes aux contrats API (200/404/422 selon cas).
- Événements `definition.*` émis conformément à la spec.

#### TC-DEFS-014 - Migration DM-1 : `definition_key` existe, nullable, unique, downgrade ok

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: DM-1, AC-DM1-1, NFR-6
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Procédure opérée localement/CI (Alembic)
**Tags**: @backend

**Preconditions**:

- Base de données de test (idéalement PostgreSQL pour refléter la prod).

**Steps**:

1. Appliquer la migration Alembic (`upgrade`).
2. Vérifier que la colonne `test_scenarios.definition_key` existe et est nullable.
3. Vérifier qu’un scénario existant (pré-migration) a `definition_key = NULL`.
4. Vérifier l’unicité lorsque `definition_key` est renseigné (pas de doublon possible).
5. Exécuter `downgrade` et vérifier l’absence d’erreurs.

**Expected Outcome**:

- Colonne présente, nullable, et contrainte unique conforme.
- `downgrade` fonctionne (réversibilité).

#### TC-DEFS-015 - Migration DM-2 : `pipeline_definition` JSONB nullable, downgrade ok

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: DM-2, AC-DM2-1, NFR-6
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Procédure opérée localement/CI (Alembic)
**Tags**: @backend

**Preconditions**:

- Base de données de test PostgreSQL (JSONB).

**Steps**:

1. Appliquer la migration Alembic (`upgrade`).
2. Vérifier que `agent_definitions.pipeline_definition` existe, est nullable, et stockable.
3. Vérifier qu’un agent existant (pré-migration) a `pipeline_definition = NULL`.
4. Exécuter `downgrade` et vérifier l’absence d’erreurs.

**Expected Outcome**:

- Colonne présente et compatible JSONB.
- `downgrade` fonctionne.

#### TC-DEFS-016 - Scripts legacy : présence de l’avertissement `DEPRECATED`

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: F-7, AC-F7-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Revue de fichiers `scripts/create_*.py`
**Tags**: @backend

**Preconditions**:

- Les 5 scripts legacy existent dans le repo.

**Steps**:

1. Ouvrir chacun des 5 scripts `scripts/create_*.py` concernés.
2. Vérifier la présence d’un en-tête explicite contenant `DEPRECATED` et indiquant le remplacement par le système déclaratif JSON.

**Expected Outcome**:

- Les 5 scripts contiennent l’avertissement attendu.

#### TC-DEFS-017 - NFR-2 : latence import (10 defs) p95 < 500 ms

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-2
**Test Type(s)**: Performance
**Automation Level**: Semi-automated
**Target Layer / Location**: `tests/e2e/` ou script de bench interne (à décider)
**Tags**: @perf, @api

**Preconditions**:

- Environnement de test stable (non partagé) et DB comparable à l’intégration.
- Payload contenant ~10 définitions (agents/orchestrateur/scénarios) valides.

**Steps**:

1. Exécuter une série d’appels `POST /api/definitions/import` avec le payload (en purgeant l’état DB entre runs si nécessaire).
2. Mesurer la latence p95 côté serveur (ou côté test si instrumentation limitée).

**Expected Outcome**:

- p95 < 500 ms (hors latence réseau client), selon la définition de mesure retenue.

**Notes / Clarifications**:

- TODO: confirmer la méthode de mesure/outil acceptable en CI (voir section 8).

## 6. Environments and Test Data

**Environnements** :

- Unit : sans DB.
- Intégration services/endpoints : DB isolée par test (SQLite in-memory selon stratégie) ; utiliser une fixture PostgreSQL si nécessaire pour valider les aspects JSONB / contraintes DB au plus proche (DM-2).

**Données de test minimales** :

- 1 agent valide (ex. `weather_agent`).
- 1 scénario valide référant un agent existant avec `definition_key`.
- 1 orchestrateur valide avec `pipeline_definition` référant des agents existants.
- Variantes invalides : `family_id` inconnu, `agent_id` inconnu (scenario), stage avec `agent_id` inconnu (orchestrator).

## 7. Automation Plan and Implementation Mapping

Conventions (stratégie de test) : `pytest` (+ `pytest-asyncio` si nécessaire), endpoints via `httpx.TestClient`, DB via fixtures.

| TC-ID | Automatisation | Type | Emplacement cible (suggestion) |
|---|---|---|---|
| TC-DEFS-001 | Automated | Unit | `tests/unit/test_definitions_schemas_validation.py` |
| TC-DEFS-002 | Automated | Integration | `tests/integration/test_definitions_api_schema_validation.py` |
| TC-DEFS-003 | Automated | Integration | `tests/services/test_definition_import_service_idempotent_agent.py` |
| TC-DEFS-004 | Automated | Integration | `tests/services/test_definition_import_service_idempotent_scenario.py` |
| TC-DEFS-005 | Automated | Integration | `tests/services/test_definition_import_service_update_agent.py` |
| TC-DEFS-006 | Automated | Integration | `tests/services/test_definition_import_service_upsert_definition_key.py` |
| TC-DEFS-007 | Automated | Integration | `tests/services/test_definition_export_service_agent.py` |
| TC-DEFS-008 | Automated | Integration | `tests/integration/test_definitions_round_trip_agent.py` |
| TC-DEFS-009 | Automated | Integration | `tests/services/test_definition_resolver_service_family_id.py` |
| TC-DEFS-010 | Automated | Integration | `tests/services/test_definition_resolver_service_scenario_agent_ref.py` |
| TC-DEFS-011 | Automated | Integration | `tests/integration/test_definition_import_atomicity_orchestrator_missing_agent.py` |
| TC-DEFS-012 | Automated | Integration | `tests/services/test_definition_import_service_orchestrator_pipeline_definition.py` |
| TC-DEFS-013 | Automated | Integration | `tests/integration/test_definitions_api_endpoints_and_events.py` |
| TC-DEFS-014 | Manual | Manual | Checklist Alembic (upgrade/downgrade) |
| TC-DEFS-015 | Manual | Manual | Checklist Alembic (upgrade/downgrade) |
| TC-DEFS-016 | Manual | Manual | Checklist revue scripts legacy |
| TC-DEFS-017 | Semi-automated | Performance | À décider (bench hors CI ou job dédié) |

## 8. Risks, Assumptions, and Open Questions

**Risques (extraits spec)** :

- RSK-3 / OQ-1 : validation `allowed_mcps` potentiellement non portable selon environnements → clarifier bloquant vs warning.
- RSK-4 : ordre d’import (agents avant orchestrateur) → tests doivent couvrir un import orchestrateur lorsque agents absents (TC-DEFS-011) et lorsque présents (TC-DEFS-012).

**Hypothèses** :

- Les familles (`family_id`) et les agents référencés peuvent être créés via fixtures/imports dans l’environnement de test.
- La capture des événements `definition.*` est possible dans les tests d’intégration (mock/spy).

**Open questions (à tracer)** :

1. (OQ-1) La validation `allowed_mcps` est-elle bloquante ? Impact sur TC-DEFS-009/010/011 si des MCPs sont inclus dans les JSON de référence.
2. (OQ-2) La politique de version sur update : ce plan teste l’absence de bump automatique si `version` non modifiée ; confirmer le comportement attendu global.
3. (NFR-2) Où et comment mesurer la latence import (CI vs manuel) ? Décider si TC-DEFS-017 doit être un gate CI.

## 9. Plan Revision Log

| Date (UTC) | Auteur | Changement |
|---|---|---|
| 2026-04-26 | @test-plan-writer | Création initiale du plan de test (Proposed). |

## 10. Test Execution Log

| Date (UTC) | Environnement | Version / Commit | TC exécutés | Résultat | Notes |
|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD |
