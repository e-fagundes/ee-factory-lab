[CmdletBinding()]
param(
    [string]$Namespace = "ee-factory-lab",
    [string]$Profile = "minikube",
    [switch]$SkipImageBuild,
    [switch]$EnableOllama,
    [string]$OllamaBaseUrl = "http://host.minikube.internal:11434",
    [string]$OllamaModel = "llama3.2:1b",
    [string]$PostgresPassword
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required but was not found in PATH."
    }
}

function New-LabPassword {
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return ([Convert]::ToBase64String($bytes) -replace "[^a-zA-Z0-9]", "").Substring(0, 24)
}

Require-Command "minikube"
Require-Command "kubectl"

if (-not $PostgresPassword) {
    $PostgresPassword = New-LabPassword
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

kubectl apply -f deploy/minikube/namespace.yml

$databaseUrl = "postgresql://ee_factory:$PostgresPassword@postgres:5432/ee_factory"
kubectl -n $Namespace create secret generic ee-factory-secrets `
    --from-literal=postgres-password="$PostgresPassword" `
    --from-literal=database-url="$databaseUrl" `
    --dry-run=client -o yaml | kubectl apply -f -

if (-not $SkipImageBuild) {
    Write-Host "Building API image inside Minikube..."
    minikube image build --profile $Profile -t ee-factory-lab/api:local -f apps/api/Dockerfile .

    Write-Host "Building portal image inside Minikube..."
    minikube image build --profile $Profile -t ee-factory-lab/portal:local -f Dockerfile apps/portal

    Write-Host "Building builder image inside Minikube..."
    minikube image build --profile $Profile -t ee-factory-lab/builder:local -f Dockerfile apps/builder
}

kubectl apply -k deploy/minikube

if ($EnableOllama) {
    Write-Host "Enabling Ollama advisory integration in the API deployment..."
    kubectl -n $Namespace patch configmap ee-factory-config --type merge -p (
        @{
            data = @{
                OLLAMA_ENABLED = "true"
                OLLAMA_BASE_URL = $OllamaBaseUrl
                OLLAMA_MODEL = $OllamaModel
            }
        } | ConvertTo-Json -Compress
    )
    kubectl -n $Namespace rollout restart deployment/ee-factory-api
}

kubectl -n $Namespace rollout status deployment/postgres --timeout=180s
kubectl -n $Namespace rollout status deployment/ee-factory-api --timeout=180s
kubectl -n $Namespace rollout status deployment/ee-factory-portal --timeout=180s

kubectl -n $Namespace get pods,svc,pvc

Write-Host "Deployment complete. Run scripts/port-forward.ps1 to access the portal and API."
