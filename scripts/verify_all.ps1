$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONPATH = $RepoRoot

function Assert-ExitZero([string]$Label) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Label failed with exit code $LASTEXITCODE"
  }
}

Write-Host "1/6 Running Alembic migration and schema drift check..."
uv run --directory $RepoRoot python -m alembic -c "$RepoRoot\backend\alembic.ini" upgrade head
Assert-ExitZero "Alembic upgrade head"
uv run --directory $RepoRoot python -m alembic -c "$RepoRoot\backend\alembic.ini" check
Assert-ExitZero "Alembic schema drift check"

Write-Host "2/6 Running Self-Healing & Security AST audit..."
uv run --directory $RepoRoot python scripts/self_heal.py
Assert-ExitZero "Repository Self-Healing audit"

Write-Host "3/6 Running Python V1 Desktop + Ecosystem Backend tests..."
uv run --directory $RepoRoot python -m pytest tests -v
Assert-ExitZero "Python V1 desktop test suite"
uv run --directory $RepoRoot python -m pytest backend/tests -v
Assert-ExitZero "Python ecosystem backend test suite"

Write-Host "4/6 Validating UI routes, TypeScript, and building Next.js production bundle..."
Push-Location (Join-Path $RepoRoot "frontend")
try {
  npm run validate:routes
  Assert-ExitZero "Next.js route integrity validator"
  npx tsc --noEmit
  Assert-ExitZero "TypeScript typecheck"
  npm run build
  Assert-ExitZero "Next.js production build"
} finally {
  Pop-Location
}

Write-Host "5/6 Running live Playwright UI navigation test..."
uv run --directory $RepoRoot python scripts/verify_ui_navigation.py
Assert-ExitZero "Playwright UI navigation test"

Write-Host "6/6 Verifying Electron scripts..."
node -c (Join-Path $RepoRoot "desktop\electron\main.js")
Assert-ExitZero "Electron main.js syntax check"
node -c (Join-Path $RepoRoot "desktop\electron\preload.js")
Assert-ExitZero "Electron preload.js syntax check"

Write-Host "ALL VERIFICATION STAGES PASSED."
