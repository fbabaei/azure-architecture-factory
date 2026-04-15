<#
.SYNOPSIS
    Start the Azure Architecture Factory portal monitor agent.

.DESCRIPTION
    Runs portal_monitor.py, which watches the local and (optionally) a deployed
    portal, auto-restarts the local portal when it goes down, and raises Windows
    balloon-tip alerts.

.PARAMETER DeployedUrl
    Optional URL of the deployed portal to also monitor.
    e.g.  -DeployedUrl "https://my-factory.azurecontainerapps.io"

.PARAMETER Interval
    Check interval in seconds (default: 30).

.PARAMETER MaxFailures
    Consecutive failed checks before a restart is triggered (default: 2).

.PARAMETER Foreground
    Run the monitor in the current console window (blocks). Omit to run hidden.

.EXAMPLE
    .\scripts\start_monitor.ps1
    .\scripts\start_monitor.ps1 -DeployedUrl "https://my-factory.azurecontainerapps.io" -Interval 60
    .\scripts\start_monitor.ps1 -Foreground
#>
Param(
    [Parameter(Mandatory = $false)]
    [string]$DeployedUrl = "",

    [Parameter(Mandatory = $false)]
    [int]$Interval = 30,

    [Parameter(Mandatory = $false)]
    [int]$MaxFailures = 2,

    [Parameter(Mandatory = $false)]
    [switch]$Foreground
)

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = Split-Path -Parent $ScriptDir
$MonitorScript = Join-Path $ScriptDir "portal_monitor.py"
$VenvPython  = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $MonitorScript)) {
    Write-Error "Could not find scripts/portal_monitor.py"
    exit 1
}

if (Test-Path $VenvPython) {
    $PythonCmd = $VenvPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} else {
    Write-Error "Python not found. Create .venv or install Python."
    exit 1
}

# Build environment for the child process
$env:MONITOR_INTERVAL   = $Interval
$env:MONITOR_MAX_FAILURES = $MaxFailures
if ($DeployedUrl -ne "") {
    $env:FACTORY_DEPLOYED_URL = $DeployedUrl
}

Write-Host "Starting portal monitor (interval=${Interval}s, max-failures=${MaxFailures}) ..."
if ($DeployedUrl) {
    Write-Host "  Also watching deployed portal: $DeployedUrl"
}

if ($Foreground) {
    & $PythonCmd $MonitorScript
} else {
    # Kill any existing monitor process to avoid duplicates
    $existingMonitors = Get-WmiObject Win32_Process -Filter "CommandLine LIKE '%portal_monitor.py%'" -ErrorAction SilentlyContinue
    foreach ($proc in $existingMonitors) {
        Write-Host "Stopping existing monitor (PID $($proc.ProcessId)) ..."
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }

    Start-Process `
        -FilePath $PythonCmd `
        -ArgumentList @($MonitorScript) `
        -WindowStyle Hidden `
        -WorkingDirectory $RepoRoot

    Write-Host "Portal monitor running in background."
    Write-Host "To stop it: Get-Process python | Where-Object { `$_.CommandLine -like '*portal_monitor*' } | Stop-Process -Force"
}
