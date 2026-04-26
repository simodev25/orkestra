---
id: chg-GH-14-declaratif-json-import-export
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
summary: >-
  Introduire un système déclaratif fichier-first basé sur des définitions JSON versionnées sous
  data/registry/ et data/test_lab/, avec services Python d’import/export idempotents (upsert) opérant
  directement sur les modèles SQLAlchemy, validation de dépendances, round-trip DB↔JSON et endpoints
  REST dédiés. Inclut deux extensions DB minimales (TestScenario.definition_key, AgentDefinition.pipeline_definition)
  et la dépréciation des scripts legacy.
version_impact: minor
---

## Context and Goals

Ce plan d’implémentation couvre le changement **GH-14** (cf. spec) : définitions JSON déclaratives pour agents/orchestrateurs/scénarios, import/export idempotents, validation des dépendances et endpoints REST.

**Objectifs (réf. spec)** : G-1..G-6, avec focus sur **idempotence** (NFR-1), **round-trip** (NFR-3), **validation avant écriture** (NFR-5) et **atomicité transactionnelle** (NFR-4).

**Contraintes projet intégrées au plan** :

- Tâches ≤ 2h chacune.
- **TDD obligatoire** : tests écrits avant l’implémentation associée.
- **Zones High Complexity** (à signaler explicitement) : `app/models/`, `app/services/`, `app/api/routes/`.
- **Pas de CLI** : uniquement services Python + endpoints REST.
- Règle “solo projet” : chaque commit ne touche pas plus de **3 fichiers** (le plan propose des découpages de commits compatibles).

**Open questions à résoudre avant verrouillage final** (réf. spec) :

- OQ-1 : validation `allowed_mcps` bloquante vs warning — *Decision needed: consult `@architect`*.
- OQ-2 : politique de version sur update à l’import (ne pas auto-bump vs conserver version déclarée) — *Decision needed: consult `@architect`*.
- (Optionnel) Méthode de mesure NFR-2 en CI vs manuel (TC-DEFS-017) — alignement avec @pm/@runner.

## Scope

### In Scope

- Migrations Alembic : ajout `TestScenario.definition_key` (unique, nullable) et `AgentDefinition.pipeline_definition` (JSONB, nullable) (DM-1, DM-2).
- Schémas Pydantic v1 : `kind=agent|orchestrator|scenario` (F-1).
- Services :
  - Resolver / validation dépendances (F-4)
  - Import idempotent (upsert) + atomicité (F-2, NFR-1, NFR-4)
  - Export canonique + round-trip (F-3, NFR-3)
- Endpoints REST : `POST /api/definitions/import`, `GET /api/definitions/export`, `POST /api/definitions/validate` (API-1..3).
- Fichiers JSON de référence sous `data/` pour le pipeline hôtelier (Appendice A de la spec) + scénarios correspondants.
- Marquage `DEPRECATED` des scripts legacy (F-7).

### Out of Scope

- CLI dédiée.
- Import “bulk depuis répertoire” via API.
- Validation sémantique des prompts.
- UI d’édition.

### Constraints

- TDD : tests en premier (unit/integration selon le composant).
- Chaque tâche listée ci-dessous est calibrée pour rester ≤ 2h.
- Découpage recommandé en commits ≤ 3 fichiers.

### Risks

- RSK-3 / OQ-1 : non-portabilité des `allowed_mcps` selon environnement.
- RSK-4 : ordre d’import agents → orchestrateur ; besoin de tri par dépendances.
- Risque “version bump” : les chemins existants d’update agent bumpent automatiquement (voir `agent_registry_service.update_agent`) — l’import devra éviter cet effet si non souhaité (OQ-2).

### Success Metrics

- Import idempotent : second import identique ⇒ **0 write DB** (NFR-1 ; AC-F2-1/2).
- Round-trip : export(import(json)) stable sur champs canoniques (NFR-3 ; AC-F3-1).
- Atomicité : erreur de dépendance ⇒ rollback total (NFR-4 ; AC-F4-2).

## Phases

### Phase 1: Alignement & cadrage technique (pré-implémentation)

**Goal**: Verrouiller les décisions qui conditionnent les tests et le comportement runtime (OQ-1/OQ-2) et cadrer les invariants “canonique” pour le round-trip.

