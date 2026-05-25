# Troubleshooting

## PowerShell Blocks Scripts

Run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

The lab installer also applies this setting for the current user.

## npm Or python Not Found

Restart the terminal after running:

```powershell
.\scripts\install-lab.ps1
.\scripts\verify-lab.ps1
```

## Podman Machine Not Running

For local image builds on Windows:

```powershell
.\scripts\test-build-image.ps1 -RequestId <id> -BuildImage -Runtime podman -StartPodmanMachine
```

For the full lab flow, prefer the Kubernetes builder job in Minikube. The Minikube path does not mount the host Docker socket.

## Generated Files Missing

Create a request, validate it, then run Generate files. Workspaces are created under `data/builds/<request-id>/`.

## Fedora Build Fails With `/usr/bin/python3 is not an executable`

Some public Fedora base images do not include Python at `/usr/bin/python3` before Ansible Builder runs its bootstrap steps. The platform adds a managed `dnf install -y python3 python3-pip` prepend step for Fedora requests using `ansible-core >= 2.16`.

Regenerate the files after validation so the managed bootstrap step appears in `execution-environment.yml`.

## AAP Configuration As Code Collection Resolution Fails

Current certified AAP Configuration as Code dependency sets may require private Automation Hub credentials. If `ansible-galaxy` reports that a dependency such as `ansible.platform` cannot be satisfied from public Galaxy, configure Automation Hub access in the enterprise adaptation path or use a public collection version for local lab testing.

## Publish Fails

Confirm:

- Generated files were approved.
- Publish was approved.
- `quay-docker-config` exists in namespace `ee-factory-lab`.
- The Quay robot/user has push access to the namespace.

## OSV Scan Fails

If the public OSV API is unavailable and `VULNERABILITY_SCAN_REQUIRED=false`, the platform records a warning and continues. If required mode is enabled, generation can block.
