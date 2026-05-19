# Portal Monitor Agent – User Guide

> **Scope:** Local developer tooling. This document is stored under `scripts/docs/` and is intentionally blocked from being served by any portal. It is for developer reference only.

---

## Overview

`portal_monitor.py` is a background agent that watches the Azure Architecture Factory portals and takes automatic recovery actions when a portal goes down.

| Feature | Details |
|---|---|
| **Local portal monitoring** | Checks `http://127.0.0.1:5501/` every N seconds |
| **Deployed portal monitoring** | Optionally checks any HTTPS URL (Azure Container Apps, App Service, etc.) |
| **Auto-restart** | Runs `start_factory_portal_from_anywhere.ps1` if the local portal fails |
| **Windows alerts** | Balloon-tip notifications on status changes (down, recovery, restart) |
| **No extra packages** | Uses only Python standard library + PowerShell WinForms for notifications |

---

## Quick Start

### Start monitor in the background (default)
```powershell
.\scripts\start_monitor.ps1
```

### Also watch a deployed portal
```powershell
.\scripts\start_monitor.ps1 -DeployedUrl "https://my-factory.azurecontainerapps.io"
```

### Run in the foreground (see live log output)
```powershell
.\scripts\start_monitor.ps1 -Foreground
```

### Custom interval and sensitivity
```powershell
.\scripts\start_monitor.ps1 -Interval 60 -MaxFailures 3
```

---

## Configuration

All settings can be overridden via environment variables before launching the script.

| Variable | Default | Description |
|---|---|---|
| `FACTORY_PORTAL_PORT` | `5501` | Local portal port |
| `FACTORY_DEPLOYED_URL` | _(empty)_ | Deployed portal URL to monitor (optional) |
| `MONITOR_INTERVAL` | `30` | Seconds between health checks |
| `MONITOR_TIMEOUT` | `10` | Per-request HTTP timeout in seconds |
| `MONITOR_MAX_FAILURES` | `2` | Consecutive failures before restart + alert |

### Setting an env var before starting

```powershell
$env:FACTORY_DEPLOYED_URL = "https://my-factory.azurecontainerapps.io"
$env:MONITOR_INTERVAL     = "60"
.\scripts\start_monitor.ps1
```

---

## How It Works

```
Every MONITOR_INTERVAL seconds
  ├── GET http://127.0.0.1:{PORT}/         (local portal)
  │     ├── HTTP < 500  →  mark UP, clear failure counter
  │     └── Error/5xx   →  increment failure counter
  │           └── failures >= MAX_FAILURES
  │                 ├── Windows balloon-tip: "Portal DOWN"
  │                 └── Run start_factory_portal_from_anywhere.ps1
  │                       ├── Success → balloon-tip: "Restart Triggered"
  │                       └── Failure → balloon-tip: "Restart FAILED"
  │
  └── GET {FACTORY_DEPLOYED_URL}           (deployed portal, if configured)
        ├── HTTP < 500  →  mark UP
        └── Error/5xx   →  increment failure counter
              └── failures >= MAX_FAILURES
                    └── Windows balloon-tip: "Portal DOWN"
                        (no auto-restart for deployed portals)

When a portal recovers after being DOWN:
  └── Windows balloon-tip: "Portal Recovered"
```

---

## Notifications

All notifications appear as Windows balloon tips (system tray) using PowerShell `WinForms.NotifyIcon`. No third-party packages are required.

| Event | Icon | Title |
|---|---|---|
| Monitor started | Info | Portal Monitor Started |
| Portal down (after N failures) | Error | Portal DOWN |
| Auto-restart triggered | Warning | Portal Restart Triggered |
| Auto-restart failed | Error | Portal Restart FAILED |
| Portal recovered | Info | Portal Recovered |

---

## Stopping the Monitor

```powershell
# Find and stop background monitor
Get-Process python | Where-Object { $_.CommandLine -like '*portal_monitor*' } | Stop-Process -Force
```

Or simply close the terminal window if running with `-Foreground`.

---

## Files

| File | Purpose |
|---|---|
| `scripts/portal_monitor.py` | Core monitoring loop and recovery logic |
| `scripts/start_monitor.ps1` | PowerShell launcher (background or foreground) |
| `scripts/start_factory_portal_from_anywhere.ps1` | Portal start script (invoked on auto-restart) |
| `scripts/docs/portal_monitor.md` | This document |

---

## Troubleshooting

**No balloon tips appear**
- Ensure you are on Windows with notifications enabled (Settings > System > Notifications).
- Verify PowerShell can run scripts: `Get-ExecutionPolicy` should be `RemoteSigned` or `Bypass`.

**Monitor restarts portal but it keeps going down**
- Check for port conflict: `Get-NetTCPConnection -LocalPort 5501`
- Review portal log output by running the portal in foreground: `.\scripts\start_factory_portal_from_anywhere.ps1 -Foreground`

**Monitor exits immediately**
- Confirm Python is available: run `python --version` or check `.venv`.
- Run with `-Foreground` to see error output directly.

**Deployed URL always shows DOWN**
- Confirm the URL is reachable from your machine (VPN, firewall, CORS not required for HEAD/GET).
- Test manually: `Invoke-WebRequest -Uri $env:FACTORY_DEPLOYED_URL -Method Get`
