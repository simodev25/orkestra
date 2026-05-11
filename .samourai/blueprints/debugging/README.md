# Debugging Blueprint

## Role

This blueprint frames a reproducible technical investigation: symptom, hypotheses, observations, root cause, and proposed fix.

## When To Use

- To diagnose a bug or regression.
- To document a local or CI failure.
- Before changing code when the cause is not proven.

## Expected Files

- `debug.blueprint.yaml`: diagnostic contract.
- `debug-report.template.md`: fillable report.

## Minimal Example

```text
Produce a debug report for the failing auth.e2e.spec.ts test.
```
