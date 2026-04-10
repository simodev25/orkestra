# Audit Architecture & Production Readiness
## Agents / Families / Agent Skills / Test Lab / MCP Catalog

**Date**: 2026-04-07
**Scope**: Orkestra v0.1.0 -- Governed multi-agent orchestration platform
**Reviewer**: Staff-level architecture & production readiness audit
**Branch**: `feature/agen_run`

---

## 1. Executive Summary

### Niveau de maturite global : **Prototype avance / Pre-MVP**

Orkestra est une plateforme ambitieuse de gouvernance et d'orchestration multi-agents avec un design conceptuel remarquablement mature pour son stade de developpement. L'architecture de gouvernance (familles, skills, lifecycle agents, validation MCP, Test Lab scenarises) est intellectuellement solide et bien pensee. Cependant, l'implementation presente des ecarts significatifs entre la vision produit et la realite technique, avec des modules critiques incomplets, une absence totale d'authentification, et des couches de mock data qui masquent les limitations reelles du systeme.

### Verdict global

**Le systeme n'est PAS pret pour la production.** C'est un prototype avance avec des fondations architecturales prometteuses mais des lacunes structurelles bloquantes. Certaines parties (modele de familles/skills, state machines, prompt builder) sont de bonne qualite et peuvent etre conservees. D'autres (Test Lab, securite, MCP governance runtime) doivent etre significativement renforcees.

### Principaux risques

1. **CRITIQUE** -- 6 tables de la base de donnees (tout le Test Lab scenariste) n'ont pas de migrations : crash garanti en production
2. **CRITIQUE** -- Zero authentification/autorisation sur aucun endpoint : toute l'API est ouverte
3. **CRITIQUE** -- Les secrets (cles API) sont stockes en clair dans la DB
4. **ELEVE** -- Mock data silencieux masque les echecs backend dans l'UI MCP Toolkit
5. **ELEVE** -- Deux systemes de Test Lab paralleles et incompatibles coexistent sans integration
6. **ELEVE** -- Pas de contraintes de cle etrangere entre les 15+ entites operationnelles
7. **ELEVE** -- Fallback silencieux de l'execution MCP/agent vers des resultats simules

### Principaux quick wins

1. Ajouter la migration manquante pour les 6 tables Test Lab (1-2 jours)
2. Ajouter un middleware d'authentification basique avec API keys (2-3 jours)
3. Chiffrer `PlatformSecret.value` avec Fernet (1 jour)
4. Supprimer les fallback mock silencieux dans le MCP executor (1 jour)
5. Ajouter `selectinload` pour les relations Agent->Skills et Agent->Family (1 jour)

---

## 2. Scope analyse

### Modules/fichiers inspectes

**Backend Python** (~120 fichiers) :
- `app/models/` : 19 fichiers (toutes les entites ORM)
- `app/schemas/` : 16 fichiers (tous les schemas Pydantic)
- `app/services/` : 28 fichiers incluant `test_lab/` sous-module (6 fichiers)
- `app/api/routes/` : 19 fichiers (toutes les routes API)
- `app/state_machines/` : 8 fichiers (toutes les machines a etats)
- `app/mcp_servers/` : 4 fichiers (implementations MCP locales)
- `app/llm/` : 1 fichier (provider LLM)
- `app/core/` : 2 fichiers (config, database)
- `app/tasks/` : 1 fichier (Celery tasks)
- `migrations/versions/` : 9 fichiers (toutes les migrations)
- `app/config/` : 2 fichiers (seeds families, skills)
- `tests/` : 22 fichiers (~2081 lignes)

**Frontend TypeScript/React** (~65 fichiers) :
- `frontend/src/app/` : 22 pages (toutes les routes)
- `frontend/src/components/` : 16 composants
- `frontend/src/lib/` : 20 fichiers (types, services, API clients)
- Config : `package.json`, `tailwind.config.ts`, `tsconfig.json`

**Infrastructure** :
- `docker-compose.yml` (10 services)
- `observability/` : configs OTEL, Prometheus, Tempo, Grafana
- `pyproject.toml`

### Flux de bout en bout reconstitues

1. Creation agent : UI form -> `POST /api/agents` -> `agent_registry_service.create_agent()` -> validation + skill sync + DB persist + audit event
2. Relation agent <-> family : FK `family_id` sur `AgentDefinition`, ORM relationship, prompt builder injecte les rules de la family
3. Relation agent <-> skills : Table de jointure `AgentSkill`, sync bidirectionnelle, skill content cascade vers prompt
4. Relation agent <-> MCPs : Resolution via `obot_catalog_service` (Obot catalog) OU `MCP_TOOL_MAP` hardcode (local tools)
5. Test Lab (agent) : `POST /api/agents/{id}/test-run` -> route handler (220 lignes inline) -> `ReActAgent` + behavioral checks client-side
6. Test Lab (scenario) : `POST /api/test-lab/scenarios/{id}/run` -> Celery task -> 5-phase orchestration (prep/runtime/assertions/diagnostics/verdict) -> SSE streaming
7. MCP Catalog : Sync depuis Obot -> bindings locaux -> exposition via API -> resolution dans agent factory

---

## 3. Architecture actuelle reconstituee

### Vue d'ensemble

```
                    +-------------------+
                    |   Next.js Frontend |
                    |  (Port 3300)       |
                    +--------+----------+
                             |
                             | HTTP REST
                             v
                    +-------------------+
                    |   FastAPI Backend  |
                    |  (Port 8200)       |
                    +--------+----------+
                             |
              +--------------+-------------+
              |              |             |
              v              v             v
        +-----------+  +-----------+  +-----------+
        | PostgreSQL |  |   Redis   |  |   Obot    |
        |  (5434)    |  |  (6382)   |  |  (8080)   |
        +-----------+  +-----------+  +-----------+
                             |
                             v
                    +-------------------+
                    |  Celery Worker    |
                    |  (test lab runs)  |
                    +--------+----------+
                             |
                             v
                    +-------------------+
                    |  Ollama / OpenAI  |
                    |  (LLM providers)  |
                    +-------------------+

    Observability: OTEL Collector -> Tempo (traces) + Prometheus (metrics) -> Grafana
```

### Separation des responsabilites

| Couche | Technologie | Rôle |
|--------|-------------|------|
| Frontend | Next.js 14, Tailwind CSS, TypeScript | UI, navigation, state local |
| API | FastAPI, Pydantic v2 | Routing, validation, HTTP |
| Services | Python async functions | Business logic, lifecycle, validation |
| State Machines | Custom Python | Transitions d'etat, garde-fous |
| ORM | SQLAlchemy 2.0 (async) | Persistence, mapping |
| DB | PostgreSQL 16 | Stockage primaire |
| Cache/PubSub | Redis 7 | SSE events, Celery broker |
| Worker | Celery | Test Lab execution asynchrone |
| LLM | AgentScope + Ollama/OpenAI | ReAct agents, prompt execution |
| MCP Source | Obot platform | Catalogue externe d'outils |
| Observability | OTEL + Prometheus + Tempo + Grafana | Traces, metriques |

### Points de couplage critiques

1. **Frontend <-> Backend** : Pas de contrat OpenAPI genere/consomme. Types dupliques des deux cotes.
2. **Agent Factory <-> Obot** : Resolution MCP passe par le catalogue Obot en runtime.
3. **Celery Worker <-> DB** : Cree des engines SQLAlchemy synchrones ad-hoc (pas de pool partage).
4. **Route handlers <-> Services** : Generalement propre, sauf `run_agent_test` (220 lignes de logique dans la route).

---

## 4. Review par domaine

### 4.1 Agents

**Role attendu** : Registre gouverne d'agents IA avec lifecycle, versioning, validation, promotion, et integration aux familles/skills/MCPs.

