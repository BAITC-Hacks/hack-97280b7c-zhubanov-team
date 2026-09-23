param(
    [ValidateSet('workbench', 'starter')]
    [string]$Notebook = 'workbench'
)

$ErrorActionPreference = 'Stop'
$notebookProjectRoot = $PSScriptRoot
$notebookPython = Join-Path $notebookProjectRoot '.venv\Scripts\python.exe'
$notebookFileName = if ($Notebook -eq 'starter') { 'hackalem_starter.ipynb' } else { 'hackalem_hackathon_workbench.ipynb' }
$notebookFilePath = Join-Path $notebookProjectRoot (Join-Path 'notebooks\legacy' $notebookFileName)

Write-Warning 'This opens an optional legacy preparation notebook, not the wind forecasting application. Use start_hackalem.ps1 for the application.'
if (-not (Test-Path -LiteralPath $notebookPython -PathType Leaf)) {
    throw 'Create the root .venv first and install requirements-notebooks.txt. See README.md.'
}
if (-not (Test-Path -LiteralPath $notebookFilePath -PathType Leaf)) {
    throw "Legacy notebook is missing: $notebookFilePath"
}
& $notebookPython -c 'import jupyterlab'
if ($LASTEXITCODE -ne 0) {
    throw 'Install optional dependencies: .venv\Scripts\python.exe -m pip install -r requirements-notebooks.txt'
}

$env:JUPYTER_DATA_DIR = Join-Path $notebookProjectRoot '.jupyter-data'
$env:JUPYTER_CONFIG_DIR = Join-Path $notebookProjectRoot '.jupyter'
$env:JUPYTER_RUNTIME_DIR = Join-Path $notebookProjectRoot '.jupyter-runtime'
$env:IPYTHONDIR = Join-Path $notebookProjectRoot '.ipython'
$env:MPLCONFIGDIR = Join-Path $notebookProjectRoot '.mplconfig'
foreach ($notebookConfigDir in @($env:JUPYTER_DATA_DIR, $env:JUPYTER_CONFIG_DIR, $env:JUPYTER_RUNTIME_DIR, $env:IPYTHONDIR, $env:MPLCONFIGDIR)) {
    New-Item -ItemType Directory -Force -Path $notebookConfigDir | Out-Null
}

Push-Location $notebookProjectRoot
try {
    & $notebookPython -m jupyter lab $notebookFilePath
    if ($LASTEXITCODE -ne 0) { throw "JupyterLab exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
