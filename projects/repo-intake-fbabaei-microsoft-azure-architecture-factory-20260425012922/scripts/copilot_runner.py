"""
Copilot CLI runner for the AAF portal.

Spawns the GitHub Copilot CLI (`@github/copilot`) as a background subprocess
bounded to a specific project directory. Writes session artifacts under the
project's own ``outputs/copilot/<runId>/`` folder so that runs are discoverable
alongside other generated artifacts.

Design notes
------------
- One subprocess per run (``copilot -p <prompt>`` non-interactive mode).
- ``cwd`` is locked to the project root so Copilot can only touch files inside
  that project.
- stdout+stderr are captured into ``session.log``; a ``metadata.json`` file
  records prompt / status / timestamps for the UI.
- An in-memory registry is intentionally avoided: the filesystem IS the
  registry. This keeps the portal restart-safe and lets the UI recover state
  on reload.

Configuration env vars
----------------------
``COPILOT_CLI_BIN``         Path or command name for the Copilot CLI (default
                            ``copilot``). Override with an absolute path when
                            the CLI is installed somewhere ``PATH`` won't find.
``COPILOT_CLI_DENY_TOOLS``  Comma-separated list of ``--deny-tool`` patterns
                            passed on every run (default blocks shell ``git
                            push``, ``rm -rf``, and package publish commands).
``COPILOT_CLI_ALLOW_TOOLS`` Comma-separated list of ``--allow-tool`` patterns
                            (default ``write``,``shell`` — Copilot still
                            respects user deny rules).
``COPILOT_CLI_MAX_PROMPT``  Max prompt length in characters (default 8000).
``COPILOT_CLI_TIMEOUT_SEC`` Hard kill timeout in seconds (default 1800 = 30m).
``COPILOT_CLI_MAX_PARALLEL`` Max concurrent runs per project (default 2).
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Iterable

logger = logging.getLogger(__name__)

UTC = timezone.utc


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


# --- configuration ---------------------------------------------------------

COPILOT_CLI_BIN: str = os.environ.get("COPILOT_CLI_BIN", "").strip() or "copilot"

_DEFAULT_DENY_TOOLS = [
    "shell(git push*)",
    "shell(rm -rf*)",
    "shell(npm publish*)",
    "shell(pnpm publish*)",
    "shell(yarn publish*)",
    "shell(gh release*)",
    "shell(az logout*)",
]

_DEFAULT_ALLOW_TOOLS = ["write", "shell"]


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _resolved_deny_tools() -> list[str]:
    override = _split_csv(os.environ.get("COPILOT_CLI_DENY_TOOLS"))
    return override or list(_DEFAULT_DENY_TOOLS)


def _resolved_allow_tools() -> list[str]:
    override = _split_csv(os.environ.get("COPILOT_CLI_ALLOW_TOOLS"))
    return override or list(_DEFAULT_ALLOW_TOOLS)


def _max_prompt_chars() -> int:
    try:
        return max(100, int(os.environ.get("COPILOT_CLI_MAX_PROMPT", "8000")))
    except ValueError:
        return 8000


def _timeout_sec() -> int:
    try:
        return max(60, int(os.environ.get("COPILOT_CLI_TIMEOUT_SEC", "1800")))
    except ValueError:
        return 1800


def _max_parallel() -> int:
    try:
        return max(1, int(os.environ.get("COPILOT_CLI_MAX_PARALLEL", "2")))
    except ValueError:
        return 2


# --- availability ----------------------------------------------------------

def is_available() -> bool:
    """Return True when the Copilot CLI binary resolves on PATH."""
    return shutil.which(COPILOT_CLI_BIN) is not None


def cli_version() -> str | None:
    """Return ``copilot --version`` output, or None when unavailable."""
    if not is_available():
        return None
    try:
        out = subprocess.run(
            [COPILOT_CLI_BIN, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return (out.stdout or out.stderr).strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


# --- run directory layout --------------------------------------------------

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _runs_root(project_root: pathlib.Path) -> pathlib.Path:
    return project_root / "outputs" / "copilot"


def _run_dir(project_root: pathlib.Path, run_id: str) -> pathlib.Path | None:
    if not _RUN_ID_RE.fullmatch(run_id):
        return None
    root = _runs_root(project_root).resolve()
    candidate = (root / run_id).resolve()
    if root not in candidate.parents and candidate != root:
        return None
    return candidate


def _new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]


# --- metadata I/O ----------------------------------------------------------

def _metadata_path(run_dir: pathlib.Path) -> pathlib.Path:
    return run_dir / "metadata.json"


def _log_path(run_dir: pathlib.Path) -> pathlib.Path:
    return run_dir / "session.log"


def _read_metadata(run_dir: pathlib.Path) -> dict | None:
    try:
        raw = _metadata_path(run_dir).read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_metadata(run_dir: pathlib.Path, metadata: dict) -> None:
    try:
        _metadata_path(run_dir).write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to write metadata for %s: %s", run_dir.name, exc)


def _refresh_status(run_dir: pathlib.Path, metadata: dict) -> dict:
    """Re-check PID liveness and update status to ``succeeded``/``failed``/``timeout``."""
    status = metadata.get("status")
    if status in {"succeeded", "failed", "timeout", "cancelled"}:
        return metadata

    pid = metadata.get("pid")
    started_at = metadata.get("startedAt")
    if not pid:
        return metadata

    if _pid_alive(int(pid)):
        # Still running. Honor hard timeout.
        if started_at:
            try:
                started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                age = (datetime.now(tz=UTC) - started).total_seconds()
                if age > _timeout_sec():
                    _terminate_pid(int(pid))
                    metadata["status"] = "timeout"
                    metadata["finishedAt"] = _utcnow_iso()
                    metadata["note"] = f"Killed after {int(age)}s > timeout {_timeout_sec()}s."
                    _write_metadata(run_dir, metadata)
            except ValueError:
                pass
        return metadata

    # PID not alive anymore. Determine outcome from exit-code sentinel file.
    exit_code_file = run_dir / "exit.code"
    exit_code: int | None = None
    try:
        if exit_code_file.is_file():
            exit_code = int(exit_code_file.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        exit_code = None

    if exit_code == 0:
        metadata["status"] = "succeeded"
    elif exit_code is None:
        metadata["status"] = "unknown"
    else:
        metadata["status"] = "failed"
    metadata["exitCode"] = exit_code
    metadata.setdefault("finishedAt", _utcnow_iso())
    _write_metadata(run_dir, metadata)
    return metadata


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            # On Windows, os.kill raises OSError if process doesn't exist.
            os.kill(pid, 0)
            return True
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _terminate_pid(pid: int) -> None:
    try:
        if os.name == "nt":
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


# --- public API ------------------------------------------------------------

class CopilotRunError(Exception):
    """Raised when a run cannot be started (validation / preflight failure)."""


def start_run(
    project_root: pathlib.Path,
    prompt: str,
    *,
    requested_by: str | None = None,
    extra_env: dict[str, str] | None = None,
    model: str | None = None,
    session_id: str | None = None,
    mcp_config_path: str | None = None,
    agent: str | None = None,
) -> dict:
    """Spawn a Copilot CLI run for ``project_root`` and return its metadata.

    Optional args:
      model: passed as ``--model <name>`` (e.g. ``claude-sonnet-4.5``).
      session_id: passed as ``--resume=<uuid>``. When a run with this session_id
        has been spawned before, Copilot resumes it; otherwise a new session
        is created with that UUID. If None, a new UUID is minted per run.
      mcp_config_path: path to an MCP config JSON. Passed via
        ``--additional-mcp-config @<path>``.
      agent: custom agent name (e.g. ``brd-to-architecture-diagram``). Passed
        via ``--agent <name>``.
    """
    if not is_available():
        raise CopilotRunError(
            f"Copilot CLI '{COPILOT_CLI_BIN}' is not installed on the portal host."
        )

    prompt = (prompt or "").strip()
    if not prompt:
        raise CopilotRunError("Prompt is required.")
    if len(prompt) > _max_prompt_chars():
        raise CopilotRunError(f"Prompt exceeds max length ({_max_prompt_chars()} chars).")

    # Enforce per-project concurrency cap.
    active = [r for r in list_runs(project_root) if r.get("status") == "running"]
    if len(active) >= _max_parallel():
        raise CopilotRunError(
            f"Too many active Copilot runs for this project ({len(active)}). "
            f"Wait for one to finish or cancel it."
        )

    run_id = _new_run_id()
    run_dir = _runs_root(project_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    deny_tools = _resolved_deny_tools()
    allow_tools = _resolved_allow_tools()

    # Resolve full path so Windows picks up .cmd/.bat shims from npm global.
    resolved_bin = shutil.which(COPILOT_CLI_BIN) or COPILOT_CLI_BIN

    # Session ID: caller-provided (to resume) or freshly minted (new chain).
    effective_session_id = (session_id or "").strip() or str(uuid.uuid4())

    cmd: list[str] = [resolved_bin, "-p", prompt, "--no-color"]
    # --resume=<uuid> starts or resumes a session with that exact UUID.
    cmd.extend([f"--resume={effective_session_id}"])
    if model:
        cmd.extend(["--model", model])
    if agent:
        cmd.extend(["--agent", agent])
    # MCP config: caller-provided path → auto-discover in project or repo root.
    mcp_path = _resolve_mcp_config(project_root, mcp_config_path)
    if mcp_path:
        cmd.extend(["--additional-mcp-config", f"@{mcp_path}"])
    for t in allow_tools:
        cmd.extend(["--allow-tool", t])
    for t in deny_tools:
        cmd.extend(["--deny-tool", t])

    # Environment: inherit, then merge overrides. GITHUB_TOKEN / COPILOT auth
    # is expected to already be present on the portal host.
    env = os.environ.copy()
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items() if v is not None})

    # Force Copilot to consider this a fresh session dir.
    env.setdefault("COPILOT_LOG_DIR", str(run_dir))
    env.setdefault("NO_COLOR", "1")

    log_file = _log_path(run_dir)
    prompt_file = run_dir / "prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    metadata = {
        "runId": run_id,
        "status": "running",
        "prompt": prompt,
        "projectSlug": project_root.name,
        "startedAt": _utcnow_iso(),
        "requestedBy": requested_by or "",
        "cmd": cmd,
        "allowTools": allow_tools,
        "denyTools": deny_tools,
        "timeoutSec": _timeout_sec(),
        "sessionId": effective_session_id,
        "model": model or "",
        "mcpConfigPath": mcp_path or "",
        "agent": agent or "",
    }

    try:
        log_handle = log_file.open("ab", buffering=0)
    except OSError as exc:
        raise CopilotRunError(f"Failed to open log file: {exc}") from exc

    # Header block so the UI can render a friendly preamble.
    header = (
        f"# Copilot run {run_id}\n"
        f"# project: {project_root.name}\n"
        f"# started: {metadata['startedAt']}\n"
        f"# requestedBy: {metadata['requestedBy']}\n"
        f"# cmd: {' '.join(cmd[:3])} ... ({len(cmd)} args)\n"
        f"# allowTools: {','.join(allow_tools)}\n"
        f"# denyTools: {','.join(deny_tools)}\n"
        f"# --- stdout+stderr below ---\n"
    ).encode("utf-8")
    log_handle.write(header)

    try:
        popen_kwargs: dict = {
            "cwd": str(project_root),
            "env": env,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **popen_kwargs)
    except (OSError, ValueError) as exc:
        log_handle.close()
        raise CopilotRunError(f"Failed to launch Copilot CLI: {exc}") from exc

    metadata["pid"] = proc.pid
    _write_metadata(run_dir, metadata)

    # Reaper thread: waits for exit, writes exit.code, closes log handle.
    threading.Thread(
        target=_reap_process,
        args=(proc, run_dir, log_handle),
        name=f"copilot-reaper-{run_id}",
        daemon=True,
    ).start()

    return metadata


def _reap_process(
    proc: subprocess.Popen,
    run_dir: pathlib.Path,
    log_handle,
) -> None:
    try:
        exit_code = proc.wait()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Copilot reaper error in %s: %s", run_dir.name, exc)
        exit_code = -1
    finally:
        try:
            log_handle.close()
        except OSError:
            pass
    try:
        (run_dir / "exit.code").write_text(str(exit_code), encoding="utf-8")
    except OSError:
        pass
    metadata = _read_metadata(run_dir) or {}
    metadata["exitCode"] = exit_code
    metadata["finishedAt"] = _utcnow_iso()
    if metadata.get("status") not in {"cancelled", "timeout"}:
        metadata["status"] = "succeeded" if exit_code == 0 else "failed"
    _write_metadata(run_dir, metadata)


def list_runs(project_root: pathlib.Path) -> list[dict]:
    """Return newest-first list of runs with status refreshed."""
    runs_root = _runs_root(project_root)
    if not runs_root.is_dir():
        return []
    out: list[dict] = []
    for child in sorted(runs_root.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        md = _read_metadata(child)
        if not md:
            continue
        md = _refresh_status(child, md)
        # Don't leak the full cmd array or env in list responses — keep it lean.
        out.append({
            "runId": md.get("runId") or child.name,
            "status": md.get("status", "unknown"),
            "prompt": md.get("prompt", ""),
            "startedAt": md.get("startedAt"),
            "finishedAt": md.get("finishedAt"),
            "exitCode": md.get("exitCode"),
            "requestedBy": md.get("requestedBy"),
            "sessionId": md.get("sessionId"),
            "model": md.get("model") or "",
            "agent": md.get("agent") or "",
        })
    return out


def get_run(project_root: pathlib.Path, run_id: str) -> dict | None:
    run_dir = _run_dir(project_root, run_id)
    if run_dir is None or not run_dir.is_dir():
        return None
    md = _read_metadata(run_dir)
    if not md:
        return None
    return _refresh_status(run_dir, md)


def read_log_tail(project_root: pathlib.Path, run_id: str, max_bytes: int = 64_000) -> str | None:
    run_dir = _run_dir(project_root, run_id)
    if run_dir is None:
        return None
    path = _log_path(run_dir)
    if not path.is_file():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(-max_bytes, 2)
                data = b"... [truncated, showing last %d bytes] ...\n" % max_bytes
                data += fh.read()
            else:
                data = fh.read()
        return data.decode("utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read log %s: %s", path, exc)
        return None


def cancel_run(project_root: pathlib.Path, run_id: str) -> dict | None:
    run_dir = _run_dir(project_root, run_id)
    if run_dir is None or not run_dir.is_dir():
        return None
    md = _read_metadata(run_dir)
    if not md:
        return None
    if md.get("status") != "running":
        return _refresh_status(run_dir, md)
    pid = md.get("pid")
    if pid:
        _terminate_pid(int(pid))
    md["status"] = "cancelled"
    md["finishedAt"] = _utcnow_iso()
    _write_metadata(run_dir, md)
    return md


def runtime_info() -> dict:
    """Portal-exposed info: installed? version? concurrency caps?"""
    return {
        "available": is_available(),
        "bin": COPILOT_CLI_BIN,
        "version": cli_version(),
        "maxPromptChars": _max_prompt_chars(),
        "timeoutSec": _timeout_sec(),
        "maxParallel": _max_parallel(),
        "allowTools": _resolved_allow_tools(),
        "denyTools": _resolved_deny_tools(),
        "supportedModels": _supported_models(),
    }


# --- MCP config discovery --------------------------------------------------

_MCP_CANDIDATES = (
    ".copilot/mcp-config.json",
    ".github/copilot/mcp-config.json",
)


def _resolve_mcp_config(
    project_root: pathlib.Path,
    explicit: str | None,
) -> str | None:
    """Return the MCP config path to pass to Copilot, if any.

    Preference order:
      1. caller-provided ``explicit`` path (must exist and be a file).
      2. ``<project_root>/.copilot/mcp-config.json`` (and alt).
      3. repo-root equivalents (walking up from project_root until we find a .git).
    """
    if explicit:
        p = pathlib.Path(explicit)
        if p.is_file():
            return str(p.resolve())
        return None

    for name in _MCP_CANDIDATES:
        p = project_root / name
        if p.is_file():
            return str(p.resolve())

    # Walk up to the repo root looking for .git, then check for config there.
    cur = project_root.resolve()
    for _ in range(6):
        if (cur / ".git").exists():
            for name in _MCP_CANDIDATES:
                p = cur / name
                if p.is_file():
                    return str(p.resolve())
            break
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _supported_models() -> list[str]:
    """Return the list of models surfaced in the portal UI picker.

    This is a UX hint only — the CLI accepts any model name the user's plan
    supports. Override with ``COPILOT_CLI_MODELS`` env var (comma-separated).
    """
    override = _split_csv(os.environ.get("COPILOT_CLI_MODELS"))
    if override:
        return override
    return [
        "claude-sonnet-4.5",
        "claude-opus-4.5",
        "claude-haiku-4.5",
        "gpt-5.2",
        "gpt-5.2-codex",
        "gpt-5-mini",
    ]


# --- git diff --------------------------------------------------------------

def diff_run(
    project_root: pathlib.Path,
    run_id: str,
    max_bytes: int = 200_000,
) -> dict | None:
    """Return a git diff summary of files changed since the run started.

    Uses git at the repo root. Filters to files under ``project_root`` so the
    output is scoped to the run's project. Returns None when run_id is invalid
    or git is unavailable.
    """
    run_dir = _run_dir(project_root, run_id)
    if run_dir is None or not run_dir.is_dir():
        return None
    md = _read_metadata(run_dir)
    if not md:
        return None

    # Find repo root by walking up from the project_root.
    repo_root = project_root.resolve()
    for _ in range(6):
        if (repo_root / ".git").exists():
            break
        if repo_root.parent == repo_root:
            return {"runId": run_id, "error": "Not inside a git repo.", "files": [], "patch": ""}
        repo_root = repo_root.parent
    else:
        return {"runId": run_id, "error": "Not inside a git repo.", "files": [], "patch": ""}

    # Path prefix git should scope to, relative to repo root.
    try:
        rel_prefix = project_root.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        rel_prefix = ""

    def _git(args: list[str]) -> tuple[int, str]:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=20,
            )
            return out.returncode, (out.stdout or "") + (out.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return -1, str(exc)

    name_args = ["diff", "--name-status", "HEAD", "--"]
    patch_args = ["diff", "HEAD", "--"]
    if rel_prefix:
        name_args.append(rel_prefix)
        patch_args.append(rel_prefix)

    rc_names, names_out = _git(name_args)
    if rc_names != 0:
        return {"runId": run_id, "error": names_out.strip(), "files": [], "patch": ""}

    files: list[dict] = []
    for line in names_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            files.append({"status": parts[0], "path": parts[1]})

    rc_patch, patch_out = _git(patch_args)
    if rc_patch != 0:
        patch_out = patch_out or ""
    truncated = False
    if len(patch_out) > max_bytes:
        patch_out = patch_out[:max_bytes] + f"\n... [truncated at {max_bytes} bytes] ...\n"
        truncated = True

    # Include untracked files under the project path (new files Copilot wrote).
    ls_args = ["ls-files", "--others", "--exclude-standard"]
    if rel_prefix:
        ls_args.append("--")
        ls_args.append(rel_prefix)
    rc_ls, ls_out = _git(ls_args)
    if rc_ls == 0:
        existing = {f["path"] for f in files}
        for line in ls_out.splitlines():
            line = line.strip()
            if line and line not in existing:
                files.append({"status": "??", "path": line})

    return {
        "runId": run_id,
        "repoRoot": str(repo_root),
        "projectPrefix": rel_prefix,
        "files": files,
        "patch": patch_out,
        "truncated": truncated,
    }


# --- agent discovery -------------------------------------------------------

_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")


def list_agents(search_root: pathlib.Path) -> list[dict]:
    """Discover custom Copilot agents under ``<search_root>/.github/agents/``.

    Returns a list of ``{"name", "path", "description"}`` entries. ``name`` is
    the file stem with any trailing ``.agent`` suffix removed, which matches
    what the Copilot CLI expects for ``--agent <name>``. ``description`` is
    parsed from YAML front-matter when present.
    """
    agents: list[dict] = []
    base = (search_root / ".github" / "agents").resolve()
    if not base.is_dir():
        return agents

    for path in sorted(base.glob("*.agent.md")):
        stem = path.name
        if stem.endswith(".agent.md"):
            name = stem[: -len(".agent.md")]
        else:
            name = path.stem
        if not _AGENT_NAME_RE.fullmatch(name):
            continue
        description = _extract_agent_description(path)
        agents.append({
            "name": name,
            "path": str(path.relative_to(search_root)) if path.is_relative_to(search_root) else str(path),
            "description": description,
        })
    return agents


def _extract_agent_description(path: pathlib.Path) -> str:
    """Read YAML front-matter ``description`` or fall back to first heading."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    if not lines:
        return ""
    if lines[0].strip() == "---":
        for i in range(1, min(len(lines), 40)):
            line = lines[i]
            if line.strip() == "---":
                break
            m = re.match(r'^\s*description\s*:\s*"?(.+?)"?\s*$', line)
            if m:
                return m.group(1).strip()
    # Fall back to the first non-empty, non-front-matter line.
    for line in lines:
        s = line.strip().lstrip("#").strip()
        if s and not s.startswith("---"):
            return s[:200]
    return ""