**Implementation reelle** :
- Modele `AgentDefinition` riche : 30+ champs incluant `status`, `criticality`, `cost_profile`, `version`, `owner`, `family_id`, `soul_content`, `prompt_content`, `skills_content`, `allowed_mcps`, `forbidden_effects`, `limitations`, `llm_provider`, `llm_model`.
- CRUD complet via `agent_registry_service.py` (617 lignes).
- Lifecycle gere par `AgentLifecycleSM` : draft -> tested -> registered -> active -> deprecated/disabled -> archived.
- Historique versionne via `AgentDefinitionHistory` avec snapshot avant chaque modification.
- Enrichissement systematique via `enrich_agent()` (resolution family, skills, MCPs).
- Generation de draft via heuristiques deterministes (pas de LLM malgre l'UI qui suggere "AI-powered generation").
- Integration AgentScope pour l'execution via `agent_factory.create_agentscope_agent()`.

**Ecarts** :
- `AgentCreate` schema permet au client de setter `last_test_status`, `last_validated_at`, `usage_count` -- champs operationnels qui devraient etre read-only.
- `agent_id` est user-supplied (natural key) sans unicite verifiee cote frontend.
- Le champ `status` est un `str` sans contrainte de base de donnees -- n'importe quelle valeur est acceptee.
- Le `generate-draft` endpoint ne fait PAS appel a un LLM malgre le naming. `source="mock_llm"` dans la reponse.

**Points forts** :
- Modele de donnees complet et bien pense.
- Lifecycle state machine robuste avec transitions gardees.
- Versioning avec historique et restauration fonctionnels.
- Prompt builder multi-couches integrant family rules, skill behaviors, agent soul.
- Event sourcing via `emit_event()` sur chaque operation.

**Fragilites** :
- N+1 queries sur le listing (3 queries supplementaires par agent via `enrich_agent()`).
- `AgentStatus` enum non enforce en DB.
- Pas de concurrence optimiste (pas de version number pour eviter les ecrasements).

**Dette technique** :
- Route `run_agent_test` de 220 lignes avec business logic inline.
- Duplication du select dans `_sync_agent_skills()` (query executee deux fois).
- `family_rel` naming non-standard pour la relation ORM.

**Risques prod** :
- Sans auth, n'importe qui peut creer/modifier/supprimer des agents.
- Le `generate-draft` retourne des donnees mock -- attention a ne pas vendre ca comme de l'IA.

**Note : 6.5/10**

---

### 4.2 Families

**Role attendu** : Taxonomie d'agents avec regles par defaut, effets interdits, attentes de sortie, propagees a tous les agents membres.

**Implementation reelle** :
- Modele `FamilyDefinition` avec : `label`, `description`, `default_system_rules` (JSONB), `default_forbidden_effects` (JSONB), `default_output_expectations` (JSONB), `status`, `version`, `owner`.
- 8 familles pre-definies dans `families.seed.json` : Preparation, Analysis, Design, Execution, Governance, Decision, Delivery, Validation.
- CRUD complet dans `family_service.py`.
- Relation M-N avec skills via `SkillFamily` join table.
- Relation 1-N avec agents via FK `family_id`.
- Historique versionne via `FamilyDefinitionHistory`.
- Garde de suppression : impossible de supprimer une famille avec des agents attaches.

**Ecarts** :
- Le `status` de famille defaulte a la string `"active"` sans enum defini (pas de `FamilyStatus` dans `enums.py`).
- Pas de notion d'heritage hierarchique entre familles.
- Les `default_system_rules` sont injectees dans le prompt mais pas validees structurellement.

**Points forts** :
- Concept solide de gouvernance par famille -- les effets interdits et les regles systeme sont bien integres dans le prompt builder.
- Le seed data est bien structure et semantiquement coherent.
- La cascade skill -> famille -> agent est implementee.
- L'archivage est prefere a la suppression hard.

**Fragilites** :
- `SkillFamily` join table n'a pas de timestamps -- impossible de savoir quand une association a ete creee.
- `label` vs `name` inconsistance avec les agents (agents utilisent `name`).

**Dette technique** : Mineure. Module relativement propre.

**Risques prod** :
- Sans validation de `status`, des etats invalides peuvent etre inseres.
- Pas de permissions : n'importe qui peut modifier les familles fondamentales.

**Note : 7/10**

---

### 4.3 Agent Skills

**Role attendu** : Capacites composables assignables aux agents, avec templates comportementaux et guidelines de sortie, gouvernees par compatibilite avec les familles.

**Implementation reelle** :
- Modele `SkillDefinition` avec : `label`, `category`, `description`, `allowed_families` (JSONB), `behavior_templates` (JSONB), `output_guidelines` (JSONB), `status`, `version`, `owner`.
- 14 skills pre-definis dans `skills.seed.json` (user need reformulation, task structuring, requirements extraction, etc.).
- Relation M-N avec familles via `SkillFamily` et avec agents via `AgentSkill`.
- `allowed_families` restreint quelles familles peuvent utiliser un skill -- valide a la creation d'agent.
- Cascade de contenu : quand un skill est modifie, le contenu est propage a tous les agents referencants via `_cascade_skills_content()`.
- Historique versionne via `SkillDefinitionHistory`.

**Ecarts** :
- Les `behavior_templates` et `output_guidelines` sont des listes de strings -- pas de structure riche (pas de parametres, pas de schema d'entree/sortie, pas de type de retour).
- Un skill n'a pas de notion d'"execution" -- c'est purement un ensemble de regles textuelles injectees dans le prompt. Ce n'est pas un "skill executif" au sens classique.
- `AgentSkill` join table n'a pas de timestamps.

**Points forts** :
- La gouvernance par `allowed_families` est une excellente idee -- les skills preparation ne peuvent pas etre utilises par un agent governance.
- La cascade `_cascade_skills_content` garantit la coherence entre skill definition et agent prompt.
- Le seed data est semantiquement riche et bien categorise.

**Fragilites** :
- Skills sont purement textuels -- pas de schema machine-readable pour validation structurelle des sorties.
- Pas de notion de "version de skill utilise par un agent" -- l'agent recoit toujours la derniere version.
- Pas de dependency entre skills (skill A requiert skill B).

**Dette technique** :
- `list_skills_with_agents` route contient un join query inline au lieu d'utiliser le service layer.

**Risques prod** :
- Modifier un skill propage automatiquement a TOUS les agents qui l'utilisent -- pas de validation intermediaire, pas de staging.

**Note : 6.5/10**

---

### 4.4 Test Lab

**Role attendu** : Infrastructure de test qualite pour valider le comportement des agents avant promotion, avec scenarios, assertions, diagnostics, scoring, et verdict.

**Implementation reelle** :

**DEUX systemes de Test Lab coexistent** :

**Systeme 1 -- Agent Test Lab (per-agent, `/agents/{id}/test-lab`)** :
- Route `POST /api/agents/{id}/test-run` : 220 lignes inline dans le handler de route.
- Cree un `AgentTestRun` (modele simplifie, `agent_test_runs` table).
- Execute via `agent_test_service.execute_test_run()` -> `ReActAgent`.
- Behavioral checks evalues **cote client** via `mock-runner.ts` avec des heuristiques naives :
  - `stayInScope` : cherche la string "not within my scope" dans la reponse.
  - `flagsMissingData` : retourne toujours `true`.
  - `handlesAmbiguity` : retourne toujours `true`.
  - `refusesOutOfScopeAction` : retourne toujours `true`.
- Verdict calcule cote client (pas de validation server-side).
- Debug JSON ecrit sur disque.
- "Save case" button n'a aucun `onClick` -- bouton mort.

**Systeme 2 -- Agentic Test Lab (scenario-based, `/test-lab`)** :
- Modeles riches : `TestScenario`, `TestRun`, `TestRunEvent`, `TestRunAssertion`, `TestRunDiagnostic`.
- **MAIS : 6 tables n'ont AUCUNE migration.** Ces tables n'existent pas en base apres `alembic upgrade head`.
- Orchestration 5 phases via Celery + workers LLM (preparation, runtime, assertions, diagnostics, verdict).
- Assertion engine deterministe (8 types d'assertions).
- Diagnostic engine deterministe (7 patterns detectes).
- Scoring engine (0-100 avec penalites).
- SSE streaming via Redis pub/sub.
- Agent summary avec qualification gate (3 runs minimum, 80% pass rate).

**Ecarts MAJEURS** :
- Le systeme 2 est structurellement superieur mais **completement non-fonctionnel** a cause des migrations manquantes.
- Le systeme 1 est fonctionnel mais les checks comportementaux sont des facades (toujours `true`).
- Les deux systemes utilisent des modeles de donnees differents (`AgentTestRun` vs `TestRun`) avec des vocabulaires de verdict incompatibles (`"pass"/"fail"` vs `"passed"/"failed"`).
- Pas de lien entre les deux systemes.
- Bug dans `orchestrator.py` ligne 469 : `msg_count` non defini -> `NameError` a l'execution.
- Le Celery worker cree un `create_engine()` a chaque event (15+ par test run) au lieu d'utiliser un pool.

**Points forts** :
- La vision du systeme 2 est excellente : scenarios declaratifs, assertions deterministes, diagnostics automatiques, scoring, SSE live.
- L'assertion engine couvre les cas essentiels (tool_called, output_schema_matches, max_duration_ms, etc.).
- Le diagnostic engine detecte des patterns utiles (tool_failure, timeout, excessive_iterations).
- L'agent summary avec qualification gate est un bon concept de lifecycle.

**Fragilites** :
- Systeme 2 inutilisable sans migration.
- Systeme 1 donne un faux sentiment de qualite avec des checks bidon.
- Pas de notion de dataset de test, de test reproductible, de baseline regression.
- Pas de lien Test Lab -> lifecycle agent (la promotion n'est pas bloquee par les resultats de test en pratique).

**Dette technique** : Massive. Deux systemes paralleles, migrations manquantes, bugs runtime.

**Risques prod** :
- Crash garanti sur tout appel Test Lab scenario en production.
- Les checks comportementaux trompeurs peuvent donner l'impression qu'un agent est valide alors qu'il ne l'est pas.

**Note : 3/10**

---

### 4.5 MCP Catalog

**Role attendu** : Registre gouverne d'outils MCP avec decouverte, validation, permissions, monitoring, et integration agents.

**Implementation reelle** :

**DEUX registres MCP coexistent** :

**Registre 1 -- Obot Catalog (`/api/mcp-catalog`)** :
- Source de verite : Obot platform externe.
- `obot_catalog_service.py` (687 lignes) : sync, import, binding, filtering.
- `OrkestraMCPBinding` table : overlay local sur les MCPs Obot (enabled, business_domain, risk_level, allowed_workflows, agent_family_tags).
- Mock data embarque : `_MOCK_OBOT_SERVERS` (100 lignes hardcodees) utilise en fallback.
- Stats, filtering par categorie, binding workflows/families.

**Registre 2 -- Local MCP Registry (`/api/mcps`)** :
- `MCPDefinition` modele local avec lifecycle (draft -> tested -> registered -> active).
- `mcp_registry_service.py` : CRUD + lifecycle transitions.
- `mcp_validation_engine.py` : Validation multi-regles sophistiquee (structural, governance, runtime, contract, integration).
- Health monitoring, usage stats.

**Resolution runtime des MCPs pour les agents** :
- `agent_factory.py` utilise DEUX mecanismes :
  - `MCP_TOOL_MAP` hardcode : mapping statique de MCP IDs vers des fonctions Python locales (weather, search_engine, consistency_checker, document_parser).
  - `resolve_mcp_servers()` : resolution via `obot_catalog_service.available_mcp_summaries()` pour obtenir des URLs, puis connexion HTTP streamable.
- `mcp_executor.py` : TROISIEME mapping parallele identique a `MCP_TOOL_MAP`.

**Ecarts** :
- Trois voies paralleles de resolution MCP (factory local, factory Obot, executor local) qui peuvent diverger.
- Les MCPs locaux (`search_engine`, `consistency_checker`) retournent des donnees simulees, pas de vrais resultats.
- L'MCP executor a un fallback silencieux vers des resultats simules en cas d'echec (confidence 0.85 hardcodee).
- `MCPDefinition` n'a pas de table d'historique (contrairement aux agents, familles, skills).
- L'MCP validation engine est sophistique mais n'est appele que manuellement (pas de gate automatique sur les transitions de lifecycle).
- Pas de timeout/rate limiting/quota sur l'invocation des outils MCP.

**Points forts** :
- La validation engine est impressionnante : 5 categories de regles, scoring, integration testing.
- Le concept de `OrkestraMCPBinding` pour superposer de la gouvernance locale sur un catalogue externe est intelligent.
- Le lifecycle MCP avec degraded state est bien pense.
- Le binding par workflow et par agent family permet un scoping fin.

**Fragilites** :
- Le `_MOCK_OBOT_SERVERS` embarque cree de la confusion sur ce qui est reel vs simule.
- `mcp_executor` retourne des resultats faux en cas d'echec sans signalement clair.
- Pas de cache sur les appels Obot -- chaque listing re-interroge l'API externe.
- Le frontend MCP Toolkit utilise `MOCK_MCPS` en fallback silencieux -- l'UI semble toujours fonctionner meme sans backend.

**Dette technique** :
- Triple mapping MCP a consolider.
- Mock data a isoler du code de production.
- Absence d'historique pour `MCPDefinition`.

**Risques prod** :
- Un MCP defaillant retourne quand meme un resultat "reussi" via le fallback.
- Sans auth, n'importe qui peut enable/disable des MCPs ou modifier des bindings.
- Les MCPs Obot sont appeles sans retry ni circuit breaker.
- Pas de log d'invocation MCP exploitable pour audit.

**Note : 5/10**

---

## 5. Review transverse

### 5.1 Frontend

**Constats** :
- 22 pages, 16 composants partages, 20 fichiers de lib (types + services).
- Pas de state management global (pas de React Context, Zustand, Redux, SWR, React Query).
- Chaque page gere son propre etat via `useState`/`useEffect`.
- Pas de cache partage -- chaque navigation re-fetch tout.
- Design system coherent (glassmorphism, JetBrains Mono, palette cyber) mais pas de design tokens extraits.
- 9 liens sidebar vers des pages inexistantes (phantom routes).
- Deux systemes de types paralleles (`lib/types.ts` vs `lib/agent-registry/types.ts`).
- 5 copies identiques de la fonction `request<R>()` dans les services.
- Mix de raw `fetch()` et de service abstractions.
- Formulaires : validation correcte sur les agents, minimale sur les MCPs et scenarios.
- Accessibilite quasi absente (pas d'ARIA, pas de focus trapping, pas de navigation clavier, contraste insuffisant).
- Zero responsive design (sidebar fixe 224px, pas de breakpoint mobile).

**Preuves concretes** :
- `frontend/src/lib/mcp/service.ts` : `catch () { return MOCK_MCPS; }` sur 6 fonctions.
- `frontend/src/lib/agent-test-lab/mock-runner.ts` : `handlesAmbiguity: () => true`, `refusesOutOfScopeAction: () => true`.
- `frontend/src/components/layout/sidebar.tsx` : liens vers `/requests`, `/cases`, `/plans`, `/runs`, `/control`, `/approvals`, `/audit`, `/workflows`, `/admin` -- aucune de ces pages n'existe.
- `frontend/src/app/agents/page.tsx` ligne 420 : `StatCard` redefini localement alors que `components/ui/stat-card.tsx` existe.

**Risques** :
- L'utilisateur ne peut pas distinguer les donnees reelles des donnees mock.
- La navigation brisee donne une impression d'inachevement.
- Sans cache, la performance se degrade avec l'echelle.

**Recommandations** :
1. Adopter React Query ou SWR pour le data fetching et le caching.
2. Supprimer les fallback mock silencieux -- afficher clairement les erreurs.
3. Retirer les liens sidebar vers les pages non implementees.
4. Extraire un `useApi<T>()` hook unifie au lieu de 5 copies de `request()`.
5. Ajouter un mobile layout avec sidebar collapsible.

### 5.2 Backend

**Constats** :
- Architecture fonctionnelle par module : routes thin -> services -> ORM. Pattern bien respecte.
- 19 routes files, 28 service modules, 8 state machines.
- Services sont des modules Python avec des fonctions async (pas de classes) -- cohesion par domaine.
- Validation metier dans les services : `validate_agent_definition()`, `validate_mcp_definition()`.
- Event sourcing via `emit_event()` sur chaque mutation.
- History snapshots avant chaque update (agents, families, skills).

**Preuves concretes d'anti-patterns** :
- `app/api/routes/agents.py:run_agent_test` (lignes 238-461) : 220 lignes de business logic dans un handler de route.
- `app/services/mcp_executor.py` lignes 115-126 : fallback silencieux vers resultats simules.
- `app/services/subagent_executor.py` lignes 72-91 : meme pattern de fallback simule.
- `app/services/agent_registry_service.py` lignes 126-128 : query executee mais resultat jamais utilise (copy-paste bug).
- `app/services/test_lab/orchestrator.py` lignes 38-51 : `create_engine()` appele a chaque event emit.

**Risques** :
- Zero authentication middleware.
- Auto-commit sur `get_db()` commit meme les reads.
- Pas de global exception handler.
- Pas d'exception hierarchy custom (tout est `ValueError`).

**Recommandations** :
1. Extraire `run_agent_test` vers un service dedie.
2. Supprimer les fallbacks silencieux vers la simulation.
3. Ajouter un middleware d'authentification.
4. Creer une hierarchie d'exceptions metier (NotFound, ValidationError, StateViolation, AuthorizationDenied).
5. Ajouter un global exception handler FastAPI.

### 5.3 Data model / DB

**Constats** :
- 25+ entites ORM avec `BaseModel` commun (id, created_at, updated_at).
- 3 strategies de generation d'ID coexistent (prefixed short, user-supplied natural key, UUID4).
- Zero FK constraints sur les entites operationnelles (Request, Case, Run, RunNode, Invocations).
- ORM relationships definies SEULEMENT sur Family <-> Agent <-> Skill. Toutes les autres entites n'ont aucune relationship.
- 6 tables de Test Lab sans migrations.
- `Mapped[str]` sur des colonnes `DateTime` dans 6+ modeles.
- `AgentTestRun` et `TestRun` sont des modeles dupliques avec vocabulaire incompatible.
- `PlatformSecret.value` en clair.
- `new_id()` utilise 48 bits d'entropie (collision probable a ~16.7M records).

**Index manquants critiques** :
- `subagent_invocations.agent_id`
- `mcp_invocations.mcp_id`
- `cases.tenant_id`, `requests.tenant_id`
- `test_runs.status`, `test_run_events.event_type`
- Composite `(run_id, status)` sur `run_nodes`

**Recommandations** :
1. Ecrire la migration pour les 6 tables Test Lab.
2. Consolider `AgentTestRun` et `TestRun` en un seul modele.
3. Corriger les type hints `Mapped[str]` -> `Mapped[datetime]`.
4. Ajouter les index manquants.
5. Augmenter l'entropie de `new_id()` (utiliser full UUID4).
6. Chiffrer les secrets.

### 5.4 LLM / Prompt architecture

**Constats** :

**Points d'entree LLM reels** :
1. `agent_test_service.execute_test_run()` -- ReAct agent pour test per-agent.
2. `subagent_executor._execute_with_agentscope()` -- ReAct agent pour execution de production.
3. `test_lab/orchestrator.run_worker()` -- 4 workers LLM pour le Test Lab scenariste.
4. `test_lab/orchestrator._execute_target_agent()` -- Agent sous test dans le Test Lab.

**`agent_generation_service.generate_agent_draft()`** NE fait PAS appel a un LLM. C'est du keyword matching deterministe retournant `source="mock_llm"`.

**Prompt builder** (`prompt_builder.py`) :
- Architecture 7 couches bien pensee :
  1. Family system rules
  2. Skill behavior templates + output guidelines
  3. Soul content (personnalite optionnelle)
  4. Agent mission (purpose + description + prompt_content)
  5. Output expectations
  6. Contract references
  7. Runtime context (criticality, forbidden effects, allowed MCPs, limitations)
- Merge des forbidden effects (union family + agent).
- Injection des MCPs autorises dans le prompt.
- Les skills sont concatenes textuellement dans le prompt.

**Preuves concretes** :
- `app/services/prompt_builder.py` lignes 85-106 : merge des forbidden effects family + agent.
- `app/services/agent_factory.py` lignes 128-160 : creation du ReAct agent avec toolkit MCP.
- `app/services/test_lab/orchestrator.py` lignes 290-320 : worker LLM avec system prompt specifique par phase.

**Risques** :
- Prompts non versionnes independamment -- changes quand le code change.
- Pas de schema de sortie enforce sur les reponses LLM (le ReAct agent retourne du texte libre).
- Le max_round du ReAct agent est hardcode a 3 -- risque de boucle infinie si augmente sans garde-fou.
- Pas de validation des sorties LLM contre un schema attendu.
- La logique metier (forbidden effects, system rules) vit dans le prompt -- si le LLM desobeit, pas de garde-fou deterministe.
- Le Test Lab workers utilisent Ollama cloud (`https://ollama.com`) comme endpoint -- pas un endpoint Ollama local.

**Recommandations** :
1. Ajouter un schema de sortie JSON pour les agents et valider les reponses LLM.
2. Versionner les prompts separement du code.
3. Ajouter des garde-fous deterministes post-LLM (verifier que les forbidden effects ne sont pas violes dans la sortie).
4. Configurer correctement l'endpoint Ollama pour le Test Lab.
5. Ajouter un budget token par agent avec enforcement.

### 5.5 MCP / Tool governance

**Constats** :
- Triple mapping MCP : `agent_factory.MCP_TOOL_MAP`, `mcp_executor._get_mcp_tools()`, `agent_factory.resolve_mcp_servers()`.
- 4 tools locaux implementes : weather (reel API Open Meteo), search_engine (simule), consistency_checker (simule), document_parser (simule).
- `mcp_validation_engine.py` : 5 categories, 15+ regles, scoring -- bien fait mais appele manuellement.
- `OrkestraMCPBinding` : binding local sur Obot avec `risk_level`, `allowed_workflows`, `agent_family_tags`.
- Pas de runtime enforcement de `allowed_mcps` au-dela de l'injection dans le prompt.
- Pas d'allowlist/denylist enforced cote executor (l'agent decide seul via le prompt).

**Preuves** :
- `app/services/mcp_executor.py` ligne 115 : `result = {"output": "Simulated...", "confidence": 0.85}`.
- `app/services/agent_factory.py` ligne 50-65 : `MCP_TOOL_MAP` hardcode.
- `app/mcp_servers/search_engine.py` : retourne des resultats fabriques, pas de vraie recherche.
- `app/mcp_servers/consistency_checker.py` : retourne des inconsistances fabriquees.

**Risques** :
- Un agent peut theoriquement appeler n'importe quel outil expose dans sa toolkit, meme si `allowed_mcps` le restreint dans le prompt (le LLM peut desobeir).
- Les resultats simules creent des faux positifs en test et en monitoring.
- Pas de timeout par outil MCP.
- Pas de quota d'invocation.
- Pas de journal d'invocation MCP exploitable.

**Recommandations** :
1. Consolider les 3 mappings MCP en un seul registre.
2. Ajouter un enforcement deterministe de `allowed_mcps` dans l'executor (pas seulement dans le prompt).
3. Ajouter timeout, retry, circuit breaker sur les invocations MCP.
4. Supprimer les outils simules du code de production.
5. Logger chaque invocation MCP avec input/output/duration/status.

### 5.6 Security

**Constats CRITIQUES** :

| Risque | Severite | Detail |
|--------|----------|--------|
| Zero authentification | CRITIQUE | Aucun middleware auth, aucun check sur aucun endpoint |
| Secrets en clair | CRITIQUE | `PlatformSecret.value` est un `Text` non chiffre |
| CORS permissif | ELEVE | `allow_methods=["*"]`, `allow_headers=["*"]` |
| Endpoints secrets ouverts | CRITIQUE | `GET/PUT/DELETE /api/settings/secrets` sans auth |
| Test Lab config injectable | ELEVE | `PUT /api/test-lab/config` ecrit du JSON arbitraire sans validation |
| Path traversal potentiel | MOYEN | `/api/debug-strategy/{filename}` lit des fichiers -- check partiel seulement |
| Prompt injection | MOYEN | Pas de sanitization du user input avant injection dans les prompts LLM |
| MCP tooling non controle | ELEVE | L'agent LLM decide seul quels outils appeler -- pas d'enforcement deterministe |
| Docker socket monte | ELEVE | Obot a acces a `/var/run/docker.sock` -- container escape possible |
| Pas de rate limiting | MOYEN | Aucun rate limit sur aucun endpoint |
| SECRET_KEY hardcode | MOYEN | `orkestra-dev-secret-change-in-prod` dans docker-compose |
| Pas de tenant isolation | MOYEN | `tenant_id` existe sur Request/Case mais jamais enforced |

**Recommandations prioritaires** :
1. **Immediat** : Ajouter un middleware d'authentification (API key ou JWT).
2. **Immediat** : Chiffrer `PlatformSecret.value` avec Fernet.
3. **Immediat** : Restreindre CORS aux origines specifiques.
4. **Court terme** : Ajouter rate limiting (ex: slowapi).
5. **Court terme** : Valider et sanitizer tous les inputs avant injection dans les prompts.
6. **Court terme** : Retirer le mount Docker socket de l'Obot ou isoler le container.
7. **Moyen terme** : Implementer RBAC avec separation design-time/runtime/admin.

### 5.7 Performance / Scalability

**Bottlenecks identifies** :

| Bottleneck | Impact | Localisation |
|------------|--------|-------------|
| N+1 queries agent listing | Latence lineaire avec le nombre d'agents | `enrich_agent()` x N dans `list_agents` |
| N+1 queries skill listing | Idem | `_get_allowed_families()` par skill |
| In-memory filtering | Charge RAM proportionnelle a la taille du dataset | `agent_registry_service.list_agents` text search, MCP filter |
| Engine creation par event | 15+ engines SQLAlchemy par test run | `test_lab/orchestrator.emit()` |
| Pas de pagination | Toutes les listes retournent TOUT | Tous les endpoints list_* |
| Pas de cache | Chaque requete refetch tout | Surtout `obot_catalog_service` qui appelle l'API externe |
| MCP health/usage en memoire | Charge toutes les invocations en RAM | `mcp_registry_service.get_mcp_health/usage` |
| Frontend re-fetch complet | Pas de SWR/React Query | Chaque navigation re-charge tout |

**Recommandations** :
1. Ajouter `selectinload` sur les relations Agent->Skills, Agent->Family.
2. Implementer la pagination (offset/limit avec total count) sur tous les endpoints de listing.
3. Deplacer le text search en DB (pg_trgm ou LIKE).
4. Creer un engine SQLAlchemy partage dans le Celery worker.
5. Ajouter Redis cache pour le catalogue Obot (TTL 5min).
6. Utiliser des aggregations SQL pour health/usage MCP.

### 5.8 Observability / Auditability

**Constats** :
- OTEL Collector configure : traces vers Tempo, metriques vers Prometheus.
- Prometheus client integre (`prometheus-client`) avec metriques custom.
- Grafana provisionne avec un dashboard `agent-test-lab.json`.
- `AuditEvent` avec `emit_event()` sur chaque mutation -- bon pattern d'event sourcing.
- `EvidenceRecord` et `ReplayBundle` modeles pour l'audit de runs.
- SSE streaming pour le Test Lab via Redis pub/sub.
- `structlog` declare comme dependance mais non configure visible (pas d'import visible dans les services principaux).
- Debug strategy tracer ecrit des JSON detailles sur disque.

**Manques** :
- Pas de correlation ID propage de bout en bout (request_id frontend -> API -> service -> DB -> Celery -> LLM).
- `structlog` declare mais pas integre dans les services -- les logs utilisent `print()` et `logging` standard.
- Pas de metriques business (agents crees/jour, tests runs/jour, MCP invocations/jour).
- Pas de trace de prompt complet (input prompt -> LLM response) persistee pour audit.
- Pas d'alerting configure.
- Le Grafana dashboard est unique (test-lab seulement) -- manque dashboards agents, MCPs, platform health.

**Recommandations** :
1. Ajouter un middleware FastAPI qui genere un `correlation_id` sur chaque requete et le propage.
2. Configurer structlog correctement avec JSON output.
3. Ajouter des metriques business Prometheus.
4. Persister les prompts complets et reponses LLM pour audit.
5. Creer des dashboards Grafana pour chaque domaine.
6. Configurer des alertes (test failures, MCP degradation, error rates).

### 5.9 Testing strategy

**Constats** :
- 22 fichiers de tests, ~2081 lignes total.
- Pytest + pytest-asyncio + httpx TestClient.
- `conftest.py` : SQLite in-memory pour les tests (divergence avec PostgreSQL en prod -- pas de JSONB, pas de lateral joins).
- Tests couvrent : agents CRUD, families CRUD, skills CRUD, MCPs CRUD, MCP catalog, state machines, orchestration, prompt builder, MCP validation, workflows, approvals, audit, control, supervision, settings.
- Pas de tests frontend (zero).
- Pas de tests d'integration avec LLM.
- Pas de tests du Test Lab orchestrator.
- Pas de tests E2E.

**Analyse de couverture** :

| Module | Tests | Couverture estimee |
|--------|-------|--------------------|
| Agent CRUD + registry | `test_api_agents.py`, `test_api_agent_registry_product.py` | Moyenne |
| Families CRUD | `test_api_families.py` | Bonne |
| Skills CRUD | `test_api_skills.py` | Bonne |
| MCP registry | `test_api_mcps.py` | Faible |
| MCP catalog | `test_api_mcp_catalog.py` | Moyenne |
| MCP validation | `test_mcp_validation.py` | Bonne |
| State machines | `test_state_machines.py` | Bonne |
| Prompt builder | `test_prompt_builder.py` | Bonne |
| Test Lab orchestrator | AUCUN | Zero |
| Test Lab assertions | AUCUN | Zero |
| Agent factory/execution | `test_executors.py` | Faible |
| Frontend | AUCUN | Zero |

**Risques** :
- SQLite vs PostgreSQL divergence : les tests passent mais le code peut echouer en prod (JSONB, lateral joins, etc.).
- Zero test sur le Test Lab -- le module le plus complexe n'est pas teste.
- Zero test frontend.

**Recommandations** :
1. Migrer les tests vers PostgreSQL (via testcontainers ou docker).
2. Ajouter des tests pour le Test Lab orchestrator.
3. Ajouter des tests frontend (Jest + React Testing Library).
4. Ajouter des tests d'integration LLM avec des mocks structures.

### 5.10 Product/UX consistency

**Constats** :
- Design system coherent visuellement (glassmorphism, palette cyber, typography JetBrains Mono).
- Les 5 modules forment un systeme de travail **partiellement connecte** :
  - Agent -> Family -> Skills : bien integre.
  - Agent -> Test Lab : deux systemes deconnectes.
  - Agent -> MCP : trois voies de resolution deconnectees.
  - MCP Catalog -> MCP Toolkit : parallel paths sans cross-linking.
- 9 liens sidebar morts.
- Mixed languages (FR stats dans agents, EN partout ailleurs).
- Dashboard Quick Actions pointent vers des pages inexistantes.
- "AI-powered" agent generation est en realite du keyword matching.

**Recommandations** :
1. Retirer les liens sidebar morts ou implementer les pages.
2. Unifier les deux Test Lab en un seul parcours.
3. Unifier les MCPs en un seul parcours catalogue + toolkit.
4. Standardiser la langue (tout EN ou tout FR).
5. Ne pas qualifier de "AI-powered" ce qui ne l'est pas.

---

## 6. Findings detailles

| ID | Gravite | Domaine | Finding | Pourquoi c'est un probleme | Preuve code | Recommandation |
|----|---------|---------|---------|----------------------------|-------------|----------------|
| F01 | Critique | DB | 6 tables Test Lab sans migrations | Crash garanti sur tout appel Test Lab scenario en prod | `test_scenarios`, `test_runs`, `test_run_events`, `test_run_assertions`, `test_run_diagnostics`, `agent_test_runs` absentes de `migrations/versions/` | Ecrire migration 010 |
| F02 | Critique | Securite | Zero authentification | Toute l'API est ouverte au monde | Aucun middleware auth dans `app/main.py` | Ajouter middleware auth API key/JWT |
| F03 | Critique | Securite | Secrets en clair | Cles API stockees sans chiffrement | `app/models/secret.py` : `value = Text` | Chiffrer avec Fernet |
| F04 | Critique | Securite | Endpoints secrets ouverts | N'importe qui peut lire/ecrire les secrets plateforme | `app/api/routes/settings.py` lignes 68-118 | Auth obligatoire sur ces endpoints |
| F05 | Elevee | Test Lab | Deux systemes de test paralleles incompatibles | Confusion utilisateur, maintenance doublee, vocabulaire incoherent (`pass` vs `passed`) | `agent_test_runs` vs `test_runs`, `mock-runner.ts` vs `orchestrator.py` | Consolider en un seul systeme |
| F06 | Elevee | Test Lab | Behavioral checks toujours `true` | Faux sentiment de qualite, qualification bidon | `mock-runner.ts` : `handlesAmbiguity: () => true` | Supprimer ou implementer reellement |
| F07 | Elevee | MCP | Fallback silencieux vers resultats simules | Masque les echecs, cree des faux positifs | `mcp_executor.py` L115 : `confidence: 0.85` hardcode | Supprimer le fallback, fail explicitement |
| F08 | Elevee | Frontend | Mock data masque les echecs backend | L'utilisateur ne peut pas distinguer reel de mock | `mcp/service.ts` : `catch () { return MOCK_MCPS }` | Afficher clairement les erreurs |
| F09 | Elevee | DB | Zero FK constraints entites operationnelles | Orphans, pas de CASCADE, pas d'integrite referentielle | `migrations/versions/001_initial_schema.py` : aucun FK | Ajouter FK constraints |
| F10 | Elevee | Backend | 220 lignes de business logic dans route handler | Violation separation of concerns, intestable | `app/api/routes/agents.py` lignes 238-461 | Extraire vers service |
| F11 | Elevee | Securite | Test Lab config injectable | JSON arbitraire ecrit sans validation | `app/api/routes/test_lab.py` `update_config` | Ajouter validation de schema |
| F12 | Elevee | Securite | Docker socket monte pour Obot | Container escape possible | `docker-compose.yml` : `/var/run/docker.sock` | Isoler Obot ou retirer le mount |
| F13 | Elevee | LLM | Pas de validation des sorties LLM | Le LLM peut desobeir aux forbidden effects sans detection | `agent_factory.py` : reponse texte libre | Ajouter validation post-LLM |
| F14 | Moyenne | DB | `Mapped[str]` sur colonnes DateTime | Type hints trompeurs pour IDE et type checkers | `run.py`, `invocation.py`, `approval.py` : 6+ occurrences | Corriger vers `Mapped[datetime]` |
| F15 | Moyenne | DB | ID prefix collision `evt_` | Confusion entre AuditEvent et TestRunEvent | `models/audit.py` et `models/test_lab.py` | Prefixes uniques |
| F16 | Moyenne | DB | `new_id()` 48 bits entropie | Collision probable a 16.7M records | `models/base.py` : `uuid4().hex[:12]` | Utiliser full UUID4 |
| F17 | Moyenne | Backend | Engine creation par event dans Celery | 15+ engines par test run, resource leak | `test_lab/orchestrator.py` L38-51 | Pool partage |
| F18 | Moyenne | Backend | Bug `msg_count` non defini | NameError a l'execution | `test_lab/orchestrator.py` L469 | Corriger la variable |
| F19 | Moyenne | Frontend | 9 liens sidebar morts | Navigation brisee, impression d'inachevement | `sidebar.tsx` : `/requests`, `/cases`, etc. | Retirer ou implementer |
| F20 | Moyenne | Frontend | Deux systemes de types paralleles | Types derive, maintenance doublee | `lib/types.ts` vs `lib/agent-registry/types.ts` | Consolider |
| F21 | Moyenne | Backend | Query dupliquee inutile | Performance gaspillee | `agent_registry_service.py` L126-128 | Supprimer la query morte |
| F22 | Moyenne | Frontend | `request<R>()` copie 5 fois | DRY violation | 5 fichiers service avec helper identique | Extraire vers `lib/api-client.ts` |
| F23 | Moyenne | Backend | Pas de pagination | Tous les list endpoints retournent tout | Tous les `list_*` dans routes/ | Ajouter offset/limit |
| F24 | Moyenne | Backend | N+1 queries agent listing | 3 queries/agent sur listing | `enrich_agent()` dans `list_agents` | `selectinload` |
| F25 | Moyenne | Performance | Pas de cache Obot | Chaque listing re-interroge l'API externe | `obot_catalog_service.list_catalog_items()` | Redis cache TTL 5min |
| F26 | Faible | DB | `AgentCreate` expose champs operationnels | Client peut setter `usage_count`, `last_test_status` | `schemas/agent.py` : `AgentCreate` | Retirer ces champs du create schema |
| F27 | Faible | DB | Status sans enum validation | N'importe quelle string acceptee pour status | `FamilyDefinition.status`, `SkillDefinition.status` | Ajouter enums et CheckConstraint |
| F28 | Faible | Backend | `generate-draft` ne fait pas d'appel LLM | Naming trompeur | `agent_generation_service.py` + `source="mock_llm"` | Renommer ou implementer |
| F29 | Faible | Frontend | StatCard defini 3 fois localement | Duplication malgre composant existant | Agents page, MCPs page, Toolkit page | Utiliser le composant UI partage |
| F30 | Faible | Frontend | Accessibilite absente | Non-conforme WCAG | Pas d'ARIA, pas de focus trapping, contraste insuffisant | Plan d'accessibilite dedic |
| F31 | Faible | Observability | structlog declare mais non configure | Logs non structures | `pyproject.toml` dependance sans configuration | Configurer structlog |

---

## 7. Gaps structurels majeurs

### Bloquants pour une plateforme serieuse

1. **Authentification / Autorisation** : Aucun systeme d'identite, de role, ou de permission. Impossible de distinguer un admin d'un utilisateur, un designer d'un operateur.

2. **Separation design-time / runtime / admin** : Pas de boundary entre "configurer un agent" et "executer un agent en production". Le meme endpoint sans auth fait les deux.

3. **Contrat de sortie LLM** : Les agents retournent du texte libre. Pas de schema JSON enforce, pas de validation post-generation, pas de rejet automatique en cas de non-conformite.

4. **Enforcement deterministe des MCPs** : Le controle d'acces aux outils repose uniquement sur le prompt (le LLM "devrait" respecter les forbidden effects). Pas de garde-fou cote executor.

5. **Multi-tenancy** : `tenant_id` existe sur 2 entites (Request, Case) mais n'est jamais enforce. Toutes les autres entites sont mono-tenant.

6. **Test reproductible** : Pas de notion de dataset de test fixe, de seed deterministe, de baseline regression. Les tests d'agents sont one-shot et non reproductibles.

7. **Cost tracking / Budget enforcement** : Les couts sont hardcodes (0.02 MCP, 0.5 agent). Pas de calcul reel, pas d'enforcement de budget en runtime.

8. **Rate limiting / Abuse prevention** : Aucune protection contre l'abus d'API.

9. **Prompt versioning** : Les prompts changent quand le code change. Pas de versionning independant, pas de A/B testing, pas de rollback de prompt.

10. **Agent-to-agent communication** : Pas de protocol de delegation ou de communication entre agents dans un workflow multi-agents. Chaque agent est un silo.

---

## 8. Plan de refactor priorise

### Phase 0 : Fixes critiques immediats (1-2 semaines)

| Action | Objectif | Impact | Complexite | Priorite | Dependances |
|--------|----------|--------|------------|----------|-------------|
| Migration Test Lab | 6 tables manquantes | Debloque tout le Test Lab scenario | Faible | P0 | Aucune |
| Middleware auth API key | Bloquer l'acces non-autorise | Securite fondamentale | Faible | P0 | Aucune |
| Chiffrement secrets | Proteger les cles API | Securite fondamentale | Faible | P0 | Aucune |
| Fix bug `msg_count` | Eviter NameError runtime | Stabilite | Trivial | P0 | Aucune |
| Supprimer fallbacks simules | Pas de faux positifs | Fiabilite | Faible | P0 | Aucune |
| Restreindre CORS | Reduire surface d'attaque | Securite | Trivial | P0 | Aucune |

### Phase 1 : Stabilisation architecture (4-6 semaines)

| Action | Objectif | Impact | Complexite | Priorite | Dependances |
|--------|----------|--------|------------|----------|-------------|
| Consolider Test Labs | Un seul systeme de test | Coherence produit | Elevee | P1 | Phase 0 |
| Ajouter FK constraints | Integrite referentielle | Fiabilite DB | Moyenne | P1 | Aucune |
| Pagination tous endpoints | Performance a l'echelle | Performance | Moyenne | P1 | Aucune |
| React Query / SWR | Cache et data management frontend | Performance UX | Moyenne | P1 | Aucune |
| Extraire `run_agent_test` vers service | Separation of concerns | Maintenabilite | Faible | P1 | Aucune |
| Consolider triple MCP mapping | Single source of truth outils | Architecture | Moyenne | P1 | Aucune |
| Corriger type hints DateTime | Type safety | Qualite code | Faible | P1 | Aucune |
| Selectinload relations | Eliminer N+1 | Performance | Faible | P1 | Aucune |
| Retirer liens sidebar morts | UX coherente | UX | Trivial | P1 | Aucune |

### Phase 2 : Industrialisation (8-12 semaines)

| Action | Objectif | Impact | Complexite | Priorite | Dependances |
|--------|----------|--------|------------|----------|-------------|
| RBAC + multi-tenancy | Separation design/runtime/admin | Securite, multi-user | Elevee | P2 | Phase 1 |
| Schema de sortie LLM + validation | Contrat agent respecte | Fiabilite agents | Elevee | P2 | Aucune |
| Enforcement deterministe MCPs | Controle reel des outils | Securite agents | Moyenne | P2 | Phase 1 |
| Prompt versioning | A/B testing, rollback prompts | Gouvernance LLM | Moyenne | P2 | Aucune |
| Rate limiting | Protection abus | Securite | Faible | P2 | Phase 0 auth |
| Tests PostgreSQL | Tests fiables prod-like | Qualite | Moyenne | P2 | Aucune |
| Tests frontend | Couverture UI | Qualite | Moyenne | P2 | Aucune |
| Structlog configuration | Logs structures JSON | Observabilite | Faible | P2 | Aucune |
| Correlation ID bout en bout | Tracabilite complete | Observabilite | Moyenne | P2 | Aucune |
| Cache Redis Obot | Performance catalogue | Performance | Faible | P2 | Aucune |
| Cost tracking reel | Budget enforcement | Gouvernance | Moyenne | P2 | Aucune |

### Phase 3 : Montee en capacite (12+ semaines)

| Action | Objectif | Impact | Complexite | Priorite | Dependances |
|--------|----------|--------|------------|----------|-------------|
| Agent-to-agent communication | Workflows multi-agents reels | Fonctionnalite core | Elevee | P3 | Phase 2 |
| Test datasets + regression baselines | Tests reproductibles | Qualite agents | Elevee | P3 | Phase 1 |
| Search index (pg_trgm/Elastic) | Recherche a l'echelle | Performance | Moyenne | P3 | Phase 2 |
| Dashboards Grafana complets | Operabilite | Observabilite | Moyenne | P3 | Phase 2 |
| Alerting | Detection incidents | Operabilite | Moyenne | P3 | Phase 2 |
| Webhooks / notifications | Integration externe | Extensibilite | Moyenne | P3 | Phase 2 |
| Accessibility WCAG AA | Conformite | UX | Moyenne | P3 | Phase 1 |

---

## 9. Cible architecture recommandee

### Boundaries claires

```
+---------------------------------------------------+
|                   UI Layer                         |
|  Next.js + React Query + Unified Type System      |
|  Single source of truth for types (generated       |
|  from OpenAPI spec)                                |
+---------------------------------------------------+
                         |
                    OpenAPI contract
                         |
+---------------------------------------------------+
|                  API Gateway                       |
|  Auth middleware + Rate limiting + Correlation ID   |
|  RBAC enforcement (design/runtime/admin roles)      |
+---------------------------------------------------+
          |                    |                |
+---------+------+   +---------+-----+   +-----+--------+
| Design Services|   | Runtime Engine|   | Admin Services|
| Agent Registry |   | Execution     |   | User Mgmt    |
| Family CRUD    |   | Orchestration |   | Settings     |
| Skill CRUD     |   | MCP Executor  |   | Audit        |
| MCP Catalog    |   | LLM Gateway   |   | Analytics    |
+----------------+   +---------------+   +--------------+
          |                    |                |
+---------+--------------------------------------------+
|              Shared Domain Layer                      |
|  State Machines | Event Bus | Validation Engine       |
|  Prompt Registry | Cost Tracker | Policy Engine        |
+------------------------------------------------------+
                         |
+------------------------------------------------------+
|              Data Layer                               |
|  PostgreSQL (entities) | Redis (cache, pubsub)        |
|  Prompt Store (versioned) | Audit Log (append-only)   |
+------------------------------------------------------+
                         |
+------------------------------------------------------+
|              External Integrations                    |
|  Obot (MCP source) | Ollama/OpenAI (LLM providers)  |
|  MCP Servers (remote tools)                           |
+------------------------------------------------------+
```

### Modele de donnees cible

- **Consolider `AgentTestRun` et `TestRun`** en un seul modele `TestRun` avec un champ `test_type` (quick/scenario).
- **Ajouter FK constraints** partout.
- **Ajouter `MCPDefinitionHistory`** pour l'audit MCP.
- **Ajouter `changed_by`** sur toutes les tables d'historique.
- **Ajouter `User`/`Role`/`Team`** entites pour RBAC.
- **Ajouter `PromptVersion`** entite pour le versioning des prompts.
- **Ajouter `CostRecord`** entite pour le tracking des couts.

### Separation design/runtime/test/catalog

| Domaine | Responsabilite | Acces |
|---------|---------------|-------|
| Design | Definition agents, familles, skills, prompts | Role: designer |
| Catalog | Enregistrement et gouvernance MCPs | Role: catalog_admin |
| Runtime | Execution agents, invocation MCPs | Role: operator |
| Test | Qualification agents, scenarios, assertions | Role: tester |
| Admin | Settings, secrets, users, audit | Role: admin |

### Gouvernance MCP

1. **Discovery** : Sync automatique depuis Obot + enregistrement manuel.
2. **Validation** : Gate automatique sur chaque transition de lifecycle (pas seulement manuelle).
3. **Allowlist enforcement** : L'executor filtre les outils disponibles dans la toolkit AVANT de les exposer a l'agent LLM (pas seulement via prompt).
4. **Observability** : Chaque invocation MCP loggee avec input/output/duration/cost/status.
5. **Quotas** : Budget d'invocation par agent par run (nombre d'appels et cout).
6. **Circuit breaker** : Desactivation automatique d'un MCP apres N echecs consecutifs.

### Strategie de validation des outputs LLM

1. **Schema JSON** : Chaque agent definit un `output_schema` JSON Schema.
2. **Validation post-generation** : Le runtime valide la sortie LLM contre le schema.
3. **Forbidden effects check** : Verification deterministe que la sortie ne contient pas d'actions interdites.
4. **Retry with constraint reinforcement** : En cas d'echec de validation, re-soumettre avec des contraintes renforcees (max 2 retries).
5. **Fallback reject** : Si la validation echoue apres retries, rejeter la sortie et logger l'incident.

### Strategie d'observabilite

1. **Correlation ID** : Genere au niveau API, propage a travers services, Celery, LLM calls.
2. **Structured logging** : structlog configure avec JSON output, correlation ID inclus.
3. **Traces** : OTEL traces pour chaque request, avec spans pour DB, LLM, MCP.
4. **Metriques business** : Agents crees/jour, tests/jour, pass rate, MCP invocations, cout total.
5. **Dashboards** : Un dashboard par domaine (Agents, Test Lab, MCPs, Platform Health).
6. **Alerting** : AlertManager configure pour test failure rate, error rate, latency, cost spikes.

### Strategie de securite

1. **AuthN** : JWT tokens avec refresh, ou API keys pour M2M.
2. **AuthZ** : RBAC avec roles (designer, tester, operator, admin) et scopes par ressource.
3. **Input validation** : Pydantic strict mode sur tous les schemas. Sanitization avant prompt injection.
4. **Secrets** : Fernet encryption pour les valeurs, rotation support.
5. **MCP scoping** : Allowlist enforcement cote executor + audit logging.
6. **Rate limiting** : Par endpoint, par user, par role.
7. **CORS** : Whitelist stricte d'origines.
8. **Network** : Obot dans un reseau isole, pas de Docker socket mount.

---

## 10. Production Readiness Scorecard

| Critere | Note /10 | Justification |
|---------|----------|---------------|
| Architecture | 6 | Separation propre frontend/backend/DB. Concepts de gouvernance bien penses. Couplage MCP triple et Test Lab dual problematiques. |
| Coherence produit/implementation | 4 | Ecarts importants : mock data masquant les echecs, behavioral checks bidon, liens morts, generate-draft sans LLM. |
| Qualite frontend | 5 | Design coherent, composants corrects, mais pas de state management, pas de types unifies, mock silencieux, accessibilite absente. |
| Qualite backend | 6 | Services bien structures, state machines robustes, event sourcing present. Route handler god function et fallbacks simules degradent. |
| Qualite DB | 4 | 6 tables sans migration, zero FK sur entites operationnelles, type hints incorrects, IDs collision-prone. Modele conceptuel bon. |
| Securite | 1 | Zero auth, secrets en clair, CORS ouvert, Docker socket monte, endpoints sensibles exposes. Critique. |
| LLM/Prompt discipline | 5 | Prompt builder 7 couches bien concu. Pas de schema de sortie, pas de validation post-LLM, pas de versioning. |
| Gouvernance MCP | 4 | Validation engine sophistiquee. Triple mapping, fallback simule, pas d'enforcement runtime, pas de quotas. |
| Performance | 4 | N+1 partout, pas de pagination, pas de cache, engine creation par event, filtering in-memory. |
| Observabilite | 4 | OTEL configure mais structlog non integre, pas de correlation ID, un seul dashboard, pas d'alerting. |
| Testabilite | 3 | 2081 lignes de tests (leger), SQLite vs PostgreSQL, zero test Test Lab, zero test frontend. |
| Maintenabilite | 5 | Code generalement lisible, modules bien decoupe. Dette technique dans Test Lab et MCP. Triple duplication MCP. |
| **Readiness production globale** | **3/10** | **Prototype avance. Fondations conceptuelles bonnes. Implementation insuffisante pour la production.** |

---

## 11. Verdict final

### Ce systeme est-il aujourd'hui un prototype, un MVP technique, ou une base production credible ?

**C'est un prototype avance en transition vers MVP technique.** La vision architecturale est mature (gouvernance par familles, skills composables, lifecycle agents, validation MCP multi-regles, Test Lab 5 phases). Mais l'implementation accumule trop de gaps critiques pour etre qualifiee de base production : zero securite, tables manquantes, mock data masquant les echecs, deux systemes de test paralleles incompatibles.

### Quelles parties peuvent etre conservees ?

1. **Modele de gouvernance familles/skills** : Bien pense, bien implemente, seed data de qualite.
2. **State machines** : Robustes, declaratives, completes pour tous les domaines.
3. **Prompt builder multi-couches** : Architecture de prompt elegante integrant toute la chaine de gouvernance.
4. **Service layer architecture** : Pattern sain de separation routes/services/models.
5. **Event sourcing via `emit_event()`** : Bon fondement d'auditabilite.
6. **MCP validation engine** : Sophistiquee et bien structuree.
7. **Test Lab scenariste (systeme 2)** : Concept 5 phases excellent, assertion engine et diagnostic engine bien implementes.
8. **Design system frontend** : Identite visuelle coherente et distinctive.

### Quelles parties doivent etre refaites ?

1. **Couche securite** : A creer from scratch (auth, RBAC, rate limiting, input sanitization).
2. **Agent Test Lab (systeme 1)** : Behavioral checks bidon a eliminer. Consolider avec le systeme 2.
3. **Resolution MCP** : Triple mapping a consolider en un seul registre.
4. **Fallbacks simules** : A supprimer partout (mcp_executor, subagent_executor, frontend mock).
5. **Frontend data management** : A remplacer par React Query/SWR avec types unifies.

### Quel module est le plus faible ?

**Test Lab (3/10)**. Deux systemes paralleles dont le meilleur n'a pas de migrations, des checks comportementaux bidon dans le systeme fonctionnel, un bug runtime, et zero couverture de tests. C'est pourtant le module le plus critique pour la qualite de la plateforme.

### Quel module est le plus prometteur ?

**Families + Skills (7/10)**. Le modele de gouvernance par familles avec des skills composables, des effets interdits, des regles systeme, et une cascade automatique est conceptuellement solide et relativement bien implemente. C'est le coeur de la proposition de valeur de la plateforme et il constitue une base solide pour l'industrialisation.

---

*Fin de l'audit. Document genere le 2026-04-07.*
