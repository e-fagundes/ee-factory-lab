[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Initialize-SessionPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = @($machinePath, $userPath) -join ";"
}

Initialize-SessionPath

$checks = @(
    @{ Command = "git"; Arguments = @("--version") },
    @{ Command = "python"; Arguments = @("--version") },
    @{ Command = "node"; Arguments = @("--version") },
    @{ Command = "npm"; Arguments = @("--version") },
    @{ Command = "make"; Arguments = @("--version") },
    @{ Command = "podman"; Arguments = @("--version") },
    @{ Command = "kubectl"; Arguments = @("version", "--client=true") },
    @{ Command = "minikube"; Arguments = @("version") },
    @{ Command = "helm"; Arguments = @("version", "--short") },
    @{ Command = "ollama"; Arguments = @("--version"); Optional = $true }
)

$failed = 0

foreach ($check in $checks) {
    $command = Get-Command $check.Command -ErrorAction SilentlyContinue
    if (-not $command) {
        $label = if ($check.Optional) { "optional" } else { "required" }
        Write-Host "MISSING [$label] $($check.Command)" -ForegroundColor $(if ($check.Optional) { "Yellow" } else { "Red" })
        if (-not $check.Optional) {
            $failed++
        }
        continue
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $version = & $command.Source @($check.Arguments) 2>$null | Select-Object -First 1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    Write-Host "OK $($check.Command): $version"
}

Write-Host ""
Write-Host "Execution policy:"
Write-Host (Get-ExecutionPolicy -List | Format-Table -AutoSize | Out-String)

if ($failed -gt 0) {
    throw "$failed required lab tool(s) were not found in PATH. Run scripts\install-lab.ps1 and open a new terminal."
}

Write-Host ""
Write-Host "Lab PATH verification completed."
