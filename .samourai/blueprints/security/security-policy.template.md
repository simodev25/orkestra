# Security Policy: <scope>

## Scope

<scope>

## Sensitive Data

- Secrets, tokens, API keys, cookies, credentials.
- Personal or contractual data.
- Logs containing sensitive information.

## Agent Rules

- Never read, display, store, or copy secrets.
- Mask any sensitive value observed accidentally.
- Ask for approval before GitHub, Jira, CI/CD, publishing, or deployment.
- Ask for approval before deletion, reset, overwrite, merge, or rebase.

## Sensitive Actions

| Action | Approval Required | Notes |
| --- | --- | --- |
| <action> | yes | <notes> |

## Verification

```bash
<security_check_command>
```

## Escalation

Contact: <owner_or_team>