**Tasks**:

- [x] **(≤1h)** Confirmer avec `@architect` la politique de validation `allowed_mcps` (bloquant vs warning vs mode “relaxed”) (OQ-1).  (Décision: warning non bloquant sans mode additionnel, evidence task_id `ses_235c65d72ffer0zXcn1Ecv2om5`)
  **Fichiers/modules**: (documenter dans code plus tard) `app/services/definition_resolver_service.py` (à créer).  
  **Dépendances**: aucune.
- [x] **(≤1h)** Confirmer la politique de version à l’import (source de vérité JSON vs auto-bump) et l’impact sur `AgentDefinition.version` (OQ-2).  (Décision: version déclarée JSON, aucun auto-bump à l’import, evidence task_id `ses_235c65d72ffer0zXcn1Ecv2om5`)
  **Fichiers/modules**: `app/services/definition_import_service.py` (à créer).  
  **Dépendances**: aucune.
- [x] **(≤2h)** Définir les **champs canoniques** pour la comparaison idempotente et round-trip (exclusions explicites : `usage_count`, `last_test_status`, `last_validated_at`, timestamps, etc. — cf. RSK-1).  (Implémenté dans `app/services/definition_canonicalization.py`, tests `tests/unit/test_definition_canonicalization.py`, pytest PASS)
  **Fichiers/modules**: `app/services/definition_canonicalization.py` (à créer) + tests unit associés.  
  **Dépendances**: OQ-2.

**Acceptance Criteria**:

- Must: OQ-1 et OQ-2 ont une décision documentée et traduisible en tests.
- Must: la liste “canonique” est explicitée et testable (support de NFR-1/NFR-3).

Criterion: OQ-1 et OQ-2 ont une décision documentée et traduisible en tests. — PASSED (consultation @architect task_id `ses_235c65d72ffer0zXcn1Ecv2om5`)
Criterion: la liste “canonique” est explicitée et testable (support de NFR-1/NFR-3). — PASSED (`python3 -m pytest tests/unit/test_definition_canonicalization.py`)

**Files and modules**:

- (Nouveaux) `app/services/definition_canonicalization.py`

**Tests**:

- Unit: tests de canonicalisation (diff stable) — prépare TC-DEFS-003/008.

**Completion signal**: décisions actées + tests unit de canonicalisation en rouge (avant implémentation).

---

### Phase 2: Migrations Alembic + extensions modèles (High Complexity: `app/models/`)

**Goal**: Introduire les 2 extensions DB non-destructives et réversibles (DM-1, DM-2 ; NFR-6).

**Tasks**:

- [ ] **(≤2h)** Écrire la migration Alembic ajoutant `test_scenarios.definition_key` (nullable + unique index) (DM-1).  
  **Fichiers/modules**: `alembic/versions/<new>_add_definition_key_and_pipeline_definition.py` (à créer).
- [ ] **(≤2h)** Étendre la migration pour `agent_definitions.pipeline_definition` (JSONB nullable) (DM-2).  
  **Fichiers/modules**: même fichier Alembic que la tâche précédente.
- [ ] **(≤1.5h)** Mettre à jour les modèles SQLAlchemy pour exposer les champs (`AgentDefinition.pipeline_definition`, `TestScenario.definition_key`).  
  **Fichiers/modules** (High Complexity): `app/models/registry.py`, `app/models/test_lab.py`.

**Acceptance Criteria**:

- Must: AC-DM1-1 et AC-DM2-1 satisfaits (colonne présente, nullable, downgrade ok).

**Files and modules**:

- `alembic/versions/*add_definition_key_and_pipeline_definition*.py`
- (High Complexity) `app/models/registry.py`, `app/models/test_lab.py`

**Tests**:

- Manual (selon test plan): TC-DEFS-014, TC-DEFS-015 (upgrade/downgrade).

**Completion signal**:

- Commits (≤3 fichiers / commit) recommandés :
  - `build(db): add alembic migration for GH-14` (1 fichier Alembic)
  - `refactor(models): add definition fields for GH-14` (2 fichiers modèles)

---

### Phase 3: Schémas Pydantic v1 (TDD) — `app/schemas/definitions.py`

