#!/usr/bin/env python3
"""
Portal Monitor Agent
====================
Continuously monitors the local Azure Architecture Factory portal and an optional
deployed portal URL.  When a portal goes down it:
  1. Attempts to restart the local portal via start_factory_portal_from_anywhere.ps1
  2. Fires a Windows balloon-tip alert on the local machine

Configuration (environment variables):
  FACTORY_DEPLOYED_URL   – Deployed portal URL to also monitor (optional).
                           e.g. https://my-factory.azurecontainerapps.io
  FACTORY_PORTAL_PORT    – Local portal port (default: 5501)
  MONITOR_INTERVAL       – Check interval in seconds (default: 30)
  MONITOR_TIMEOUT        – Per-request timeout in seconds (default: 10)
  MONITOR_MAX_FAILURES   – Consecutive failures before restart (default: 2)

Usage:
  python scripts/portal_monitor.py
"""

import os
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_PORT = int(os.environ.get("FACTORY_PORTAL_PORT", "5501"))
LOCAL_URL = f"http://127.0.0.1:{LOCAL_PORT}/"
DEPLOYED_URL = os.environ.get("FACTORY_DEPLOYED_URL", "").strip()
CHECK_INTERVAL = int(os.environ.get("MONITOR_INTERVAL", "30"))
REQUEST_TIMEOUT = int(os.environ.get("MONITOR_TIMEOUT", "10"))
MAX_FAILURES = int(os.environ.get("MONITOR_MAX_FAILURES", "2"))
START_SCRIPT = REPO_ROOT / "scripts" / "start_factory_portal_from_anywhere.ps1"

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Windows notification (balloon tip via PowerShell – no extra packages needed)
# ---------------------------------------------------------------------------

def _notify(title: str, message: str, icon: str = "Warning") -> None:
    """Show a Windows balloon tip notification using PowerShell + WinForms."""
    icon_map = {"Info": "Information", "Warning": "Warning", "Error": "Error"}
    icon_name = icon_map.get(icon, "Warning")
    ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::{icon_name}
$n.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::{icon_name}
$n.BalloonTipTitle = '{_escape_ps(title)}'
$n.BalloonTipText  = '{_escape_ps(message)}'
$n.Visible = $true
$n.ShowBalloonTip(8000)
Start-Sleep -Seconds 9
$n.Dispose()
"""
    try:
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-WindowStyle", "Hidden",
             "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log(f"[notify] Could not show notification: {exc}")


def _escape_ps(text: str) -> str:
    """Escape single-quotes for PowerShell string injection."""
    return text.replace("'", "''")


# ---------------------------------------------------------------------------
# Portal health check
# ---------------------------------------------------------------------------

def _is_up(url: str) -> tuple[bool, str]:
    """Return (is_up, reason)."""
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status < 500:
                return True, f"HTTP {resp.status}"
            return False, f"HTTP {resp.status}"
    except HTTPError as exc:
        # 4xx are still "up" (server responded)
        if exc.code < 500:
            return True, f"HTTP {exc.code}"
        return False, f"HTTP {exc.code}"
    except URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Local portal restart
# ---------------------------------------------------------------------------

def _restart_local() -> bool:
    """Attempt to restart the local portal; return True on success."""
    if not START_SCRIPT.exists():
        log(f"[restart] Script not found: {START_SCRIPT}")
        return False
    log("[restart] Launching start_factory_portal_from_anywhere.ps1 ...")
    result = subprocess.run(
        ["powershell", "-NonInteractive", "-File", str(START_SCRIPT), "-NoOpen"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        log("[restart] Portal start script completed successfully.")
        return True
    log(f"[restart] Script exited {result.returncode}: {result.stderr.strip()}")
    return False


# ---------------------------------------------------------------------------
# Monitor state per endpoint
# ---------------------------------------------------------------------------

class EndpointMonitor:
    def __init__(self, url: str, label: str, is_local: bool = False):
        self.url = url
        self.label = label
        self.is_local = is_local
        self.failures = 0
        self.last_status: bool | None = None   # None = unknown (first check)
        self.restart_attempted = False

    def check(self) -> None:
        up, reason = _is_up(self.url)

        if up:
            if self.last_status is False:
                msg = f"{self.label} is back ONLINE ({self.url})"
                log(f"[UP]   {msg}")
                _notify("Portal Recovered", msg, icon="Info")
            elif self.last_status is None:
                log(f"[UP]   {self.label} is UP | {reason}")
            self.failures = 0
            self.restart_attempted = False
            self.last_status = True
        else:
            self.failures += 1
            log(f"[DOWN] {self.label} – {reason} (failure {self.failures}/{MAX_FAILURES})")

            if self.failures >= MAX_FAILURES:
                alert_msg = (
                    f"{self.label} is DOWN after {self.failures} checks.\n"
                    f"URL: {self.url}\nReason: {reason}"
                )
                _notify("Portal DOWN", alert_msg, icon="Error")

                if self.is_local and not self.restart_attempted:
                    self.restart_attempted = True
                    log("[action] Attempting local portal restart ...")
                    ok = _restart_local()
                    if ok:
                        _notify(
                            "Portal Restart Triggered",
                            f"{self.label} restart has been initiated.\n"
                            f"Waiting {CHECK_INTERVAL}s for it to come up ...",
                            icon="Warning",
                        )
                        # Give it time to start before next check
                        time.sleep(min(CHECK_INTERVAL, 15))
                    else:
                        _notify(
                            "Portal Restart FAILED",
                            f"Could not restart {self.label}. Manual intervention required.",
                            icon="Error",
                        )

                self.last_status = False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    log("=" * 60)
    log("Azure Architecture Factory – Portal Monitor")
    log(f"  Local portal : {LOCAL_URL}")
    if DEPLOYED_URL:
        log(f"  Deployed URL : {DEPLOYED_URL}")
    else:
        log("  Deployed URL : (not configured – set FACTORY_DEPLOYED_URL)")
    log(f"  Check interval : {CHECK_INTERVAL}s | Timeout: {REQUEST_TIMEOUT}s | Max failures: {MAX_FAILURES}")
    log("=" * 60)

    monitors: list[EndpointMonitor] = [
        EndpointMonitor(LOCAL_URL, "Local Portal", is_local=True),
    ]
    if DEPLOYED_URL:
        monitors.append(EndpointMonitor(DEPLOYED_URL, "Deployed Portal", is_local=False))

    _notify(
        "Portal Monitor Started",
        f"Monitoring {len(monitors)} portal(s) every {CHECK_INTERVAL}s.",
        icon="Info",
    )

    while True:
        for m in monitors:
            try:
                m.check()
            except Exception as exc:
                log(f"[error] Unexpected error checking {m.label}: {exc}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Monitor stopped by user.")
        sys.exit(0)
