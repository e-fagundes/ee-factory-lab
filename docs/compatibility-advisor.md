# Compatibility Advisor

The Collection Compatibility Advisor helps users avoid broad, fragile Execution Environments.

It does not claim to perfectly solve all dependency conflicts.

## Inputs

- Declared automation domain.
- Selected collections and pinned versions.
- Python dependencies.
- System dependencies.
- Guardrail findings.
- Domain taxonomy from `config/domain-taxonomy.yml`.

## Checks

- Collection-to-domain mapping.
- Disconnected automation domains.
- Excessive EE scope.
- Unknown collection domains.
- Declared domain mismatch.
- Best-effort collection metadata resolution.
- Exact Python version conflicts when identifiable.

## Metadata Resolution

When `ansible-galaxy` is available in the API runtime, the advisor downloads selected collection packages into a temporary directory and inspects archive contents for:

- `requirements.txt`
- `bindep.txt`

The temporary workspace is discarded after analysis.

If `ansible-galaxy` is unavailable or download fails, the advisor records an INFO or WARNING finding and continues with taxonomy-based analysis.

## Outputs

Each request receives:

- `compatibility-report.json`
- `compatibility-report.md`

Severity levels:

- `BLOCKER`
- `WARNING`
- `INFO`

## Split Recommendation

When disconnected domains are present, the report recommends splitting requests into purpose-driven images, for example:

- `ee-ansible-windows`
- `ee-community-vmware`
- `ee-kubernetes`
- `ee-servicenow`
