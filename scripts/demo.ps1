param(
    [ValidateSet("lock", "latency", "control")]
    [string]$Scenario = "lock",
    [ValidateSet("quick", "demo", "full")]
    [string]$Profile = "demo"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LocalK6 = Join-Path $RepositoryRoot ".tools\k6\k6-v2.1.0-windows-amd64"
if (Test-Path -LiteralPath $LocalK6) {
    $env:PATH = "$LocalK6;$env:PATH"
}
$env:TRACEFORGE_TRUSTED_LOCAL_MODE = "true"

Push-Location $RepositoryRoot
try {
    uv run python scripts/bootstrap_demo_repo.py
    uv run traceforge demo $Scenario --profile $Profile
}
finally {
    Pop-Location
}
