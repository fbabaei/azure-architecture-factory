"""Tests for feed projection of BRD readiness and auto-flow gate metadata."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import start_factory_portal as portal


class _FakeHandler:
    def __init__(self):
        self.payload = None
        self.status = None

    def _authorized_user(self):
        return None

    def _send_json(self, payload, status=200):
        self.payload = payload
        self.status = status


def test_serve_json_feed_projects_include_readiness_fields(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)

        slug = "sample-readiness-project"
        project_dir = projects_dir / slug
        project_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "title": "Sample Readiness Project",
            "status": "Ready",
            "source_brd": "docs/intake/sample.md",
            "created_at": "2026-04-23T00:00:00Z",
            "generation_options": {"enableObservability": True},
            "links": {
                "readme": "projects/sample-readiness-project/README.md",
                "architectureOverview": "projects/sample-readiness-project/docs/architecture-overview.md",
            },
            "suggested_runtime": {"runtime": "agent-framework"},
            "brd_readiness": {
                "classification": "Auto-Ready With Guardrails",
                "percentage_score": 78,
            },
            "orchestrator_auto_flow": {
                "mode": "auto",
                "eligible": False,
                "reason": "Architect review required",
            },
            "implementation_language": "python",
            "iac_tool": "bicep",
        }
        (project_dir / "project-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        (root / "factory-projects.generated.json").write_text(
            json.dumps({"generatedAt": "2026-04-23T00:00:01Z", "projects": []}),
            encoding="utf-8",
        )

        monkeypatch.setattr(portal, "FACTORY_REPO_ROOT", root)
        monkeypatch.setattr(portal, "AUTH_MODE", "none")
        monkeypatch.setattr(portal, "VISIBLE_SLUGS", None)

        handler = _FakeHandler()
        portal.FactoryPortalHandler._serve_json_feed(handler)

        assert handler.status == 200
        assert isinstance(handler.payload, dict)
        projects = handler.payload.get("projects") or []
        assert len(projects) == 1
        item = projects[0]
        assert item["slug"] == slug
        assert item["brdReadiness"]["classification"] == "Auto-Ready With Guardrails"
        assert item["orchestratorAutoFlow"]["eligible"] is False
        assert item["implementationLanguage"] == "python"
        assert item["iacTool"] == "bicep"
        assert item["links"]["readme"].endswith("README.md")