**Goal**: Introduire les schémas déclaratifs v1 avec discriminant `kind` et validation stricte (F-1, NFR-5).

**Tasks**:

- [x] **(≤2h)** (TDD) Écrire les tests unitaires de validation des 3 kinds (agent/orchestrator/scenario) + erreurs de schéma (TC-DEFS-001).  (`tests/unit/test_definitions_schemas_validation.py`, pytest PASS)
  **Fichiers/modules**: `tests/unit/test_definitions_schemas_validation.py`.
- [x] **(≤2h)** Implémenter `app/schemas/definitions.py` : modèles Pydantic v2, `schema_version="v1"`, discriminated union, `pipeline_definition` pour orchestrator, `definition_key` pour scenario.  (`app/schemas/definitions.py` ajouté)
  **Fichiers/modules** (High Complexity si schémas utilisés par routes/services): `app/schemas/definitions.py`.

**Acceptance Criteria**:

- Must: schémas valident les payloads attendus (F-1).
- Must: les payloads invalides échouent en validation (NFR-5).

Criterion: schémas valident les payloads attendus (F-1). — PASSED (`python3 -m pytest tests/unit/test_definitions_schemas_validation.py`)
Criterion: les payloads invalides échouent en validation (NFR-5). — PASSED (`python3 -m pytest tests/unit/test_definitions_schemas_validation.py`)

**Files and modules**:

- `app/schemas/definitions.py`
- `tests/unit/test_definitions_schemas_validation.py`

**Tests**:

- Unit: TC-DEFS-001.

**Completion signal**:

- Commits (≤3 fichiers / commit) recommandés :
  - `test: add unit tests for definitions schemas (GH-14)` (1 fichier)
  - `feat(schemas): add v1 definitions schemas (GH-14)` (1 fichier)

---

### Phase 4: Resolver service (validation dépendances) (TDD) — High Complexity: `app/services/`

**Goal**: Valider toutes les dépendances avant écriture DB (F-4), réutiliser au besoin la validation existante (familles/skills/MCPs) et produire des erreurs contextualisées.

**Tasks**:

- [ ] **(≤2h)** (TDD) Tests d’intégration du resolver : `family_id` inexistant/inactif ⇒ erreur (TC-DEFS-009).  
  **Fichiers/modules**: `tests/services/test_definition_resolver_service_family_id.py`.
- [ ] **(≤2h)** (TDD) Tests d’intégration : scénario avec `agent_id` inexistant ⇒ erreur claire (TC-DEFS-010).  
  **Fichiers/modules**: `tests/services/test_definition_resolver_service_scenario_agent_ref.py`.
- [ ] **(≤2h)** Implémenter `definition_resolver_service` :
  - validation family/skills via patterns existants (`agent_registry_service.validate_agent_definition`, `skill_service.resolve_skills`),
  - validation MCPs selon décision OQ-1,
  - validation orchestrator `pipeline_definition.stages[*].agent_id`.
  
  **Fichiers/modules** (High Complexity): `app/services/definition_resolver_service.py`.

**Acceptance Criteria**:

- Must: AC-F4-1 couvert (family_id invalide).
- Must: erreurs incluent suffisamment de contexte (`ref`, champs incriminés) pour API-3.

**Files and modules**:

- (High Complexity) `app/services/definition_resolver_service.py`
- `tests/services/test_definition_resolver_service_family_id.py`
- `tests/services/test_definition_resolver_service_scenario_agent_ref.py`

**Tests**:

- Integration: TC-DEFS-009, TC-DEFS-010.

**Completion signal**:

- Commits (≤3 fichiers / commit) recommandés :
  - `test: add resolver dependency validation tests (GH-14)` (2 fichiers)
  - `feat(services): add definition resolver service (GH-14)` (1 fichier)

---

### Phase 5: Import service (upsert idempotent + atomicité) (TDD) — High Complexity: `app/services/`

**Goal**: Importer des définitions en DB de façon idempotente (F-2), transactionnelle (NFR-4) et sans écraser des champs non déclarés (RSK-1).

**Tasks**:

- [ ] **(≤2h)** (TDD) Tests d’intégration import agent idempotent (no-op, 0 write DB au 2e import) (TC-DEFS-003).  
  **Fichiers/modules**: `tests/services/test_definition_import_service_idempotent_agent.py`.
