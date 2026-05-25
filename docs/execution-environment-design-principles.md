# Execution Environment Design Principles

Prefer small, purpose-driven, versioned EEs aligned to one automation domain.

Avoid monolithic enterprise EEs that mix unrelated domains such as Windows, VMware, Kubernetes, and ServiceNow unless the same workflow truly needs all dependencies.

## Practical Rules

- Pin every collection version.
- Keep Python dependencies narrow and explicit.
- Use RPM-based base images for generated EEs in this lab.
- Treat a meaningful Git or IDP edit as a new immutable image tag.
- Keep ownership clear: one EE should map to one primary automation domain.
- Split EEs when dependency sets belong to disconnected domains.
