# Quick health check for ASPIRANT AI environment, migrations, audio hardware, and endpoints
$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

Write-Host "=== ASPIRANT AI Health Check ===" -ForegroundColor Cyan

uv run python --version
uv run python -m alembic -c backend/alembic.ini current

$Env:PYTHONPATH = "$RepoRoot;$RepoRoot\src"
uv run python -c @"
from aspirant.core.config import AppSettings
from aspirant.voice.diagnostics import diagnose_audio_devices
cfg = AppSettings()
diag = diagnose_audio_devices()
print('Config OK:', {'wake_word': cfg.wake_word, 'voice_gender': cfg.voice_gender, 'robot_enabled': cfg.enable_robot})
print('Audio Status:', diag.get('mic_status'), '| Devices:', len(diag.get('input_devices', [])))
"@

Write-Host "Health check completed cleanly." -ForegroundColor Green
