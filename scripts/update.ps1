# Non-destructive dependency and migration update for ASPIRANT AI
$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

Write-Host "Syncing Python environment with uv..." -ForegroundColor Cyan
uv sync

Write-Host "Applying pending database migrations..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File ".\scripts\run_migrations.ps1"

if (Test-Path "frontend\package.json") {
    Write-Host "Updating Next.js frontend dependencies..." -ForegroundColor Cyan
    Push-Location "frontend"
    try {
        npm install
    } finally {
        Pop-Location
    }
}
Write-Host "ASPIRANT AI update complete." -ForegroundColor Green
