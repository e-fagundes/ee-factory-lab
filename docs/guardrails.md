# Guardrails

Guardrails are deterministic and live in backend services, not in the portal and not in the LLM.

## Implemented Rules

1. EE name must follow a safe lowercase naming convention.
2. Image tag must be valid.
3. Collections must be pinned by default.
4. Base image must be in the allowed RPM-based list unless custom base image mode is justified.
5. Custom base image mode emits a warning.
6. Automation domain is required.
7. Known collections are mapped to domain taxonomy.
8. Disconnected domain mixing is blocked unless justified.
9. Python dependencies must parse as safe requirement syntax.
10. System dependencies are allowlisted or warned.
11. Secret-like dependency values are blocked.
12. Registry credentials are not accepted in generated files.
13. Build commands are fixed command lists, not user-interpolated shell strings.
14. Risky overrides require justification.

## Configuration

- `config/domain-taxonomy.yml`
- `config/allowed-base-images.yml`
- `config/guardrails.yml`

The starter taxonomy includes infrastructure, cloud, network, security, observability, and database domains. For example,
`community.postgresql` maps to the `database` domain so PostgreSQL administration EEs can pass domain governance without
being treated as unmapped custom scope.

## Severity

- `BLOCKER`: request cannot generate files.
- `WARNING`: request can continue but needs review.
- `INFO`: context for the reviewer.
