$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONPATH = $RepoRoot

Write-Host "1/3 Running Python V1 + Ecosystem Backend tests..."
uv run --directory $RepoRoot python -m pytest tests -v
uv run --directory $RepoRoot python -m pytest backend/tests -v

Write-Host "2/3 Typechecking and building Next.js frontend..."
Push-Location (Join-Path $RepoRoot "frontend")
try {
  npx tsc --noEmit
  npm run build
} finally {
  Pop-Location
}

Write-Host "3/3 Verifying Electron scripts..."
node -c (Join-Path $RepoRoot "desktop\electron\main.js")
node -c (Join-Path $RepoRoot "desktop\electron\preload.js")
Write-Host "ALL CHECKS PASSED."
