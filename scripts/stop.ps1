# Stop local ASPIRANT AI services listening on ports 8000, 8420, or 3000
$ErrorActionPreference = "Continue"
$Ports = @(8000, 8420, 3000)

foreach ($port in $Ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pidVal in $pids) {
            if ($pidVal -and $pidVal -gt 4) {
                Write-Host "Stopping process PID $pidVal on port $port..." -ForegroundColor Yellow
                Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
Write-Host "ASPIRANT AI local listeners stopped." -ForegroundColor Green
