[CmdletBinding()]
param(
    [ValidateSet('UTC', 'Asia/Almaty')][string]$SourceTimezone = 'UTC',
    [string]$DataDir = (Join-Path $PSScriptRoot 'data/input'),
    [ValidateRange(1024, 65535)][int]$ApiPort = 8000,
    [ValidateRange(1024, 65535)][int]$UiPort = 5173,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements.txt first; see INSTALL.md.'
}
$npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source
$nodeVersion = [Version](& node -p 'process.versions.node')
if ($nodeVersion -lt [Version]'22.12.0') { throw 'Use Node.js 22.12+ (tested with Node 22).' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend/node_modules/.bin/vite.cmd'))) {
    throw 'Run npm --prefix frontend ci first.'
}
$resolvedData = (Resolve-Path -LiteralPath $DataDir).Path
foreach ($name in @('turbine-1.csv', 'turbine-2.csv')) {
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedData $name) -PathType Leaf)) {
        throw "Missing organizer CSV: $name in $resolvedData"
    }
}
& $pythonPath -c 'import fastapi, uvicorn, pandas, numpy, sys; from zoneinfo import ZoneInfo; ZoneInfo(sys.argv[1])' $SourceTimezone
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies are incomplete; install requirements.txt.' }
if ($ApiPort -eq $UiPort) { throw 'API and frontend require different ports.' }
$occupiedPorts = Get-NetTCPConnection -State Listen -LocalPort @($ApiPort, $UiPort) -ErrorAction SilentlyContinue
if ($occupiedPorts) { throw 'A requested port is occupied. Stop your existing server or select -ApiPort / -UiPort.' }
Write-Host "Prerequisites found. CSV timezone scenario: $SourceTimezone (not organizer-confirmed)."
if ($CheckOnly) { return }

$logDir = Join-Path $projectRoot 'outputs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$originalEnv = @{}
foreach ($name in @('DATA_DIR', 'SOURCE_TIMEZONE', 'VITE_API_PROXY_TARGET', 'VITE_API_BASE_URL')) {
    $originalEnv[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$backendProcess = $null
Push-Location $projectRoot
try {
    $env:DATA_DIR = $resolvedData
    $env:SOURCE_TIMEZONE = $SourceTimezone
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
    # Same-origin relative requests use Vite's local API proxy.
    $env:VITE_API_BASE_URL = '/'
    $backendProcess = Start-Process -FilePath $pythonPath `
        -ArgumentList @('-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', "$ApiPort") `
        -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir 'backend.stdout.log') `
        -RedirectStandardError (Join-Path $logDir 'backend.stderr.log')

    $ready = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(25)
    while ([DateTime]::UtcNow -lt $deadline) {
        $backendProcess.Refresh()
        if ($backendProcess.HasExited) { throw 'Backend exited; inspect outputs/backend.stderr.log.' }
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$ApiPort/health" -TimeoutSec 2
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 200 }
    }
    if (-not $ready) { throw 'Backend did not become ready; inspect outputs/backend.stderr.log.' }
    Write-Host "Open http://127.0.0.1:$UiPort and choose Backend API. Stop with Ctrl+C."
    & $npmCommand --prefix frontend run dev -- --host 127.0.0.1 --port $UiPort --strictPort
    if ($LASTEXITCODE -ne 0) { throw "Frontend exited with code $LASTEXITCODE." }
} finally {
    if ($null -ne $backendProcess) {
        $backendProcess.Refresh()
        if (-not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id }
    }
    foreach ($name in $originalEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $originalEnv[$name], 'Process')
    }
    Pop-Location
}
