# GitHub Actions

The repository includes four workflows.

## lint-and-test.yml

- Installs backend dependencies.
- Runs `ruff`.
- Runs backend tests.
- Installs portal dependencies.
- Runs portal lint.
- Builds the portal.
- Runs `npm audit --audit-level=moderate`.
- Performs basic secret-pattern checks.

## validate-examples.yml

- Validates every example request.
- Checks collection pinning through guardrails.
- Runs the compatibility advisor in dry-run mode.
- Runs the OSV vulnerability advisor.
- Runs `ansible-builder create` for all examples.

## build-example-ee.yml

Manual workflow.

Inputs:

- `ee`
- `tag`
- `registry_namespace`
- `push`

Default behavior builds locally in the GitHub runner with `push=false`.

When `push=true`, Quay secrets are required:

- `QUAY_USERNAME`
- `QUAY_PASSWORD`

## release.yml

Packages the project artifact. Future releases can add signed archives and optional published example images.
