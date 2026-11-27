# Launch ASPIRANT AI in desktop, web, or ecosystem mode (with optional Windows Startup shortcut toggle)
param(
    [ValidateSet("desktop", "web", "ecosystem")]
    [string]$Mode = "desktop",
    [switch]$RegisterStartup,
    [switch]$UnregisterStartup
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutCmd = Join-Path $StartupDir "AspirantAI.cmd"

if ($RegisterStartup) {
    $cmdBody = "@echo off`r`npowershell -ExecutionPolicy Bypass -File `"$RepoRoot\scripts\start.ps1`" -Mode $Mode`r`n"
    Set-Content -Path $ShortcutCmd -Value $cmdBody -Encoding ASCII
    Write-Host "Registered Windows Startup launcher at $ShortcutCmd" -ForegroundColor Green
}
if ($UnregisterStartup -and (Test-Path $ShortcutCmd)) {
    Remove-Item $ShortcutCmd -Force
    Write-Host "Removed Windows Startup launcher $ShortcutCmd" -ForegroundColor Yellow
}

if ($Mode -eq "desktop") {
    Write-Host "Starting ASPIRANT AI Native PySide6 Workstation..." -ForegroundColor Cyan
    uv run python -m aspirant.main
} elseif ($Mode -eq "ecosystem") {
    powershell -ExecutionPolicy Bypass -File ".\scripts\dev_ecosystem.ps1"
} else {
    Write-Host "Starting ASPIRANT AI Ecosystem API (8000) & Web Console (3000)..." -ForegroundColor Cyan
    powershell -ExecutionPolicy Bypass -File ".\scripts\dev_ecosystem.ps1"
}
