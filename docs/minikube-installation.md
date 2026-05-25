# Minikube Installation

Minikube is the primary runtime for this lab.

## Windows Preparation

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\install-lab.ps1
.\scripts\verify-lab.ps1
```

Restart the terminal after installation so user `PATH` updates are available.

## Start Minikube

```powershell
.\scripts\setup-minikube.ps1
```

The default Windows lab path uses Podman:

```powershell
.\scripts\setup-minikube.ps1 -Driver podman -Memory 6144mb
```

If your Podman machine exposes less memory, lower the value:

```powershell
.\scripts\setup-minikube.ps1 -Memory 4096mb
```

## Build Local Images Into Minikube

```powershell
minikube image build -t ee-factory-lab/api:local -f apps/api/Dockerfile .
minikube image build -t ee-factory-lab/portal:local -f Dockerfile apps/portal
minikube image build -t ee-factory-lab/builder:local -f Dockerfile apps/builder
```

## Create Secrets

The deploy script creates the PostgreSQL/API secret directly in Kubernetes with a generated password:

```powershell
.\scripts\deploy-minikube.ps1
```

Quay registry secret for publishing:

```powershell
$env:QUAY_USERNAME = Read-Host "Quay username or robot"
$env:QUAY_PASSWORD = Read-Host "Quay token"
.\scripts\create-quay-secret.ps1
```

## Deploy

```powershell
.\scripts\deploy-minikube.ps1
kubectl -n ee-factory-lab get pods,svc,pvc
```

## Port Forward

```powershell
.\scripts\port-forward.ps1 -StopExisting
```

Open:

- Portal: http://localhost:3000
- API docs: http://localhost:8000/docs

## Builder Job

The API creates Jobs dynamically after generated files are approved. A template is included at `deploy/minikube/builder-job-template.yml` to make the build shape explicit.

The Job mounts:

- `ee-factory-data` PVC at `/data`.
- Optional `quay-docker-config` as `/workspace/.docker/config.json`.

No Docker socket is mounted.

For local Minikube compatibility, the builder Job runs rootful privileged Buildah. This is isolated to the lab build worker and should be treated as a local-only trade-off. A production platform should use a controlled build service such as Tekton, OpenShift Builds, hardened BuildKit, Kaniko, or a dedicated pipeline with image scanning, signing, and policy enforcement.
