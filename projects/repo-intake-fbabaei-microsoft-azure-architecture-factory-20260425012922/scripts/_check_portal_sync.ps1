$ErrorActionPreference = 'Stop'
$localHtml   = (Get-FileHash factory-portal.html -Algorithm SHA256).Hash
$localRunner = (Get-FileHash scripts/local_brd_runner.py -Algorithm SHA256).Hash
$localSrv    = (Get-FileHash scripts/start_factory_portal.py -Algorithm SHA256).Hash
Write-Host "Local  portal.html     : $localHtml"
Write-Host "Local  local_brd_runner: $localRunner"
Write-Host "Local  start_factory   : $localSrv"
Write-Host '--- remote (via az containerapp exec) ---'
$cmd = 'sha256sum /app/factory-portal.html /app/scripts/local_brd_runner.py /app/scripts/start_factory_portal.py'
az containerapp exec -n arch-factory-dev-portal -g arch-factory-dev-rg --command $cmd 2>&1
