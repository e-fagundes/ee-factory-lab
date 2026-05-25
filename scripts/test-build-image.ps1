[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RequestId,

    [switch]$BuildImage,

    [switch]$StartDockerDesktop,

    [switch]$StartPodmanMachine,

    [ValidateSet("auto", "docker", "podman")]
    [string]$Runtime = "podman"
)

$ErrorActionPreference = "Stop"

trap {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

function Initialize-SessionPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = @($machinePath, $userPath) -join ";"
}

Initialize-SessionPath

function Resolve-Python {
    $candidatePaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:ProgramFiles "Python312\python.exe")
    )

    foreach ($candidate in $candidatePaths) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "Python 3.12 was not found. Run scripts\install-lab.ps1 first."
}

function Resolve-ContainerRuntime {
    param(
        [string]$PreferredRuntime,
        [bool]$AllowDockerDesktopStart,
        [bool]$AllowPodmanMachineStart
    )

    $candidateNames = if ($PreferredRuntime -eq "auto") { @("podman", "docker") } else { @($PreferredRuntime) }
    $diagnostics = New-Object System.Collections.Generic.List[string]

    foreach ($candidate in $candidateNames) {
        $runtimePath = Resolve-ContainerRuntimePath -RuntimeName $candidate
        if (-not $runtimePath) {
            $diagnostics.Add("$candidate was not found in PATH.")
            continue
        }

        $readiness = Test-ContainerRuntimeReady -RuntimePath $runtimePath
        if ($readiness.Ready) {
            return @{
                Name = $candidate
                Path = $runtimePath
            }
        }

        if ($candidate -eq "docker" -and $AllowDockerDesktopStart) {
            Start-DockerDesktop
            $readiness = Test-ContainerRuntimeReady -RuntimePath $runtimePath
            if ($readiness.Ready) {
                return @{
                    Name = $candidate
                    Path = $runtimePath
                }
            }
        }

        if ($candidate -eq "podman" -and $AllowPodmanMachineStart) {
            Start-PodmanMachine -PodmanPath $runtimePath
            $readiness = Test-ContainerRuntimeReady -RuntimePath $runtimePath
            if ($readiness.Ready) {
                return @{
                    Name = $candidate
                    Path = $runtimePath
                }
            }
        }

        $diagnostics.Add("$candidate was found at $runtimePath, but it is not ready. $($readiness.Message)")
    }

    $message = @(
        "No ready container runtime was found.",
        "",
        ($diagnostics -join "`n"),
        "",
        "To build an image, start a Podman machine or Docker Desktop and wait until the engine is running.",
        "You can also rerun with -StartPodmanMachine or -StartDockerDesktop to let this script start a runtime and wait for readiness.",
        "To only generate the Containerfile/build context, run this script without -BuildImage."
    ) -join "`n"

    throw $message
}

function Start-PodmanMachine {
    param([string]$PodmanPath)

    $wslStatus = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("--status")
    if ($wslStatus.ExitCode -ne 0) {
        Write-Host "WSL is not ready. Podman machine cannot start until WSL2 is installed and enabled."
        return
    }

    $machineList = Invoke-NativeCapture -FilePath $PodmanPath -Arguments @("machine", "list")
    $machineOutput = $machineList.Output -join "`n"
    if ($machineOutput -notmatch "podman-machine-default") {
        Write-Host "Creating Podman machine..."
        $init = Invoke-NativeCapture -FilePath $PodmanPath -Arguments @("machine", "init")
        $init.Output | ForEach-Object { Write-Host $_ }
        if ($init.ExitCode -ne 0) {
            Write-Host "podman machine init failed."
            return
        }
    }

    Write-Host "Starting Podman machine..."
    $start = Invoke-NativeCapture -FilePath $PodmanPath -Arguments @("machine", "start")
    $start.Output | ForEach-Object { Write-Host $_ }

    $rootConnection = Invoke-NativeCapture -FilePath $PodmanPath -Arguments @(
        "system",
        "connection",
        "default",
        "podman-machine-default-root"
    )
    if ($rootConnection.ExitCode -eq 0) {
        Write-Host "Using podman-machine-default-root as the local lab connection."
    }

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Seconds 3
        $readiness = Test-ContainerRuntimeReady -RuntimePath $PodmanPath
        if ($readiness.Ready) {
            Write-Host "Podman machine is ready."
            return
        }
        Write-Host "Waiting for Podman machine... ($attempt/20)"
    }
}

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @()
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return @{
        ExitCode = $exitCode
        Output = $output
    }
}

function Resolve-ContainerRuntimePath {
    param([string]$RuntimeName)

    $command = Get-Command $RuntimeName -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $knownPaths = @{
        docker = @(
            (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe")
        )
        podman = @(
            (Join-Path $env:ProgramFiles "RedHat\Podman\podman.exe"),
            (Join-Path $env:ProgramFiles "Podman\podman.exe")
        )
    }

    foreach ($candidatePath in $knownPaths[$RuntimeName]) {
        if (Test-Path $candidatePath) {
            return $candidatePath
        }
    }

    return $null
}

function Start-DockerDesktop {
    $dockerDesktopPath = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerDesktopPath)) {
        Write-Host "Docker Desktop executable was not found at $dockerDesktopPath"
        return
    }

    $running = Get-Process | Where-Object { $_.ProcessName -eq "Docker Desktop" }
    if (-not $running) {
        Write-Host "Starting Docker Desktop..."
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden
    }
    else {
        Write-Host "Docker Desktop is already running. Waiting for engine readiness..."
    }

    $dockerPath = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        Start-Sleep -Seconds 4
        $readiness = Test-ContainerRuntimeReady -RuntimePath $dockerPath
        if ($readiness.Ready) {
            Write-Host "Docker engine is ready."
            return
        }
        Write-Host "Waiting for Docker engine... ($attempt/30)"
    }
}

