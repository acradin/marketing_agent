param([switch]$Demo, [switch]$Check)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    python -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12+ required'"
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12+ and put it on PATH' }
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
& ./.venv/Scripts/python.exe -m pip install -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if ($Demo) {
    & ./.venv/Scripts/python.exe -m scripts.demo
    exit $LASTEXITCODE
}
if ($Check) {
    & ./.venv/Scripts/python.exe -m scripts.check_connections
    exit $LASTEXITCODE
}
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
& ./.venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& ./.venv/Scripts/python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8765
