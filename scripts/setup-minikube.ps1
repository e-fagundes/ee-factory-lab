[CmdletBinding()]
param(
    [string]$Driver = "podman",
    [string]$ContainerRuntime = "containerd",
    [int]$Cpus = 4,
    [string]$Memory = "6144mb",
    [string]$Profile = "minikube"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required but was not found in PATH."
    }
}

Require-Command "minikube"
Require-Command "kubectl"
Require-Command "podman"

try {
    podman info *> $null
} catch {
    Write-Host "Podman is installed but not connected. Trying to start the default Podman machine..."
    podman machine start
    podman info *> $null
}

Write-Host "Starting Minikube profile '$Profile' with driver '$Driver'..."
minikube start `
    --profile $Profile `
    --driver $Driver `
    --container-runtime $ContainerRuntime `
    --cpus $Cpus `
    --memory $Memory

minikube profile $Profile
minikube addons enable storage-provisioner --profile $Profile
minikube addons enable default-storageclass --profile $Profile

Write-Host "Minikube is ready."
