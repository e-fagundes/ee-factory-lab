# Project Compliance Checklist

This checklist tracks the repository against the original platform engineering brief.

## Implemented

- Public-repository structure for `ee-factory-lab`.
- FastAPI backend with OpenAPI docs.
- Pydantic request models.
- Structured JSON logging.
- Domain taxonomy in `config/domain-taxonomy.yml`.
- Allowed RPM-based base images in `config/allowed-base-images.yml`.
- Deterministic guardrails for naming, tags, pinned collections, base images, domains, domain mixing, Python requirement syntax, system dependency review, secret-like values, and override justification.
- Template generation for schema v3 `execution-environment.yml`, `requirements.yml`, `requirements.txt`, `bindep.txt`, `manifest.json`, reports, and README.
- Local workspaces under `data/builds/<request-id>/` with `context/` and `logs/`.
- SQLite local development persistence and PostgreSQL-ready Minikube persistence.
- Example EEs for general, Windows, VMware, and ServiceNow.
- Minikube manifests for frontend, backend, PostgreSQL, shared data PVC, services, configmaps, secret template, RBAC, and builder job template.
- API-created Kubernetes build job specs.
- Builder worker for `ansible-builder create`, BuildKit/Buildah image build, logs, OCI archive, metadata, and registry push.
- Generated-files approval gate.
- Publish approval gate.
- Quay.io publishing through Kubernetes Secret.
- OSV.dev vulnerability advisor.
- Compatibility advisor with taxonomy, best-effort collection metadata inspection, and conflict warnings.
- Optional Ollama documentation assistance.
- Next.js portal wired to API actions.
- GitHub Actions for lint/test, example validation, manual example build, and release packaging.
- Windows install, verify, and local build test scripts.
- Documentation for architecture, Minikube, Quay.io, guardrails, compatibility, vulnerability scanning, security, Ollama, GitHub Actions, troubleshooting, and enterprise adaptation.

## Known Lab Trade-Offs

- The local development database defaults to SQLite for simplicity.
- The Minikube build path is functional lab architecture, not a hardened production build service.
- OSV.dev scanning is dependency intelligence, not full image scanning.
- The portal is intentionally compact and single-page for local demonstration.
- Example image publication requires user-provided Quay credentials.

## Next Enterprise Hardening Steps

- Add authenticated users and request ownership.
- Add an append-only audit event table.
- Add image scanner integration after build.
- Add SBOM generation.
- Add Cosign signatures.
- Add private Automation Hub support.
- Add GitOps reconciliation.
- Add AAP controller registration after publish.
