# Minikube Manifests

This is the primary runtime path for `ee-factory-lab`.

## Included

- Namespace.
- Frontend deployment/service.
- Backend deployment/service.
- PostgreSQL deployment/service/PVC.
- Shared build workspace PVC.
- Builder Job template.
- ConfigMap.
- Secret example.
- Service account and RBAC.

## Quick Start

```powershell
.\scripts\setup-minikube.ps1
.\scripts\deploy-minikube.ps1
.\scripts\port-forward.ps1 -StopExisting
```

The default Minikube memory is `6144mb` because Podman Desktop on Windows often exposes less than 8 GiB by default.
Use `.\scripts\setup-minikube.ps1 -Memory 4096mb` if your lab machine is smaller.

The deploy script creates `ee-factory-secrets` directly in Kubernetes with a generated PostgreSQL password.
Do not commit real secret manifests.

To enable Quay.io publishing:

```powershell
$env:QUAY_USERNAME = Read-Host "Quay username or robot"
$env:QUAY_PASSWORD = Read-Host "Quay token"
.\scripts\create-quay-secret.ps1
```

The portal is available at `http://localhost:3000` and calls the API through `http://127.0.0.1:8000`.

## Build Job

The API creates a Job dynamically after generated files approval. The template documents the expected environment and volumes.

No host Docker socket is mounted.
