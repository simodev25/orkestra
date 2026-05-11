# Agents Blueprint

## Role

This blueprint standardizes agent creation: objective, triggers, permissions, allowed tools, inputs, outputs, and limits.

## When To Use

- To add a new agent under `.opencode/agent/`.
- To adapt an agent for VS Code or another environment.
- To document which sensitive actions are allowed.

## Expected Files

- `agent.blueprint.yaml`: agent generation contract.
- `agent.template.md`: Markdown agent skeleton.

## Minimal Example

```text
Create a release-manager agent with read, search, edit, and shell_readonly tools.
It must never push or merge without human approval.
```
