$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path '.venv')) { py -3 -m venv .venv; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
& .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& .\.venv\Scripts\python.exe -m playwright install chromium
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& .\.venv\Scripts\python.exe -m frameport.cli
