[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statePath = Join-Path $repoRoot "data/metadata/port-forward-pids.json"

if (-not (Test-Path $statePath)) {
    Write-Host "No port-forward state file found."
    exit 0
}

$state = Get-Content $statePath -Raw | ConvertFrom-Json
foreach ($pidValue in @($state.api_pid, $state.portal_pid)) {
    if ($pidValue) {
        Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item $statePath -Force
Write-Host "Port-forward processes stopped."
