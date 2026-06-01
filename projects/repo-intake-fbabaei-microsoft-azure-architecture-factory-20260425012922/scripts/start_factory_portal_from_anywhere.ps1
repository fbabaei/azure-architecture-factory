Param(
    [Parameter(Mandatory = $false)]
    [int]$Port = 5501,

    [Parameter(Mandatory = $false)]
    [switch]$NoOpen,

    [Parameter(Mandatory = $false)]
    [switch]$Foreground
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PortalScript = Join-Path $RepoRoot "scripts\start_factory_portal.py"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PortalScript)) {
    Write-Error "Could not find scripts/start_factory_portal.py."
    exit 1
}

if (Test-Path $VenvPython) {
    $PythonCmd = $VenvPython
    $PythonArgs = @($PortalScript)
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
    $PythonArgs = @($PortalScript)
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
    $PythonArgs = @($PortalScript)
}
else {
    Write-Error "Python was not found. Install Python or create .venv first."
    exit 1
}

$existingConn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existingConn) {
    $existingProcess = Get-Process -Id $existingConn.OwningProcess -ErrorAction SilentlyContinue
    if ($existingProcess) {
        Write-Host "Stopping process on port $Port (PID: $($existingProcess.Id))..."
        $existingProcess | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

Push-Location $RepoRoot
try {
    if ($Foreground) {
        & $PythonCmd @PythonArgs
    }
    else {
        Start-Process -FilePath $PythonCmd -ArgumentList $PythonArgs -WorkingDirectory $RepoRoot | Out-Null
        Start-Sleep -Seconds 2
        if (-not $NoOpen) {
            Start-Process "http://127.0.0.1:$Port/"
        }
        Write-Host "Azure Architecture Factory portal started. Open http://127.0.0.1:$Port/ if needed."
    }
}
finally {
    Pop-Location
}
