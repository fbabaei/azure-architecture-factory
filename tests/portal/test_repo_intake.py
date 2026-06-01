"""Tests for repo intake helper functions.

These tests cover URL validation, branch-suffix sanitisation, PAT masking,
and the Markdown report builder — all without performing any real git operations.
"""
from __future__ import annotations

import io
import pathlib
import shutil
from types import SimpleNamespace

import pytest
import start_factory_portal as portal


# ── URL validation ─────────────────────────────────────────────────────────


def test_validate_repo_url_github() -> None:
    url, err = portal._validate_repo_url("https://github.com/owner/repo")
    assert err is None
    assert url == "https://github.com/owner/repo"


def test_validate_repo_url_ado() -> None:
    url, err = portal._validate_repo_url("https://dev.azure.com/org/project/_git/repo")
    assert err is None
    assert "dev.azure.com" in url


def test_validate_repo_url_rejects_http() -> None:
    url, err = portal._validate_repo_url("http://github.com/owner/repo")
    assert url == ""
    assert err is not None
    assert "https" in err.lower()


def test_validate_repo_url_rejects_unknown_host() -> None:
    url, err = portal._validate_repo_url("https://gitlab.com/owner/repo")
    assert url == ""
    assert err is not None
    assert "gitlab.com" in err


def test_validate_repo_url_strips_embedded_credentials() -> None:
    url, err = portal._validate_repo_url("https://x-oauth-basic:ghp_abc123@github.com/owner/repo")
    assert err is None
    assert "@" not in url
    assert "ghp_abc123" not in url


def test_validate_repo_url_rejects_empty() -> None:
    url, err = portal._validate_repo_url("")
    assert url == ""
    assert err is not None


def test_validate_repo_url_rejects_non_url() -> None:
    url, err = portal._validate_repo_url("not-a-url-at-all")
    assert url == ""
    assert err is not None


def test_validate_local_repo_path_accepts_git_directory(tmp_path: pathlib.Path) -> None:
    repo_dir = tmp_path / "local-repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    path, err = portal._validate_local_repo_path(str(repo_dir))
    assert err is None
    assert path == repo_dir.resolve()


def test_validate_local_repo_path_rejects_non_git_directory(tmp_path: pathlib.Path) -> None:
    repo_dir = tmp_path / "not-a-repo"
    repo_dir.mkdir()
    path, err = portal._validate_local_repo_path(str(repo_dir))
    assert path is None
    assert err is not None
    assert ".git" in err


# ── Branch suffix sanitisation ─────────────────────────────────────────────


def test_sanitize_branch_suffix_valid() -> None:
    suffix, err = portal._sanitize_branch_suffix("analysis-2026")
    assert err is None
    assert suffix == "analysis-2026"


def test_sanitize_branch_suffix_with_dots_underscores() -> None:
    suffix, err = portal._sanitize_branch_suffix("feat.my_branch-01")
    assert err is None
    assert suffix == "feat.my_branch-01"


def test_sanitize_branch_suffix_too_long() -> None:
    _, err = portal._sanitize_branch_suffix("a" * 51)
    assert err is not None
    assert "50" in err


def test_sanitize_branch_suffix_invalid_chars_space() -> None:
    _, err = portal._sanitize_branch_suffix("my branch")
    assert err is not None


def test_sanitize_branch_suffix_invalid_starts_with_hyphen() -> None:
    _, err = portal._sanitize_branch_suffix("-invalid-start")
    assert err is not None


def test_sanitize_branch_suffix_empty() -> None:
    _, err = portal._sanitize_branch_suffix("")
    assert err is not None


def test_sanitize_repo_workflow_mode_defaults_to_analysis_only() -> None:
    mode, err = portal._sanitize_repo_workflow_mode(None)
    assert err is None
    assert mode == "analysis-only"


def test_sanitize_repo_workflow_mode_accepts_implement_pr() -> None:
    mode, err = portal._sanitize_repo_workflow_mode("implement-pr")
    assert err is None
    assert mode == "implement-pr"


def test_sanitize_repo_workflow_mode_rejects_unknown_value() -> None:
    _, err = portal._sanitize_repo_workflow_mode("ship-it")
    assert err is not None


def test_sanitize_repo_automation_goal_accepts_empty() -> None:
    goal, err = portal._sanitize_repo_automation_goal("")
    assert err is None
    assert goal == ""


