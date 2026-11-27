# Initial Setup & Dependencies for Aspirant AI (Windows 11)
param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

Write-Host "==> Setting up ASPIRANT AI in $RepoRoot" -ForegroundColor Cyan

if (!(Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example (configure GEMINI_API_KEY and secrets before cloud runs)." -ForegroundColor Yellow
} else {
    Write-Host "Preserving existing .env configuration." -ForegroundColor Green
}

uv sync

Write-Host "Running Alembic database migrations..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File ".\scripts\run_migrations.ps1"

if (-not $SkipFrontend -and (Test-Path "frontend\package.json")) {
    Write-Host "Installing Web Console dependencies..." -ForegroundColor Cyan
    Push-Location "frontend"
    try {
        npm install
    } finally {
        Pop-Location
    }
}

Write-Host "Setup complete. Run .\scripts\start.ps1 to launch ASPIRANT AI." -ForegroundColor Green
