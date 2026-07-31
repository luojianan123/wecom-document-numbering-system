$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Join-Path $ProjectRoot "backend"
$VenvRoot = Join-Path $BackendRoot ".venv-win"
$Python = Join-Path $VenvRoot "Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Creating the Windows Python environment..."
    py -3.12 -m venv $VenvRoot
}

Write-Host "Installing or updating backend dependencies..."
& $Python -m pip install --disable-pip-version-check -e "$BackendRoot[dev]"

Write-Host "Applying database migrations..."
Set-Location $ProjectRoot
& $Python -m alembic -c "$BackendRoot\alembic.ini" upgrade head

Write-Host "Starting the file code system at http://localhost:8088"
& $Python -m uvicorn app.main:app --app-dir $BackendRoot --host 0.0.0.0 --port 8088