def test_sanitize_repo_automation_goal_rejects_too_long() -> None:
    _, err = portal._sanitize_repo_automation_goal("x" * 5000)
    assert err is not None


# ── PAT masking ────────────────────────────────────────────────────────────


def test_mask_pat_in_text_github() -> None:
    text = "https://x-oauth-basic:ghp_supersecret@github.com/owner/repo"
    masked = portal._mask_pat_in_text(text)
    assert "ghp_supersecret" not in masked
    assert "***@" in masked


def test_mask_pat_in_text_ado() -> None:
    text = "error: authentication failed https://pat:ado_token123@dev.azure.com/org/proj"
    masked = portal._mask_pat_in_text(text)
    assert "ado_token123" not in masked
    assert "***@" in masked


def test_mask_pat_in_text_no_creds_unchanged() -> None:
    text = "No credentials in this string"
    assert portal._mask_pat_in_text(text) == text


def test_mask_pat_in_text_multiple() -> None:
    text = "https://tok@github.com and https://other@dev.azure.com"
    masked = portal._mask_pat_in_text(text)
    assert masked.count("***@") == 2
    assert "tok" not in masked
    assert "other" not in masked


# ── make_authed_clone_url ──────────────────────────────────────────────────


def test_make_authed_clone_url_github() -> None:
    result = portal._make_authed_clone_url("https://github.com/owner/repo", "mytoken")
    assert "mytoken" in result
    assert "x-oauth-basic" in result
    assert "github.com" in result


def test_make_authed_clone_url_ado() -> None:
    result = portal._make_authed_clone_url(
        "https://dev.azure.com/org/project/_git/repo", "mytoken"
    )
    assert "mytoken" in result
    assert "dev.azure.com" in result


# ── Report builder ─────────────────────────────────────────────────────────


def _mock_analysis() -> dict:
    return {
        "readme": "# My Project\n\nA sample project.",
        "arch_files": [],
        "tech_stack": ["package.json", "requirements.txt"],
        "file_counts": {"TypeScript": 42, "Python": 7, "Markdown": 5},
        "dir_tree": ["src", "tests", "docs", "README.md"],
    }


def test_build_repo_analysis_report_has_required_sections() -> None:
    report = portal._build_repo_analysis_report(
        "https://github.com/owner/repo",
        "AAF-analysis-2026",
        _mock_analysis(),
    )
    assert "# Repository Analysis Report" in report
    assert "**Repository**" in report
    assert "**Branch**" in report
    assert "AAF-analysis-2026" in report
    assert "## Repository Structure" in report
    assert "## Tech Stack Detected" in report
    assert "## Code Inventory" in report
    assert "README Summary" in report


def test_build_repo_analysis_report_includes_tech_stack() -> None:
    report = portal._build_repo_analysis_report(
        "https://github.com/owner/repo", "AAF-test", _mock_analysis()
    )
    assert "package.json" in report
    assert "requirements.txt" in report


def test_build_repo_analysis_report_includes_file_counts() -> None:
    report = portal._build_repo_analysis_report(
        "https://github.com/owner/repo", "AAF-test", _mock_analysis()
    )
    assert "TypeScript" in report
    assert "42" in report


def test_build_repo_analysis_report_includes_dir_tree() -> None:
    report = portal._build_repo_analysis_report(
        "https://github.com/owner/repo", "AAF-test", _mock_analysis()
    )
    for entry in ["src", "tests", "docs"]:
        assert entry in report


def test_build_repo_analysis_report_empty_analysis() -> None:
    """Should not raise even if analysis contains no data."""
    report = portal._build_repo_analysis_report(
        "https://github.com/owner/repo", "AAF-empty",
        {"readme": "", "arch_files": [], "tech_stack": [], "file_counts": {}, "dir_tree": []},
    )
    assert "# Repository Analysis Report" in report


def test_build_repo_analysis_report_with_arch_file(tmp_path: pathlib.Path) -> None:
    """Report includes an architecture section when arch_files is populated."""
    analysis = _mock_analysis()
    analysis["arch_files"] = [
        {"name": "docs/architecture.md", "content": "# Architecture\n\n## Components\n- API Gateway\n- Database"},
    ]
    report = portal._build_repo_analysis_report(
        "https://github.com/owner/repo", "AAF-arch", analysis
    )
    assert "Architecture:" in report
    assert "docs/architecture.md" in report


