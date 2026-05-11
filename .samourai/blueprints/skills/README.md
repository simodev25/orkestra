# Skills Blueprint

## Role

This blueprint describes how to create a reusable skill focused on one precise operational practice.

## When To Use

- To capture project expertise.
- To guide an agent through a recurring method.
- To create a skill under `.opencode/skills/project/`.

Skills are not slash commands. Do not generate `.opencode/command/**` files from
this blueprint, and do not document a skill as invokable with `/<skill-name>`.

## Expected Files

- `skill.blueprint.yaml`: generation contract.
- `skill.template.md`: `SKILL.md` structure.

## Minimal Example

```text
Create a "db-migration" skill for SQL migrations and rollback tests.
```
