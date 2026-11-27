$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = $RepoRoot

Write-Host "Running Alembic migrations against configured database..."
uv run --directory $RepoRoot python -m alembic -c "$RepoRoot\backend\alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) {
  throw "Alembic upgrade head failed with exit code $LASTEXITCODE"
}

uv run --directory $RepoRoot python -m alembic -c "$RepoRoot\backend\alembic.ini" current
if ($LASTEXITCODE -ne 0) {
  throw "Alembic current failed with exit code $LASTEXITCODE"
}