def test_build_repo_change_prompt_mentions_summary_and_goal() -> None:
    prompt = portal._build_repo_change_prompt(
        "https://github.com/owner/repo",
        "AAF-feature-123",
        _mock_analysis(),
        automation_goal="Add a secure notification workflow",
    )
    assert "AAF-feature-123" in prompt
    assert "secure notification workflow" in prompt
    assert portal._AAF_ANALYSIS_REPORT_FILE in prompt
    assert portal._AAF_CHANGE_SUMMARY_FILE in prompt
    assert "Do not commit, push, or open a PR" in prompt


def test_repo_change_agent_constant_matches_expected_name() -> None:
    assert portal._AAF_REPO_CHANGE_AGENT == "repo-change-agent"


def test_build_remote_file_url_github() -> None:
    url = portal._build_remote_file_url(
        "https://github.com/owner/repo",
        "AAF-demo",
        portal._AAF_ANALYSIS_REPORT_FILE,
    )
    assert url == "https://github.com/owner/repo/blob/AAF-demo/AAF-analysis-report.md"


def test_build_remote_file_url_azure_devops() -> None:
    url = portal._build_remote_file_url(
        "https://dev.azure.com/org/project/_git/repo",
        "AAF-demo",
        portal._AAF_CHANGE_SUMMARY_FILE,
    )
    assert url is not None
    assert "dev.azure.com/org/project/_git/repo" in url
    assert "version=GBAAF-demo" in url


class _FakeTextHandler:
    def __init__(self) -> None:
        self.status = None
        self.headers: dict[str, str] = {}
        self.body = b""

    def _send_json(self, payload, status=200):
        self.status = status
        self.body = str(payload).encode("utf-8")

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.headers[key] = value

    def end_headers(self):
        return None

    @property
    def wfile(self):
        return self

    def write(self, data: bytes):
        self.body += data