function Test-ContainerRuntimeReady {
    param([string]$RuntimePath)

    $result = Invoke-NativeCapture -FilePath $RuntimePath -Arguments @("info")
    if ($result.ExitCode -eq 0) {
        return @{
            Ready = $true
            Message = "Runtime responded to info."
        }
    }

    $errorLine = $result.Output | Where-Object { $_ -match "failed|error|daemon|pipe|cannot|not running" } | Select-Object -First 1
    $summary = if ($errorLine) { $errorLine } else { ($result.Output | Select-Object -Last 3) -join " " }
    return @{
        Ready = $false
        Message = if ($summary) { $summary } else { "Runtime info failed with exit code $($result.ExitCode)." }
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$workspacePath = Join-Path $repoRoot "data\builds\$RequestId"

if (-not (Test-Path $workspacePath)) {
    throw "Build workspace was not found: $workspacePath"
}

$workspace = Resolve-Path $workspacePath
if (-not $workspace.Path.StartsWith($repoRoot.Path)) {
    throw "Refusing to use a workspace outside the repository."
}

$manifestPath = Join-Path $workspace "manifest.json"
$definitionPath = Join-Path $workspace "execution-environment.yml"
$contextPath = Join-Path $workspace "context"
$buildLogPath = Join-Path $workspace "logs\build.log"

if (-not (Test-Path $manifestPath)) {
    throw "manifest.json was not found. Generate files in the portal first."
}

if (-not (Test-Path $definitionPath)) {
    throw "execution-environment.yml was not found. Generate files in the portal first."
}

New-Item -ItemType Directory -Force -Path $contextPath | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $buildLogPath) | Out-Null

$builderVenv = Join-Path $repoRoot "apps\builder\.venv"
$builderPython = Join-Path $builderVenv "Scripts\python.exe"
$ansibleBuilder = Join-Path $builderVenv "Scripts\ansible-builder.exe"

if (-not (Test-Path $builderPython)) {
    $python = Resolve-Python
    Write-Host "Creating builder virtual environment..."
    & $python -m venv $builderVenv
}

Write-Host "Installing builder dependencies..."
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
& $builderPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $repoRoot "apps\builder\requirements.txt")

if (-not (Test-Path $ansibleBuilder)) {
    throw "ansible-builder was not installed in $builderVenv"
}

Push-Location $workspace
try {
    Write-Host "Creating build context with ansible-builder..."
    $createResult = Invoke-NativeCapture -FilePath $ansibleBuilder -Arguments @(
        "create",
        "--file",
        "execution-environment.yml",
        "--context",
        "context",
        "--output-filename",
        "Containerfile"
    )
    $createResult.Output | Tee-Object -FilePath $buildLogPath

    if ($createResult.ExitCode -ne 0) {
        throw "ansible-builder create failed with exit code $($createResult.ExitCode). See $buildLogPath"
    }

    $containerfile = Join-Path $contextPath "Containerfile"
    if (Test-Path $containerfile) {
        $containerfileContent = Get-Content $containerfile -Raw
        $normalizedContainerfile = $containerfileContent.Replace("\", "/")
        if ($normalizedContainerfile -ne $containerfileContent) {
            Set-Content -Path $containerfile -Value $normalizedContainerfile -NoNewline -Encoding utf8
            "Normalized Windows path separators in generated Containerfile for Linux builders." |
                Tee-Object -FilePath $buildLogPath -Append
        }
    }

    Write-Host "Build context created: $contextPath"

    if ($BuildImage) {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        $imageRef = if ($manifest.image) { $manifest.image } else { "localhost/$($manifest.ee_name):$($manifest.image_tag)" }
        $containerRuntime = Resolve-ContainerRuntime `
            -PreferredRuntime $Runtime `
            -AllowDockerDesktopStart:$StartDockerDesktop `
            -AllowPodmanMachineStart:$StartPodmanMachine

        Write-Host "Building image $imageRef with $($containerRuntime.Name) at $($containerRuntime.Path)..."
        $buildResult = Invoke-NativeCapture -FilePath $containerRuntime.Path -Arguments @(
            "build",
            "-f",
            $containerfile,
            "-t",
            $imageRef,
            $contextPath
        )
        $buildResult.Output | Tee-Object -FilePath $buildLogPath -Append

        if ($buildResult.ExitCode -ne 0) {
            throw "Container image build failed with exit code $($buildResult.ExitCode). See $buildLogPath"
        }

        Write-Host "Image build completed: $imageRef"
    }
    else {
        Write-Host "Image build skipped. Re-run with -BuildImage to build the local image."
    }
}
finally {
    Pop-Location
}
