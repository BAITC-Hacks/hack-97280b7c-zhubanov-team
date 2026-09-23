$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:JUPYTER_DATA_DIR = Join-Path $projectRoot '.jupyter-data'
$env:JUPYTER_CONFIG_DIR = Join-Path $projectRoot '.jupyter'
$env:JUPYTER_RUNTIME_DIR = Join-Path $projectRoot '.jupyter-runtime'
$env:IPYTHONDIR = Join-Path $projectRoot '.ipython'
$env:MPLCONFIGDIR = Join-Path $projectRoot '.mplconfig'

foreach ($folder in @($env:JUPYTER_DATA_DIR, $env:JUPYTER_CONFIG_DIR, $env:JUPYTER_RUNTIME_DIR, $env:IPYTHONDIR, $env:MPLCONFIGDIR)) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
}

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$notebook = Join-Path $projectRoot 'hackalem_hackathon_workbench.ipynb'
if (-not (Test-Path -LiteralPath $python)) { throw 'Не найдено окружение .venv. Создайте его и установите requirements.txt.' }
if (-not (Test-Path -LiteralPath $notebook)) { throw 'Не найден командный ноутбук.' }

Set-Location $projectRoot
& $python -m jupyter lab $notebook