- [ ] **(≤2h)** (TDD) Tests d’intégration import scénario idempotent par `definition_key` (TC-DEFS-004) + upsert sur key dupliquée (TC-DEFS-006).  
  **Fichiers/modules**: `tests/services/test_definition_import_service_idempotent_scenario.py`, `tests/services/test_definition_import_service_upsert_definition_key.py`.
- [ ] **(≤2h)** (TDD) Test d’intégration update agent (champ modifié ⇒ updated=1) sans bump inutile (TC-DEFS-005).  
  **Fichiers/modules**: `tests/services/test_definition_import_service_update_agent.py`.
- [ ] **(≤2h)** (TDD) Test d’intégration atomicité : batch (déf valide + orchestrateur invalide) ⇒ rollback complet + erreur contextualisée stage_id (TC-DEFS-011).  
  **Fichiers/modules**: `tests/integration/test_definition_import_atomicity_orchestrator_missing_agent.py`.
- [ ] **(≤2h)** (TDD) Test d’intégration orchestrateur : persiste `pipeline_definition` + renseigne `pipeline_agent_ids` dérivé (TC-DEFS-012).  
  **Fichiers/modules**: `tests/services/test_definition_import_service_orchestrator_pipeline_definition.py`.
- [ ] **(≤2h)** Implémenter `definition_import_service` :
  - tri des définitions (agents → orchestrators → scenarios) et/ou topo-sort selon dépendances (RSK-4),
  - appel resolver en amont (validate puis import),
  - transaction unique (tout ou rien),
  - upsert par `id` (agent/orchestrator) et `definition_key` (scenario),
  - comparaison canonique (Phase 1) pour no-op,
  - préservation des champs non déclarés (exclusions explicites),
  - événements EVT-1/EVT-2 via `emit_event`.
  
  **Fichiers/modules** (High Complexity): `app/services/definition_import_service.py`.

**Acceptance Criteria**:

- Must: AC-F2-1, AC-F2-2, AC-F2-3.
- Must: AC-F4-2 (rollback + erreur contextualisée).
- Must: NFR-1 et NFR-4.

**Files and modules**:

- (High Complexity) `app/services/definition_import_service.py`
- Tests listés ci-dessus.

**Tests**:

- Integration: TC-DEFS-003/004/005/006/011/012.

**Completion signal**:

- Commits (≤3 fichiers / commit) recommandés (exemple de découpage) :
  - `test: add import idempotence tests (GH-14)` (2 fichiers)
  - `test: add import update/upsert tests (GH-14)` (2 fichiers)
  - `test: add import atomicity + orchestrator pipeline tests (GH-14)` (2 fichiers)
  - `feat(services): add definition import service (GH-14)` (1 fichier)

---

### Phase 6: Export service (round-trip) + Endpoints REST (TDD) — High Complexity: `app/services/`, `app/api/routes/`

**Goal**: Exporter une entité vers JSON canonique (F-3) et exposer les endpoints API-1..3 avec validation 422, 404, et événements EVT-1..3.

**Tasks**:

- [ ] **(≤2h)** (TDD) Tests d’intégration export agent (TC-DEFS-007) + round-trip agent via endpoints (TC-DEFS-008).  
  **Fichiers/modules**: `tests/services/test_definition_export_service_agent.py`, `tests/integration/test_definitions_round_trip_agent.py`.
- [ ] **(≤2h)** Implémenter `definition_export_service` (canonique v1) + émission EVT-3.  
  **Fichiers/modules** (High Complexity): `app/services/definition_export_service.py`.
- [ ] **(≤2h)** (TDD) Tests endpoints import/export/validate + événements (TC-DEFS-013) + schéma invalide ⇒ 422 (TC-DEFS-002).  
  **Fichiers/modules**: `tests/integration/test_definitions_api_endpoints_and_events.py`, `tests/integration/test_definitions_api_schema_validation.py`.
- [ ] **(≤2h)** Implémenter la route FastAPI `definitions` (API-1..3) en s’appuyant sur schémas + services (validate = dry-run sans écriture).  
  **Fichiers/modules** (High Complexity): `app/api/routes/definitions.py` + enregistrement dans le routeur principal (fichier à identifier lors de l’exécution).

