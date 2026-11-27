$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = $RepoRoot

Write-Host "Running Alembic migrations..."
Push-Location (Join-Path $RepoRoot "backend")
try {
  uv run --directory $RepoRoot python -m alembic upgrade head
} finally {
  Pop-Location
}
