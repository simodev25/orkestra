# PR Instructions — Orkestra

> Ce fichier configure comment les agents interagissent avec la plateforme PR/MR.
> La langue de travail est le **français**.

---

## Plateforme

| Paramètre | Valeur |
|-----------|--------|
| Plateforme | GitHub |
| Instance | Cloud (`github.com`) |
| Dépôt | `simodev25/orkestra` |
| Méthode d'accès | `gh` CLI (authentifié, compte `simodev25`) |
| Branche principale | `main` |

---

## Référence des Opérations

| Opération | Commande `gh` |
|-----------|--------------|
| Créer une PR | `gh pr create --title "..." --body "..." --base main` |
| Voir les PRs ouvertes | `gh pr list --repo simodev25/orkestra` |
| Voir le statut d'une PR | `gh pr view <numéro>` |
| Ajouter un label | `gh pr edit <numéro> --add-label "review"` |
| Lire les commentaires | `gh pr view <numéro> --comments` |
| Fermer une PR | `gh pr close <numéro>` *(humain uniquement)* |
| Merger une PR | `gh pr merge <numéro>` *(humain uniquement — jamais automatisé)* |

---

## Format du Titre de PR

```
<type>(<scope>): <description courte>
```

Exemples :
- `feat(registry): add agent versioning support`
- `fix(test-lab): correct scoring aggregation for multi-step scenarios`
- `refactor(prompt-builder): extract layer assembly to dedicated service`

Types valides : `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `build`, `ci`

---

## Template de Description PR

```markdown
## Contexte

<!-- Lien vers l'issue GitHub : Closes #<numéro> -->
<!-- Résumé en 1-2 phrases du problème résolu ou de la feature livrée -->

## Changements

<!-- 3-5 bullets décrivant les modifications principales -->
- 
- 
- 

## Tests

<!-- Quels tests ont été exécutés ? Quelle est l'évidence de passage ? -->
- [ ] `pytest tests/ -v` — tous les tests passent
- [ ] `ruff check app/` — pas d'erreurs lint
- [ ] Migration Alembic appliquée (si schéma modifié)

## Risques & Notes

<!-- Breaking changes, dépendances, points d'attention pour le reviewer -->

## Checklist

- [ ] Spec et plan à jour dans `.samourai/docai/changes/`
- [ ] Tests couvrent les critères d'acceptance
- [ ] Aucun secret exposé dans le diff
- [ ] Pas de migration Alembic manquante
```

---

## Règles Spécifiques Orkestra

- **Jamais merger automatiquement** — le merge est toujours manuel (`simodev25`).
- Si la PR touche `app/state_machines/` : mentionner explicitement dans la description les transitions lifecycle affectées.
- Si la PR touche `app/models/` : confirmer que la migration Alembic correspondante est incluse dans le diff.
- Si la PR touche l'API REST (`app/api/routes/`) : vérifier la compatibilité avec le frontend Next.js.
- Si la PR modifie `app/services/audit_service.py` ou `app/services/secret_service.py` : escalader vers une review humaine attentive.

---

## Convention de Branche

Format : `<type>/GH-<numéro>/<slug>`

Exemples :
- `feat/GH-12/agent-versioning`
- `fix/GH-23/test-lab-scoring`
- `refactor/GH-7/prompt-builder-cleanup`

La branche est créée depuis `main` et mergée dans `main`.

---

## Politique de Langue

Tous les messages, titres de PR, et descriptions générés par les agents doivent être **en français**.
Exception : les noms de commits et titres de PR suivent le format Conventional Commits en anglais
(convention technique universelle — ex: `feat(registry): add versioning`).
