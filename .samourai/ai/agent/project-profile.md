# Project Profile — Orkestra

## Mode : Build — Développement de features actives

Orkestra est un projet nouveau et actif. L'objectif principal est la livraison régulière de nouvelles fonctionnalités sur la plateforme de registry et test lab d'agents IA. Pas de phase de maintenance lourde actuellement.

## Comportements (tous les agents)

- **Spec avant code** : ne jamais commencer à implémenter sans une spec validée et un plan.
- **Couverture de tests** : toute nouvelle feature doit avoir des tests correspondants avant que la PR soit mergée.
- **Compatibilité backward** : signaler explicitement tout breaking change dans la spec et la description de PR.
- **Livraison incrémentale** : préférer des petites PRs reviewables aux gros monolithes.
- **Backlog discipliné** : `@pm` s'assure qu'aucun ticket n'entre en livraison sans critères d'acceptance et scope clair.

## Impact par agent

- **Planning** : découper le travail en petites phases livrables avec des critères d'acceptance clairs. Pas de ticket > 3 jours estimés sans découpage.
- **Développement** : implémenter des tranches de features propres avec tests et vérifications de compatibilité backward.
- **Corrections** : corriger le feedback de review en préservant l'intent de la feature et la vélocité de livraison.
- **Review** : mettre l'accent sur la justesse, la couverture de tests, la compatibilité API, et la readiness release.
- **Reporting** : présenter la capacité livrée, les fichiers affectés, les validations effectuées, et le travail de suivi.

---

## Modificateur : Complexité Élevée

Ce projet est classé **complexité élevée** (systèmes distribués, orchestration multi-agents IA, intégrations MCP/Obot, évaluation LLM non-déterministe).

- `@architect` doit être consulté avant tout changement touchant les frontières de sous-systèmes, les modèles de données, ou les APIs.
- `@plan-writer` doit découper les tâches en sous-tâches d'effort maximal estimé 2h.
- Aucun changement ne peut toucher plus de 3 fichiers dans un seul commit sans approbation humaine explicite.
- Les rapports doivent signaler le risque architectural et les preuves de validation utilisées.

---

## Modificateur : Projet Solo

Ce projet est développé par **une seule personne**.

- Les gates de review obligatoires sont allégées — `@reviewer` s'exécute mais un FAIL ne bloque pas le merge (mode advisory).
- Privilégier les petits commits fréquents plutôt que les batchs (plus facile à reverter).
- Les rapports doivent être concis et se concentrer sur ce qui doit être vérifié ensuite.

---

## Contexte domaine Orkestra (tous les agents)

- **"agent"** dans ce repo = un enregistrement `AgentDefinition` en base de données — PAS un agent OpenCode.
- **"skill"** dans ce repo = un bloc de prompt Orkestra injecté dans les agents — PAS un skill OpenCode.
- **"mcp"** = peut désigner le protocole MCP (outils externes) OU le catalog Obot — contexte déterminant.
- **"lifecycle"** = la machine à états `draft → designed → tested → registered → active → deprecated → archived` d'un agent Orkestra — PAS un cycle CI/CD.

## Zones critiques — protection obligatoire

- `app/state_machines/` — NE JAMAIS bypasser les transitions lifecycle sans confirmation humaine.
- `app/services/audit_service.py` — table append-only. NE JAMAIS modifier/supprimer des entrées.
- `app/services/secret_service.py` — NE JAMAIS logger des secrets. NE JAMAIS stocker en clair.
- `app/models/` — tout changement de schéma = nouvelle migration Alembic obligatoire.
- `app/services/effect_classifier.py` — logique de gouvernance. Modification = risque de contournement des contrôles de sécurité.
