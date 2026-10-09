[CmdletBinding()]
param([switch]$UpdateLock)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'tools\fishing\YesBd2.FishingBridge.csproj'
$output = Join-Path $root 'tools\fishing\backend'
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw 'Install .NET SDK 8 or newer, then run scripts\build_fishing.ps1.'
}
$restoreArgs = @('restore', $project, '--nologo')
if (-not $UpdateLock) { $restoreArgs += '--locked-mode' }
& dotnet @restoreArgs
if ($LASTEXITCODE -ne 0) { throw 'Fishing dependency restore failed.' }
& dotnet publish $project -c Release --no-restore -o $output --nologo
if ($LASTEXITCODE -ne 0) { throw 'Fishing backend build failed.' }
& (Join-Path $output 'YesBd2.FishingBridge.exe') --identity
if ($LASTEXITCODE -ne 0) { throw 'Fishing backend identity check failed.' }
Copy-Item -LiteralPath (Join-Path $root 'vendor\bd2-fishing\LICENSE') -Destination (Join-Path $output 'BD2Fishing-LICENSE.txt')
Copy-Item -LiteralPath (Join-Path $root 'vendor\bd2-fishing\licenses') -Destination $output -Recurse -Force
Write-Host "Fishing backend ready: $output"
