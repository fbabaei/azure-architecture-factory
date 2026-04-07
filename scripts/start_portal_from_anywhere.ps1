Param(
    [Parameter(Mandatory = $false)]
    [int]$Port = 5000,

    [Parameter(Mandatory = $false)]
    [switch]$NoOpen,

    [Parameter(Mandatory = $false)]
    [switch]$Foreground
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PortalScript = Join-Path $RepoRoot "demo\app.py"
$DemoDir = Join-Path $RepoRoot "demo"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PortalScript)) {
    Write-Error "Could not find demo/app.py."
    exit 1
}

if (Test-Path $VenvPython) {
    $PythonCmd = $VenvPython
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
}
else {
    Write-Error "Python was not found. Install Python or create .venv first."
    exit 1
}

$env:PYTHONPATH = $RepoRoot
$env:FLASK_DEBUG = "0"

Push-Location $DemoDir
try {
    if ($Foreground) {
        & $PythonCmd $PortalScript --port $Port
    }
    else {
        Start-Process -FilePath $PythonCmd -ArgumentList @($PortalScript, "--port", $Port) -WorkingDirectory $DemoDir | Out-Null
        Start-Sleep -Seconds 2
        if (-not $NoOpen) {
            Start-Process "http://127.0.0.1:$Port/"
        }
        Write-Host "Portal started in the background. Open http://127.0.0.1:$Port/ if needed."
    }
}
finally {
    Pop-Location
}
