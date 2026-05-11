# Project Bootstrap Blueprint

## Role

This blueprint initializes a project with baseline Samourai instructions: project context, agent conventions, documentation references, and security guardrails.

## When To Use

- When onboarding an existing repository.
- After installing the kit into a new target project.
- When `.samourai/AGENTS.md` must be created or realigned.

## Expected Files

- `project-bootstrap.blueprint.yaml`: generation contract.
- `AGENTS.template.md`: project-instructions template.

## Minimal Example

```text
Generate .samourai/AGENTS.md for a Node.js API using
blueprints/project-bootstrap/project-bootstrap.blueprint.yaml.
```
