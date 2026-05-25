[CmdletBinding()]
param(
    [string]$QuayUsername = $env:QUAY_USERNAME,
    [string]$QuayPassword = $env:QUAY_PASSWORD,
    [string]$QuayEmail = $(if ($env:QUAY_EMAIL) { $env:QUAY_EMAIL } else { "ee-factory-lab@example.invalid" }),
    [string]$Namespace = "ee-factory-lab"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

if (-not $QuayUsername) {
    $QuayUsername = Read-Host "Quay username or robot account"
}

if (-not $QuayPassword) {
    $securePassword = Read-Host "Quay password or robot token" -AsSecureString
    $QuayPassword = [System.Net.NetworkCredential]::new("", $securePassword).Password
}

kubectl -n $Namespace create secret docker-registry quay-docker-config `
    --docker-server=quay.io `
    --docker-username="$QuayUsername" `
    --docker-password="$QuayPassword" `
    --docker-email="$QuayEmail" `
    --dry-run=client -o yaml | kubectl apply -f -

Write-Host "Secret quay-docker-config created or updated in namespace $Namespace."
