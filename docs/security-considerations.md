# Security Considerations

This lab is intentionally explicit about risky operations.

## Docker Socket Mounting

Mounting the host Docker socket into a pod can grant broad control over the host daemon. This lab does not require Docker socket mounting for the Minikube build path. Local Docker/Podman scripts are development conveniences only.

Enterprise alternatives include BuildKit rootless, Buildah with constrained privileges, Tekton, OpenShift Builds, or a dedicated build service.

## Minikube Builder Privileges

The Minikube lab uses a dedicated builder Job with rootful privileged Buildah because rootless Buildah requires user namespace support that is not consistently available in Windows Podman-backed Minikube. The Job does not mount the host Docker socket and only receives the generated EE workspace plus optional registry credentials.

Treat this as a local lab trade-off. In an enterprise platform, move image builds into a hardened build service or pipeline with restricted service accounts, admission policy, image scanning, SBOM generation, and signing.

## Secrets

Secrets must not be stored in Git, generated EE files, examples, or build logs. Registry credentials belong in environment variables, Kubernetes Secrets, or a secrets manager.

The Quay publish path uses `kubernetes.io/dockerconfigjson` and mounts the secret as `DOCKER_CONFIG/config.json`.

## Unpinned Versions

Unpinned collection versions make builds drift over time. The platform blocks unpinned collections unless the requester enables `allow_unpinned` and provides a justification.

## Custom Base Images

Base images define the inherited package set, vulnerability profile, and package manager behavior. Custom base image mode is allowed only with an explicit warning and justification.

## LLM Output

Ollama output is never policy. It can help explain findings or draft documentation, but deterministic guardrails, vulnerability scans, and human approvals control the workflow.

## Publishing

Publishing turns a generated artifact into a consumable platform image. The platform requires a second approval gate before Quay push.

## Vulnerability Scanning

The OSV.dev integration checks selected PyPI package versions. It is useful, but it is not complete enterprise image scanning. Production adaptations should add container image scanning, SBOMs, signing, and admission policies.

## Audit Trail

Every request should retain who requested it, what changed, what was approved, what was built, and what was published. This lab records request metadata, parent request IDs, build logs, publish logs, generated files, reports, and image tags.