**Acceptance Criteria**:

- Must: API-1..3 conformes (200/404/409/422 selon spec).
- Must: AC-F3-1 (round-trip) et NFR-5 (rejet schéma avant écriture).
- Must: événements EVT-1..3 observables (au moins via spy/mock dans tests).

**Files and modules**:

- (High Complexity) `app/services/definition_export_service.py`
- (High Complexity) `app/api/routes/definitions.py`
- Tests listés ci-dessus.

**Tests**:

- Integration: TC-DEFS-002/007/008/013.

**Completion signal**:

- Commits (≤3 fichiers / commit) recommandés :
  - `test: add export + round-trip tests (GH-14)` (2 fichiers)
  - `feat(services): add definition export service (GH-14)` (1 fichier)
  - `test: add definitions endpoints tests (GH-14)` (2 fichiers)
  - `feat(api): add /api/definitions routes (GH-14)` (≤2 fichiers selon intégration routeur)

---

### Phase 7: Données JSON de référence + dépréciation scripts legacy + sync doc/spec

**Goal**: Livrer les JSON déclaratifs de référence (Appendice A) et guider l’équipe loin des scripts legacy.

**Tasks**:

- [x] **(≤2h)** Créer les fichiers JSON `data/registry/**` (5 agents + orchestrateur) conformément au schéma v1 (AC-F1-1).  (Créés/mis à jour: `data/registry/agents/{budget_fit_agent,mobility_agent,stay_discovery_agent,weather_agent}.json`, `data/registry/orchestrators/hotel_pipeline_orchestrator.json`; mapping extrait verbatim des constantes `AGENT` legacy, `pipeline_definition` séquentiel avec `stage_id` déterministes)
  **Fichiers/modules**: `data/registry/agents/*.json`, `data/registry/orchestrators/*.json`.
- [x] **(≤2h)** Créer les fichiers JSON scénarios `data/test_lab/scenarios/*.json` avec `definition_key` stables (AC-F2-2).  (Créés: 5 scénarios `data/test_lab/scenarios/scn-*.json` depuis constantes `SCENARIO` legacy; `definition_key` déterministe `scn-<agent>--<name>--<sha1[:8]>`, champs/scénarios copiés verbatim, `enabled=true` explicite)
  **Fichiers/modules**: `data/test_lab/scenarios/*.json`.
- [x] **(≤2h)** Marquer les 5 scripts legacy `scripts/create_*.py` comme `DEPRECATED` (sans suppression) (AC-F7-1).  (Headers DEPRECATED exacts ajoutés en tête des 5 scripts: `create_budget_fit_agent.py`, `create_hotel_pipeline_orchestrator.py`, `create_mobility_agent.py`, `create_stay_discovery_agent.py`, `create_weather_agent.py`)
  **Fichiers/modules**: `scripts/create_*.py` (les 5 scripts visés par la spec).

**Acceptance Criteria**:

- Must: AC-F1-1 (inventaire minimal de fichiers JSON + validation via schémas).
- Must: AC-F7-1 (header DEPRECATED).

Criterion: AC-F1-1 (inventaire minimal de fichiers JSON + validation via schémas). — PASSED (`python3` validation via `validate_definition_payload` sur 10 fichiers GH-14: 4 agents, 1 orchestrateur, 5 scénarios)
Criterion: AC-F7-1 (header DEPRECATED). — PASSED (headers exacts présents en tête des 5 scripts `scripts/create_*.py` ciblés)

**Files and modules**:

- `data/registry/**`
- `data/test_lab/scenarios/**`
- `scripts/create_*.py`

**Tests**:

- Unit: TC-DEFS-001 (peut charger quelques JSON de référence comme fixtures si souhaité).
- Manual: TC-DEFS-016.

**Completion signal**:

- Commits (≤3 fichiers / commit) recommandés (découper par sous-dossier ou groupe de 2-3 fichiers max) :
  - `docs(data): add registry JSON definitions (GH-14)` (≤3 fichiers)
  - `docs(data): add test-lab scenario JSON definitions (GH-14)` (≤3 fichiers)
  - `docs: deprecate legacy creation scripts (GH-14)` (≤3 fichiers)

