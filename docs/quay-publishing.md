# Quay.io Publishing

Quay.io is the default publish target. Publication is approval-gated and credentials are never generated into EE files.

## Quay Setup

1. Create a Quay.io account.
2. Create or choose an organization/namespace.
3. Decide the repository name. The lab uses the EE name as the repository name.
4. Create a robot account or token with push access.

## Local Login

```powershell
podman login quay.io
```

## Kubernetes Secret

The builder worker expects Docker config format at `DOCKER_CONFIG/config.json`.

```bash
read -rp "Quay username or robot: " QUAY_USERNAME
read -rsp "Quay token: " QUAY_PASSWORD
echo
export QUAY_USERNAME QUAY_PASSWORD
./scripts/create-quay-secret.sh
```

PowerShell:

```powershell
$env:QUAY_USERNAME = Read-Host "Quay username or robot"
$env:QUAY_PASSWORD = Read-Host "Quay token"
.\scripts\create-quay-secret.ps1
```

This creates:

```text
Secret: quay-docker-config
Type: kubernetes.io/dockerconfigjson
Mounted path: /workspace/.docker/config.json
```

## Publish Flow

1. Create and validate an EE request.
2. Generate files and reports.
3. Approve generated files.
4. Build the image or stage a build.
5. Review image reference, digest if available, logs, and warnings.
6. Approve publish.
7. Publish to Quay.io.

The API endpoint refuses publish before the publish approval gate is set.

The Kubernetes publish path also checks that the `quay-docker-config` Secret exists before creating the publish Job. The platform does not open an interactive Quay login from the portal.

## Manual Push

For local development only:

```powershell
.\scripts\test-build-image.ps1 -RequestId <request-id> -BuildImage -Runtime podman -StartPodmanMachine
podman push quay.io/<namespace>/<ee-name>:<tag>
```

Manual push is useful for learning, but the platform pattern is Kubernetes Job plus approval gates.