def test_handle_run_log_returns_plain_text(monkeypatch) -> None:
    run_id = "run-log-1"
    monkeypatch.setattr(portal, "_persist_runs_unlocked", lambda: None)
    monkeypatch.setattr(portal, "persist_runs", lambda: None)
    with portal.RUNS_LOCK:
        portal.RUNS[run_id] = {
            "id": run_id,
            "progress": {"logPreview": "preview line"},
            "logTail": "line 1\nline 2\nline 3",
            "stderr": "",
        }

    handler = _FakeTextHandler()
    portal.FactoryPortalHandler._handle_run_log(handler, run_id)

    assert handler.status == 200
    assert handler.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert "line 2" in handler.body.decode("utf-8")


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for repo workflow integration test")
def test_run_repo_analysis_implement_pr_with_disposable_remote(tmp_path: pathlib.Path, monkeypatch) -> None:
    remote_dir = tmp_path / "remote.git"
    work_dir = tmp_path / "seed"
    remote_dir.mkdir()
    work_dir.mkdir()

    def _git(args: list[str], cwd: pathlib.Path | None = None) -> tuple[str, str, int]:
        return portal._git_run(args, cwd=str(cwd) if cwd else None, timeout=30)

    _, stderr, rc = _git(["init", "--bare", str(remote_dir)])
    assert rc == 0, stderr

    _, stderr, rc = _git(["init", "-b", "main"], cwd=work_dir)
    assert rc == 0, stderr
    _, stderr, rc = _git(["config", "user.email", "test@example.com"], cwd=work_dir)
    assert rc == 0, stderr
    _, stderr, rc = _git(["config", "user.name", "Repo Workflow Test"], cwd=work_dir)
    assert rc == 0, stderr
    (work_dir / "README.md").write_text("# Disposable Repo\n\nSeed content.\n", encoding="utf-8")
    (work_dir / "docs").mkdir()
    (work_dir / "docs" / "architecture.md").write_text("# Architecture\n\n- API\n- Worker\n", encoding="utf-8")
    _, stderr, rc = _git(["add", "."], cwd=work_dir)
    assert rc == 0, stderr
    _, stderr, rc = _git(["commit", "-m", "seed repo"], cwd=work_dir)
    assert rc == 0, stderr
    _, stderr, rc = _git(["remote", "add", "origin", str(remote_dir)], cwd=work_dir)
    assert rc == 0, stderr
    _, stderr, rc = _git(["push", "origin", "main:main"], cwd=work_dir)
    assert rc == 0, stderr
    _, stderr, rc = _git(["symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote_dir)
    assert rc == 0, stderr

    class _FakeCopilotRunner:
        def runtime_info(self):
            return {"timeoutSec": 10}

        def start_run(self, repo_dir, prompt, requested_by="", agent=None):
            repo_path = pathlib.Path(repo_dir)
            (repo_path / "src").mkdir(exist_ok=True)
            (repo_path / "src" / "added-by-agent.txt").write_text(
                "created by fake repo-change-agent\n",
                encoding="utf-8",
            )
            return {"runId": "copilot-run-1"}

        def get_run(self, repo_dir, run_id):
            return {"status": "succeeded", "runId": run_id}

        def read_log_tail(self, repo_dir, run_id):
            return "agent started\nvalidated changes\ncompleted"

        def cancel_run(self, repo_dir, run_id):
            return {"status": "cancelled"}

    pr_calls: list[dict[str, str]] = []
    monkeypatch.setattr(portal, "copilot_runner", _FakeCopilotRunner())
    monkeypatch.setattr(portal, "_persist_runs_unlocked", lambda: None)
    monkeypatch.setattr(portal, "persist_runs", lambda: None)
    monkeypatch.setattr(portal, "FACTORY_REPO_ROOT", tmp_path)
    monkeypatch.setattr(portal, "OWNERS_FILE", tmp_path / ".portal-owners.json")
    monkeypatch.setattr(portal, "AUTH_MODE", "none")
    monkeypatch.setattr(portal, "VISIBLE_SLUGS", None)
    monkeypatch.setattr(portal, "_make_authed_clone_url", lambda repo_url, pat: str(remote_dir))
    monkeypatch.setattr(
        portal,
        "_create_pull_request",
        lambda repo_url, pat, branch_name, base_branch, title, body: (
            pr_calls.append(
                {
                    "repo_url": repo_url,
                    "branch_name": branch_name,
                    "base_branch": base_branch,
                    "title": title,
                }
            )
            or ("https://example.test/pr/1", None)
        ),
    )

    run_id = "repo-run-1"
    with portal.RUNS_LOCK:
        portal.RUNS[run_id] = {
            "id": run_id,
            "status": "queued",
            "createdAt": portal._utcnow_iso(),
            "brdFile": None,
            "startedAt": None,
            "finishedAt": None,
            "returnCode": None,
            "stdout": None,
            "stderr": None,
            "command": "repo-analysis",
            "result": None,
            "generationOptions": {
                "sourceType": "repo-analysis",
                "repoUrl": "https://github.com/example/disposable-repo",
                "branchName": "AAF-sandbox",
                "workflowMode": "implement-pr",
                "automationGoal": "Add a tiny architecture-aligned enhancement",
            },
            "owner": "tester@example.com",
        }

    handler = SimpleNamespace()
    portal.FactoryPortalHandler._run_repo_analysis(
        handler,
        run_id,
        "https://github.com/example/disposable-repo",
        "fake-pat",
        "AAF-sandbox",
        "implement-pr",
        "Add a tiny architecture-aligned enhancement",
        "tester@example.com",
    )

    with portal.RUNS_LOCK:
        run = dict(portal.RUNS[run_id])

    assert run["status"] == "completed"
    assert run["result"]["prUrl"] == "https://example.test/pr/1"
    assert run["result"]["projectSlug"].startswith("repo-intake-")
    assert run["progress"]["stage"] == "completed"
    assert "validated changes" in run["logTail"]
    assert pr_calls and pr_calls[0]["branch_name"] == "AAF-sandbox"

    imported_slug = run["result"]["projectSlug"]
    imported_root = tmp_path / "projects" / imported_slug
    assert imported_root.is_dir()
    assert (imported_root / "project-manifest.json").is_file()
    assert (imported_root / "docs" / "architecture-overview.md").is_file()
    assert (imported_root / "src" / "added-by-agent.txt").is_file()

    inspect_dir = tmp_path / "inspect"
    _, stderr, rc = _git(["clone", "--branch", "AAF-sandbox", str(remote_dir), str(inspect_dir)])
    assert rc == 0, stderr
    assert (inspect_dir / portal._AAF_ANALYSIS_REPORT_FILE).is_file()
    assert (inspect_dir / portal._AAF_CHANGE_SUMMARY_FILE).is_file()
    assert (inspect_dir / "src" / "added-by-agent.txt").is_file()


def test_run_repo_analysis_local_repo_analysis_only(tmp_path: pathlib.Path, monkeypatch) -> None:
    local_repo = tmp_path / "local-repo"
    inspect_dir = tmp_path / "inspect-local-analysis"

    def _git(args: list[str], cwd: pathlib.Path | None = None) -> tuple[str, str, int]:
        return portal._git_run(args, cwd=str(cwd) if cwd else None, timeout=30)

    local_repo.mkdir()
    _, stderr, rc = _git(["init", "-b", "main"], cwd=local_repo)
    assert rc == 0, stderr
    _, stderr, rc = _git(["config", "user.email", "test@example.com"], cwd=local_repo)
    assert rc == 0, stderr
    _, stderr, rc = _git(["config", "user.name", "Local Repo Test"], cwd=local_repo)
    assert rc == 0, stderr
    (local_repo / "README.md").write_text("# Local Repo\n\nSample content.\n", encoding="utf-8")
    (local_repo / "src").mkdir()
    (local_repo / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    _, stderr, rc = _git(["add", "."], cwd=local_repo)
    assert rc == 0, stderr
    _, stderr, rc = _git(["commit", "-m", "seed local repo"], cwd=local_repo)
    assert rc == 0, stderr

    monkeypatch.setattr(portal, "_persist_runs_unlocked", lambda: None)
    monkeypatch.setattr(portal, "persist_runs", lambda: None)
    monkeypatch.setattr(portal, "FACTORY_REPO_ROOT", tmp_path)
    monkeypatch.setattr(portal, "OWNERS_FILE", tmp_path / ".portal-owners.json")
    monkeypatch.setattr(portal, "AUTH_MODE", "none")
    monkeypatch.setattr(portal, "VISIBLE_SLUGS", None)

    run_id = "repo-local-run-1"
    with portal.RUNS_LOCK:
        portal.RUNS[run_id] = {
            "id": run_id,
            "status": "queued",
            "createdAt": portal._utcnow_iso(),
            "brdFile": None,
            "startedAt": None,
            "finishedAt": None,
            "returnCode": None,
            "stdout": None,
            "stderr": None,
            "command": "repo-analysis",
            "result": None,
            "generationOptions": {
                "sourceType": "repo-analysis-local",
                "inputSource": "local",
                "repoUrl": "local://local-repo",
                "branchName": "AAF-local-test",
                "workflowMode": "analysis-only",
                "automationGoal": "",
            },
            "owner": "tester@example.com",
        }

    handler = SimpleNamespace()
    portal.FactoryPortalHandler._run_repo_analysis(
        handler,
        run_id,
        "local://local-repo",
        "",
        "AAF-local-test",
        "analysis-only",
        "",
        "tester@example.com",
        local_repo_path=local_repo,
        input_source="local",
    )

    with portal.RUNS_LOCK:
        run = dict(portal.RUNS[run_id])

    assert run["status"] == "completed"
    assert run["result"]["reportUrl"] == ""
    assert run["result"]["inputSource"] == "local"
    assert run["result"]["branchTarget"] == "local"
    assert run["result"]["branchCommitted"] is True
    assert run["result"]["branchCommitMode"] == "analysis-report-only"
    assert run["result"]["projectSlug"].startswith("repo-intake-")

    imported_root = tmp_path / "projects" / run["result"]["projectSlug"]
    assert imported_root.is_dir()
    assert (imported_root / portal._AAF_ANALYSIS_REPORT_FILE).is_file()
    assert (imported_root / "project-manifest.json").is_file()

    _, stderr, rc = _git(["clone", "--branch", "AAF-local-test", str(local_repo), str(inspect_dir)])
    assert rc == 0, stderr
    assert (inspect_dir / portal._AAF_ANALYSIS_REPORT_FILE).is_file()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for local repo workflow integration test")
def test_run_repo_analysis_local_repo_implement_creates_local_branch(tmp_path: pathlib.Path, monkeypatch) -> None:
    local_repo = tmp_path / "local-repo"
    inspect_dir = tmp_path / "inspect-local-implement"
    local_repo.mkdir()

    def _git(args: list[str], cwd: pathlib.Path | None = None) -> tuple[str, str, int]:
        return portal._git_run(args, cwd=str(cwd) if cwd else None, timeout=30)

    _, stderr, rc = _git(["init", "-b", "main"], cwd=local_repo)
    assert rc == 0, stderr
    _, stderr, rc = _git(["config", "user.email", "test@example.com"], cwd=local_repo)
    assert rc == 0, stderr
    _, stderr, rc = _git(["config", "user.name", "Local Repo Implement Test"], cwd=local_repo)
    assert rc == 0, stderr
    (local_repo / "README.md").write_text("# Local Repo\n\nSample content.\n", encoding="utf-8")
    (local_repo / "src").mkdir()
    (local_repo / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    _, stderr, rc = _git(["add", "."], cwd=local_repo)
    assert rc == 0, stderr
    _, stderr, rc = _git(["commit", "-m", "seed local repo"], cwd=local_repo)
    assert rc == 0, stderr

    class _FakeCopilotRunner:
        def runtime_info(self):
            return {"timeoutSec": 10}

        def start_run(self, repo_dir, prompt, requested_by="", agent=None):
            repo_path = pathlib.Path(repo_dir)
            (repo_path / "src" / "added-by-agent.txt").write_text(
                "created by fake repo-change-agent\n",
                encoding="utf-8",
            )
            return {"runId": "copilot-run-local-1"}

        def get_run(self, repo_dir, run_id):
            return {"status": "succeeded", "runId": run_id}

        def read_log_tail(self, repo_dir, run_id):
            return "agent started\nvalidated changes\ncompleted"

        def cancel_run(self, repo_dir, run_id):
            return {"status": "cancelled"}

    monkeypatch.setattr(portal, "copilot_runner", _FakeCopilotRunner())
    monkeypatch.setattr(portal, "_persist_runs_unlocked", lambda: None)
    monkeypatch.setattr(portal, "persist_runs", lambda: None)
    monkeypatch.setattr(portal, "FACTORY_REPO_ROOT", tmp_path)
    monkeypatch.setattr(portal, "OWNERS_FILE", tmp_path / ".portal-owners.json")
    monkeypatch.setattr(portal, "AUTH_MODE", "none")
    monkeypatch.setattr(portal, "VISIBLE_SLUGS", None)

    run_id = "repo-local-run-implement-1"
    with portal.RUNS_LOCK:
        portal.RUNS[run_id] = {
            "id": run_id,
            "status": "queued",
            "createdAt": portal._utcnow_iso(),
            "brdFile": None,
            "startedAt": None,
            "finishedAt": None,
            "returnCode": None,
            "stdout": None,
            "stderr": None,
            "command": "repo-analysis",
            "result": None,
            "generationOptions": {
                "sourceType": "repo-analysis-local",
                "inputSource": "local",
                "repoUrl": "local://local-repo",
                "branchName": "AAF-local-implement",
                "workflowMode": "implement-pr",
                "automationGoal": "Add a tiny architecture-aligned enhancement",
            },
            "owner": "tester@example.com",
        }

    handler = SimpleNamespace()
    portal.FactoryPortalHandler._run_repo_analysis(
        handler,
        run_id,
        "local://local-repo",
        "",
        "AAF-local-implement",
        "implement-pr",
        "Add a tiny architecture-aligned enhancement",
        "tester@example.com",
        local_repo_path=local_repo,
        input_source="local",
    )

    with portal.RUNS_LOCK:
        run = dict(portal.RUNS[run_id])

    assert run["status"] == "completed"
    assert run["result"]["inputSource"] == "local"
    assert run["result"]["branchTarget"] == "local"
    assert run["result"]["branchCommitted"] is True
    assert run["result"]["branchCommitMode"] == "all-changes"
    assert run["result"]["workflowMode"] == "implement-pr"
    assert run["result"]["prUrl"] == ""
    assert run["result"]["projectSlug"].startswith("repo-intake-")

    _, stderr, rc = _git(["clone", "--branch", "AAF-local-implement", str(local_repo), str(inspect_dir)])
    assert rc == 0, stderr
    assert (inspect_dir / portal._AAF_ANALYSIS_REPORT_FILE).is_file()
    assert (inspect_dir / portal._AAF_CHANGE_SUMMARY_FILE).is_file()
    assert (inspect_dir / "src" / "added-by-agent.txt").is_file()
