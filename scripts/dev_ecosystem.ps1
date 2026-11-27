$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "Starting FastAPI Ecosystem Backend on http://127.0.0.1:8000 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='$RepoRoot'; uv run --directory '$RepoRoot' python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "Starting Next.js Web Console on http://127.0.0.1:3000 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Push-Location '$RepoRoot\frontend'; npm run dev"
