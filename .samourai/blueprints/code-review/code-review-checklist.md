# Code Review Checklist

## Correctness

- [ ] The change satisfies acceptance criteria.
- [ ] Edge cases are handled.
- [ ] Errors are handled explicitly.

## Tests

- [ ] Tests cover the happy path.
- [ ] Tests cover at least one relevant error path.
- [ ] Verification commands are documented.

## Security

- [ ] No secret, token, or credential is added.
- [ ] User input is validated.
- [ ] Logs do not expose sensitive information.

## Maintainability

- [ ] The change is scoped.
- [ ] Names are explicit.
- [ ] Useful documentation is updated.

## Decision

```text
Decision: approve | request_changes | comment
Risks:
Tests verified:
Remaining actions:
```