---

### Phase 8: Code Review, correctifs post-review, finalisation & release

**Goal**: Stabiliser, aligner spec↔impl, et préparer la livraison (inclut bump de version selon conventions repo).

**Tasks**:

- [ ] **(≤2h)** Revue de code (auto + pair) focalisée sur High Complexity zones (`models/services/routes`) et exigences NFR (idempotence, atomicité).  
  **Fichiers/modules**: revue transversale.
- [ ] **(≤2h)** Correctifs post-review (si nécessaire) — appliquer les changements par petits commits (≤3 fichiers/commit).  
  **Fichiers/modules**: selon retours.
- [ ] **(≤2h)** Finaliser “release” :
  - bump de version **minor** selon convention du repo (à localiser : fichier/versioning en vigueur),
  - reconciliation spec (si des détails ont divergé : codes d’erreur, payloads, canonicalisation).
  
  **Fichiers/modules**: fichier(s) de version + artefacts doc si requis.

**Acceptance Criteria**:

- Must: tous les TC automatisés (unit + integration) passent.
- Must: migrations validées (TC-DEFS-014/015 au moins en smoke).
- Must: endpoints API-1..3 conformes.

**Files and modules**:

- Versioning: à identifier.

**Tests**:

- Suite complète pytest + check Alembic.

**Completion signal**:

- État : “ready for PR” + version bump appliqué + spec reconcile effectuée.

## Test Scenarios

Référence : `chg-GH-14-test-plan.md`. Les scénarios ci-dessous doivent être couverts avant release.

- **Schémas** : TC-DEFS-001 (unit), TC-DEFS-002 (integration / 422).
- **Import idempotent / upsert** : TC-DEFS-003/004/005/006.
- **Resolver dépendances** : TC-DEFS-009/010.
- **Atomicité import** : TC-DEFS-011.
- **Orchestrateur pipeline_definition** : TC-DEFS-012.
- **Export & round-trip** : TC-DEFS-007/008.
- **Endpoints & events** : TC-DEFS-013.
- **Migrations** : TC-DEFS-014/015 (manual/smoke).
- **Legacy scripts** : TC-DEFS-016 (manual).
- **Perf (optionnel)** : TC-DEFS-017 (hors CI si non stabilisé).

## Artifacts and Links

- Spec: `doc/changes/2026-04/2026-04-26--GH-14--declaratif-json-import-export/chg-GH-14-spec.md`
- Test plan: `doc/changes/2026-04/2026-04-26--GH-14--declaratif-json-import-export/chg-GH-14-test-plan.md`

**Zones High Complexity impactées (attention review)** :

- `app/models/registry.py` (AgentDefinition)
- `app/models/test_lab.py` (TestScenario)
- `app/services/*` (import/export/resolver)
- `app/api/routes/*` (nouvelle route definitions)

**Fichiers existants à considérer pour intégration** (réf. demande) :

- `app/services/agent_registry_service.py` (validation famille/skills, version bump sur update — à éviter côté import)
- `app/services/test_lab/scenario_service.py` (CRUD scénarios, commit/refresh — l’import devra choisir une approche cohérente)
- `app/api/routes/agents.py` et `app/api/routes/test_lab.py` (patterns d’API existants)

## Plan Revision Log

| Date (UTC) | Auteur | Changement |
|---|---|---|
| 2026-04-26 | @plan-writer | Création initiale du plan d’implémentation (Proposed). |

## Execution Log

| Date (UTC) | Phase | Résultat | Notes |
|---|---|---|---|
| 2026-04-26 | Phase 1 | DONE | OQ-1/OQ-2 verrouillées avec @architect; canonicalisation implémentée + tests unitaires PASS. |
| 2026-04-26 | Phase 3 | DONE | Schémas déclaratifs v1 ajoutés avec union discriminée + tests unitaires verts. |
| 2026-04-26 | Phase 7 (reliquat) | DONE | JSON GH-14 finalisés depuis constantes legacy (agents/orchestrateur/scénarios), clés `definition_key` déterministes, headers DEPRECATED ajoutés aux 5 scripts legacy, validation schéma ciblée PASS. |
| TBD | TBD | TBD | TBD |
