$ErrorActionPreference = "Stop"

function Add-UserPathDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Directory
    )

    if (-not (Test-Path $Directory)) {
        return
    }

    $resolved = (Resolve-Path $Directory).Path.TrimEnd("\")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $userEntries = $userPath.Split(";", [System.StringSplitOptions]::RemoveEmptyEntries) |
        ForEach-Object { $_.TrimEnd("\") } |
        Where-Object { $_ -and ($_ -ine $resolved) }

    $newUserPath = (@($resolved) + $userEntries) -join ";"

    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    $processEntries = $env:Path.Split(";", [System.StringSplitOptions]::RemoveEmptyEntries) |
        ForEach-Object { $_.TrimEnd("\") } |
        Where-Object { $_ -and ($_ -ine $resolved) }
    $env:Path = (@($resolved) + $processEntries) -join ";"
    Write-Host "Ensured first in user PATH: $resolved"
}

function Ensure-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Name
    )

    Write-Host "Checking $Name..."
    $installed = winget list --id $Id --exact --accept-source-agreements 2>$null
    if ($LASTEXITCODE -eq 0 -and $installed -match [regex]::Escape($Id)) {
        Write-Host "$Name already installed."
        return
    }

    Write-Host "Installing $Name..."
    winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
}

function Add-ExecutableDirectoryToPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutableName,

        [string[]]$KnownDirectories = @()
    )

    foreach ($directory in $KnownDirectories) {
        if ($directory -and (Test-Path (Join-Path $directory $ExecutableName))) {
            Add-UserPathDirectory -Directory $directory
            return
        }
    }

    $searchRoots = @(
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)},
        (Join-Path $env:LOCALAPPDATA "Programs"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages")
    ) | Where-Object { $_ -and (Test-Path $_) }

    foreach ($root in $searchRoots) {
        $match = Get-ChildItem -Path $root -Recurse -Filter $ExecutableName -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($match) {
            Add-UserPathDirectory -Directory $match.DirectoryName
            return
        }
    }

    Write-Host "Could not find $ExecutableName to add to PATH. It may become available after opening a new terminal."
}

function Show-ToolVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [string[]]$Arguments = @("--version")
    )

    $resolved = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $resolved) {
        Write-Host "${Command}: not found in PATH"
        return
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $version = & $resolved.Source @Arguments 2>$null | Select-Object -First 1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    Write-Host "${Command}: $version"
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget is required. Install App Installer from Microsoft Store and run this script again."
}

Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force

Ensure-WingetPackage -Id "Git.Git" -Name "Git"
Ensure-WingetPackage -Id "GnuWin32.Make" -Name "Make"
Ensure-WingetPackage -Id "Python.Python.3.12" -Name "Python 3.12"
Ensure-WingetPackage -Id "OpenJS.NodeJS.LTS" -Name "Node.js LTS"
Ensure-WingetPackage -Id "RedHat.Podman" -Name "Podman"
Ensure-WingetPackage -Id "Kubernetes.kubectl" -Name "kubectl"
Ensure-WingetPackage -Id "Kubernetes.minikube" -Name "Minikube"
Ensure-WingetPackage -Id "Helm.Helm" -Name "Helm"
Ensure-WingetPackage -Id "Ollama.Ollama" -Name "Ollama"

Add-ExecutableDirectoryToPath -ExecutableName "git.exe" -KnownDirectories @(
    (Join-Path $env:ProgramFiles "Git\cmd")
)
Add-ExecutableDirectoryToPath -ExecutableName "make.exe" -KnownDirectories @(
    (Join-Path ${env:ProgramFiles(x86)} "GnuWin32\bin"),
    (Join-Path $env:ProgramFiles "GnuWin32\bin")
)
Add-ExecutableDirectoryToPath -ExecutableName "python.exe" -KnownDirectories @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312")
)
Add-UserPathDirectory -Directory (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\Scripts")
Add-ExecutableDirectoryToPath -ExecutableName "node.exe" -KnownDirectories @(
    (Join-Path $env:ProgramFiles "nodejs")
)
Add-ExecutableDirectoryToPath -ExecutableName "podman.exe" -KnownDirectories @(
    (Join-Path $env:ProgramFiles "RedHat\Podman"),
    (Join-Path $env:ProgramFiles "Podman")
)
Add-ExecutableDirectoryToPath -ExecutableName "kubectl.exe"
Add-ExecutableDirectoryToPath -ExecutableName "minikube.exe" -KnownDirectories @(
    (Join-Path $env:ProgramFiles "Kubernetes\Minikube")
)
Add-ExecutableDirectoryToPath -ExecutableName "helm.exe"
Add-ExecutableDirectoryToPath -ExecutableName "ollama.exe" -KnownDirectories @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama")
)

Write-Host ""
Write-Host "Lab tools installed or already present."
Write-Host "PowerShell script execution is set to RemoteSigned for CurrentUser."
Write-Host "PATH was updated for the current user. Open a new terminal so every shell sees the same PATH."
Write-Host "Podman is the default local container runtime for this lab; Docker Desktop is not installed by this script."
Write-Host "No registry credentials were requested or stored."

Write-Host ""
Write-Host "Detected tool versions:"
Show-ToolVersion -Command "git"
Show-ToolVersion -Command "python"
Show-ToolVersion -Command "node"
Show-ToolVersion -Command "npm" -Arguments @("--version")
Show-ToolVersion -Command "podman" -Arguments @("--version")
Show-ToolVersion -Command "kubectl" -Arguments @("version", "--client=true")
Show-ToolVersion -Command "minikube" -Arguments @("version")
Show-ToolVersion -Command "helm" -Arguments @("version", "--short")
Show-ToolVersion -Command "ollama" -Arguments @("--version")
