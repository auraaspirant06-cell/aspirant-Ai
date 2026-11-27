# Launch ASPIRANT AI Desktop Assistant
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
uv run python -m aspirant.main
