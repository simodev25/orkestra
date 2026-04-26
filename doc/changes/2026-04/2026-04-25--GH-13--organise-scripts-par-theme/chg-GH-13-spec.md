---
change:
  ref: GH-13
  type: chore
  status: Proposed
  slug: organise-scripts-par-theme
  title: "Réorganiser le dossier scripts/ en sous-dossiers thématiques"
  owners: [mbensass]
  service: developer-experience
  labels: [scripts, dx, organisation]
  version_impact: none
  audience: internal
  security_impact: none
  risk_level: low
  dependencies:
    internal: [scripts/]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** — Ce document est l'artefact de référence pour le changement `GH-13`.
> Il décrit le **quoi** et le **pourquoi** sans prescrire le **comment** technique.
> Il est la source de vérité pour `@plan-writer`, `@coder`, `@reviewer` et `@doc-syncer`.

---

## 1. SUMMARY

Le dossier `scripts/` d'Orkestra Mesh contient 13 fichiers à plat couvrant des usages très
différents (provisioning d'agents, seed Test Lab, infrastructure Obot, développement AgentScope).
Cette absence de structure nuit à la lisibilité et à la maintenabilité du projet.

Ce changement réorganise `scripts/` en quatre sous-dossiers thématiques (`agents/`, `testlab/`,
`infra/`, `dev/`) et ajoute un `README.md` décrivant l'organisation et l'usage de chaque thème.
Le contenu des scripts existants **ne sera pas modifié**.

---

## 2. CONTEXT

### 2.1 Current State Snapshot

- `scripts/` contient 13 fichiers à plat sans aucune hiérarchie.
- Les scripts couvrent quatre domaines distincts sans séparation visuelle :
  - **Provisioning d'agents** : 8 scripts `create_*_agent.py` / `create_*_orchestrator.py`
  - **Seed Test Lab** : 1 script `create_test_lab_tables.py`
  - **Infrastructure Obot MCP** : 1 script shell `seed_obot_mcp_servers.sh`
  - **Développement / debug AgentScope** : 3 scripts `orchestrateur_*.py`
- Aucun fichier `README.md` ou documentation d'usage n'existe dans ce dossier.

### 2.2 Pain Points / Gaps

- **Découvrabilité** : un développeur ne peut pas identifier rapidement quel script correspond à
  son besoin sans lire les noms de fichiers un par un.
- **Maintenabilité** : l'ajout de nouveaux scripts aggrave l'encombrement à plat.
- **Onboarding** : les nouveaux contributeurs n'ont aucun repère contextuel sur le rôle de chaque
  script.
- **Absence de documentation** : aucun README n'indique comment et quand utiliser ces scripts.

---

## 3. PROBLEM STATEMENT

L'organisation actuelle de `scripts/` est plate et non structurée, ce qui ralentit la
découverte, la maintenance et l'onboarding des contributeurs. Le projet a besoin d'une
organisation thématique claire, documentée, et cohérente avec la croissance attendue du nombre
de scripts.

---

## 4. GOALS

| # | Objectif |
|---|----------|
| G-1 | Regrouper les scripts en sous-dossiers reflétant leur domaine fonctionnel. |
| G-2 | Fournir une documentation minimale (README) décrivant chaque thème et son usage. |
| G-3 | Garantir qu'aucun script existant n'est modifié dans son contenu. |
| G-4 | Maintenir la cohérence avec les conventions de nommage du projet. |

### 4.1 Success Metrics / KPIs

| Métrique | Cible |
|----------|-------|
| Nombre de sous-dossiers thématiques créés | 4 (`agents/`, `testlab/`, `infra/`, `dev/`) |
| Scripts migrés sans modification de contenu | 13/13 (100 %) |
| Présence d'un `README.md` dans `scripts/` | Oui |
| Temps moyen pour trouver un script par domaine (estimation qualitative) | Réduit de façon perceptible |

### 4.2 Non-Goals

- [OUT] Modifier le contenu ou le comportement des scripts existants.
- [OUT] Créer des fichiers `__init__.py` (les scripts ne sont pas des modules Python importables).
- [OUT] Automatiser l'exécution de ces scripts (CI/CD, Makefile, etc.).
- [OUT] Ajouter de nouveaux scripts dans le cadre de ce changement.
- [OUT] Modifier les imports ou références internes à d'autres parties du projet.

---

## 5. FUNCTIONAL CAPABILITIES

| ID | Capacité | Rationale |
|----|----------|-----------|
| F-1 | Sous-dossier `agents/` regroupant les scripts de provisioning d'agents dans le registry | Séparer les scripts de création d'agents des autres usages |
| F-2 | Sous-dossier `testlab/` regroupant les scripts de seed du Test Lab | Isoler les scripts de setup de l'environnement de test |
| F-3 | Sous-dossier `infra/` regroupant les scripts de seed de l'infrastructure Obot MCP | Isoler les scripts d'infrastructure des scripts applicatifs |
| F-4 | Sous-dossier `dev/` regroupant les scripts de développement et debug AgentScope | Marquer explicitement les scripts non-productifs comme outils de développement |
| F-5 | `README.md` à la racine de `scripts/` décrivant chaque thème, son périmètre et son usage | Documenter l'organisation pour les contributeurs actuels et futurs |

### 5.1 Capability Details

**F-1 — Sous-dossier `agents/`**
Contient les 8 scripts de provisioning d'agents dans le registry Orkestra Mesh :
`create_budget_fit_agent.py`, `create_hotel_pipeline_orchestrator.py`,
`create_identity_agent.py`, `create_legal_registry_agent.py`, `create_mobility_agent.py`,
`create_stay_discovery_agent.py`, `create_weather_agent.py`, `create_word_test_agent.py`.

**F-2 — Sous-dossier `testlab/`**
Contient le script de création des tables du Test Lab : `create_test_lab_tables.py`.

**F-3 — Sous-dossier `infra/`**
Contient le script shell de seed des serveurs Obot MCP : `seed_obot_mcp_servers.sh`.

**F-4 — Sous-dossier `dev/`**
Contient les 3 scripts de développement/debug AgentScope : `orchestrateur_chat.py`,
`orchestrateur_test_conversation.py`, `orchestrateur_test.py`.

**F-5 — `README.md` racine de `scripts/`**
Doit couvrir a minima : description de chaque thème, liste des scripts par thème,
instructions d'usage génériques (prérequis, exécution).

---

## 6. USER & SYSTEM FLOWS

### Flux : Développeur cherche un script de provisioning

```
Développeur ouvre scripts/
  → voit les sous-dossiers thématiques
  → entre dans agents/
  → identifie le script par nom
  → exécute le script
```

### Flux : Nouveau contributeur découvre l'organisation

```
Contributeur clone le repo
  → lit scripts/README.md
  → comprend les 4 thèmes et leur périmètre
  → sait où créer un nouveau script selon son domaine
```

---

## 7. SCOPE & BOUNDARIES

### 7.1 In Scope

- Création des sous-dossiers `agents/`, `testlab/`, `infra/`, `dev/` sous `scripts/`.
- Déplacement des 13 scripts existants vers le sous-dossier approprié.
- Création de `scripts/README.md`.
- Mise à jour de toute référence documentaire au chemin des scripts si elle existe dans `doc/`.

### 7.2 Out of Scope

- [OUT] Modification du contenu des scripts (logique, imports, variables).
- [OUT] Création de `__init__.py` ou transformation en packages Python.
- [OUT] Ajout de nouveaux scripts.
- [OUT] Intégration CI/CD ou Makefile.
- [OUT] Modification des tests existants (sauf si un test référençait un chemin exact de script).

### 7.3 Deferred / Maybe-Later

- Ajout d'un `README.md` par sous-dossier (peut être ajouté dans un futur changement).
- Validation automatisée de la structure via un test ou lint de convention.

---

## 8. INTERFACES & INTEGRATION CONTRACTS

### 8.1 REST / HTTP Endpoints

_Sans objet — ce changement ne touche aucune API._

### 8.2 Events / Messages

_Sans objet._

### 8.3 Data Model Impact

_Sans objet — aucun modèle de données n'est affecté._

### 8.4 External Integrations

_Sans objet._

### 8.5 Backward Compatibility

Les scripts sont des outils manuels exécutés en local ; il n'y a pas de dépendance
d'importation depuis le code applicatif. Aucun risque de breaking change sur l'API ou les
modèles. Les contributeurs devront mettre à jour leurs raccourcis/alias locaux si nécessaire.

Si des références aux anciens chemins existent dans `doc/`, elles seront mises à jour dans le
périmètre de ce changement (voir 7.1).

---

## 9. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| ID | Exigence | Seuil mesurable |
|----|----------|-----------------|
| NFR-1 | **Complétude** : 100 % des scripts existants doivent être présents après migration | 13/13 scripts présents dans la nouvelle structure |
| NFR-2 | **Intégrité** : aucun fichier script ne doit être modifié dans son contenu | Diff de contenu nul entre avant et après migration pour chaque script |
| NFR-3 | **Documentation** : le `README.md` doit couvrir les 4 thèmes avec au moins 1 exemple d'usage | README présent, ≥ 4 sections thématiques, ≥ 1 exemple par thème |
| NFR-4 | **Conformité de nommage** : les sous-dossiers respectent les conventions kebab-case du projet | Vérification manuelle avant merge |

---

## 10. TELEMETRY & OBSERVABILITY REQUIREMENTS

_Sans objet — ce changement est purement organisationnel et ne génère pas de métriques runtime._

---

## 11. RISKS & MITIGATIONS

| ID | Risque | Impact | Probabilité | Mitigation | Risque résiduel |
|----|--------|--------|-------------|------------|-----------------|
| RSK-1 | Un script référencé dans la doc avec son ancien chemin devient introuvable | M | M | Rechercher toutes les occurrences des anciens chemins dans `doc/` avant merge | Faible |
| RSK-2 | Un contributeur a un alias/script local qui pointe vers l'ancien chemin | L | L | Mentionner la migration dans le message de PR | Négligeable |
| RSK-3 | Un test intégration référence un chemin exact de script | M | L | Vérifier les tests avant merge | Faible |

---

## 12. ASSUMPTIONS

- Les scripts ne sont pas importés comme modules Python depuis le code applicatif.
- Aucun pipeline CI/CD ne référence directement un script par son chemin actuel.
- Les contributeurs ont accès à `git mv` ou équivalent pour préserver l'historique git.
- La structure cible en 4 thèmes couvre exhaustivement les 13 scripts actuels.

---

## 13. DEPENDENCIES

| Type | Dépendance | Nature |
|------|-----------|--------|
| Interne | `scripts/` (état actuel) | Source de la migration |
| Interne | `doc/` (références éventuelles) | Mise à jour des chemins si nécessaire |

---

## 14. OPEN QUESTIONS

| ID | Question | Assigné à | Statut |
|----|----------|-----------|--------|
| OQ-1 | Existe-t-il des références aux scripts dans les fichiers de configuration (ex. Makefile, `.github/workflows/`) ? | @mbensass | Ouvert |
| OQ-2 | Le `README.md` doit-il inclure des instructions de prérequis (virtualenv, variables d'env) ? | @mbensass | Ouvert |

---

## 15. DECISION LOG

| ID | Décision | Rationale | Date |
|----|----------|-----------|------|
| DEC-1 | Ne pas créer de `__init__.py` | Ces scripts sont des outils CLI, pas des modules importables | 2026-04-25 |
| DEC-2 | 4 thèmes : `agents/`, `testlab/`, `infra/`, `dev/` | Reflète les 4 domaines d'usage identifiés dans le backlog | 2026-04-25 |
| DEC-3 | Un seul `README.md` à la racine de `scripts/` | Sufficient pour la V1 ; les README par sous-dossier sont déférés | 2026-04-25 |

---

## 16. AFFECTED COMPONENTS (HIGH-LEVEL)

| Composant | Nature de l'impact |
|-----------|-------------------|
| `scripts/` | Réorganisation structurelle complète |
| `doc/` | Mise à jour des références de chemins si présentes |

---

## 17. ACCEPTANCE CRITERIA

| ID | Critère | Lié à |
|----|---------|-------|
| AC-F1-1 | **Given** le dépôt après migration, **when** on liste `scripts/agents/`, **then** les 8 scripts de provisioning d'agents sont présents et leur contenu est identique à l'original | F-1, NFR-1, NFR-2 |
| AC-F2-1 | **Given** le dépôt après migration, **when** on liste `scripts/testlab/`, **then** `create_test_lab_tables.py` est présent et son contenu est identique à l'original | F-2, NFR-1, NFR-2 |
| AC-F3-1 | **Given** le dépôt après migration, **when** on liste `scripts/infra/`, **then** `seed_obot_mcp_servers.sh` est présent et son contenu est identique à l'original | F-3, NFR-1, NFR-2 |
| AC-F4-1 | **Given** le dépôt après migration, **when** on liste `scripts/dev/`, **then** les 3 scripts `orchestrateur_*.py` sont présents et leur contenu est identique à l'original | F-4, NFR-1, NFR-2 |
| AC-F5-1 | **Given** le dépôt après migration, **when** on ouvre `scripts/README.md`, **then** le fichier existe et contient une section pour chacun des 4 thèmes avec au moins un exemple d'usage | F-5, NFR-3 |
| AC-F5-2 | **Given** le dépôt après migration, **when** on compte les scripts présents dans tous les sous-dossiers, **then** le total est exactement 13 (aucun script perdu, aucun doublon) | F-1, F-2, F-3, F-4, NFR-1 |
| AC-NFR4-1 | **Given** la nouvelle structure, **when** on vérifie les noms des sous-dossiers, **then** ils respectent le kebab-case et les conventions de nommage du projet | NFR-4 |

---

## 18. ROLLOUT & CHANGE MANAGEMENT (HIGH-LEVEL)

- **Stratégie** : migration one-shot sur une branche dédiée, PR unique.
- **Rollback** : revert de la PR suffit à restaurer l'état précédent (historique git préservé via `git mv`).
- **Communication** : mention dans le message de PR pour avertir les contributeurs de mettre à jour leurs alias locaux.
- **Fenêtre** : aucune contrainte de déploiement (pas d'impact runtime).

---

## 19. DATA MIGRATION / SEEDING (IF APPLICABLE)

_Sans objet._

---

## 20. PRIVACY / COMPLIANCE REVIEW

_Sans objet — ce changement ne traite aucune donnée personnelle ou confidentielle._

---

## 21. SECURITY REVIEW HIGHLIGHTS

_Sans objet — aucun changement de logique, d'accès ou de permission._

---

## 22. MAINTENANCE & OPERATIONS IMPACT

- Les contributeurs ajoutant de nouveaux scripts devront respecter la structure thématique établie.
- La convention de placement devra être documentée dans les guidelines de contribution du projet (hors périmètre de ce changement).

---

## 23. GLOSSARY

| Terme | Définition |
|-------|-----------|
| Script de provisioning | Script créant ou configurant un agent dans le registry Orkestra Mesh |
| Test Lab | Environnement de test isolé d'Orkestra Mesh pour l'évaluation des agents |
| Obot MCP | Serveurs Multi-Channel Protocol gérés par la couche Obot d'Orkestra |
| AgentScope | Framework sous-jacent utilisé pour l'orchestration des agents |
| Sous-dossier thématique | Répertoire regroupant des scripts selon leur domaine fonctionnel |

---

## 24. APPENDICES

### Annexe A — Mapping complet des scripts (avant → après)

| Script (état actuel) | Destination |
|----------------------|-------------|
| `create_budget_fit_agent.py` | `agents/` |
| `create_hotel_pipeline_orchestrator.py` | `agents/` |
| `create_identity_agent.py` | `agents/` |
| `create_legal_registry_agent.py` | `agents/` |
| `create_mobility_agent.py` | `agents/` |
| `create_stay_discovery_agent.py` | `agents/` |
| `create_weather_agent.py` | `agents/` |
| `create_word_test_agent.py` | `agents/` |
| `create_test_lab_tables.py` | `testlab/` |
| `seed_obot_mcp_servers.sh` | `infra/` |
| `orchestrateur_chat.py` | `dev/` |
| `orchestrateur_test_conversation.py` | `dev/` |
| `orchestrateur_test.py` | `dev/` |

---

## 25. DOCUMENT HISTORY

| Version | Date | Auteur | Description |
|---------|------|--------|-------------|
| 0.1 | 2026-04-25 | @mbensass | Création initiale — statut Proposed |

---

## AUTHORING GUIDELINES

- Utiliser les IDs stables (`F-`, `AC-`, `NFR-`, `RSK-`, `OQ-`, `DEC-`) pour toute référence croisée.
- Les Acceptance Criteria suivent le format **Given / When / Then** et référencent au moins un ID.
- Les NFRs incluent un seuil mesurable.
- Les risques incluent Impact et Probabilité (H/M/L).
- Ne jamais inclure de chemins de fichiers source, tâches d'implémentation ou instructions git dans ce document.

## VALIDATION CHECKLIST

- [x] `change.ref` == `GH-13`
- [x] `owners` ≥ 1 entrée
- [x] `status` == "Proposed"
- [x] Ordre des sections exact selon `<spec_structure>`
- [x] Tous les IDs sont uniques dans leur catégorie
- [x] Chaque AC référence au moins un ID fonctionnel ou NFR
- [x] NFRs incluent des seuils mesurables
- [x] Risques incluent Impact & Probabilité
- [x] Aucun chemin de fichier source ni tâche d'implémentation dans le document
- [x] Non-goals marqués `[OUT]`
