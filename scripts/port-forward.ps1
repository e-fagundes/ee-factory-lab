[CmdletBinding()]
param(
    [string]$Namespace = "ee-factory-lab",
    [int]$ApiPort = 8000,
    [int]$PortalPort = 3000,
    [switch]$StopExisting
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Stop-PortOwner {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.OwningProcess) {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($StopExisting) {
    Stop-PortOwner -Port $ApiPort
    Stop-PortOwner -Port $PortalPort
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stateDir = Join-Path $repoRoot "data/metadata"
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$api = Start-Process -FilePath "kubectl" `
    -ArgumentList "-n", $Namespace, "port-forward", "svc/ee-factory-api", "$ApiPort`:8000" `
    -WindowStyle Hidden `
    -PassThru

$portal = Start-Process -FilePath "kubectl" `
    -ArgumentList "-n", $Namespace, "port-forward", "svc/ee-factory-portal", "$PortalPort`:3000" `
    -WindowStyle Hidden `
    -PassThru

$state = @{
    api_pid = $api.Id
    portal_pid = $portal.Id
    api_url = "http://127.0.0.1:$ApiPort"
    portal_url = "http://localhost:$PortalPort"
    started_at = (Get-Date).ToString("o")
}

$state | ConvertTo-Json | Set-Content -Path (Join-Path $stateDir "port-forward-pids.json") -Encoding utf8

Write-Host "API:    http://127.0.0.1:$ApiPort"
Write-Host "Portal: http://localhost:$PortalPort"
Write-Host "Port-forward processes started. PIDs saved in data/metadata/port-forward-pids.json."
