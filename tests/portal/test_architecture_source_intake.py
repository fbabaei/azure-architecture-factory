from __future__ import annotations

import start_factory_portal as portal


def test_sanitize_source_type_aliases() -> None:
    assert portal._sanitize_source_type("auto") == "auto"
    assert portal._sanitize_source_type("draw.io") == "drawio"
    assert portal._sanitize_source_type("markdown") == "architecture-markdown"
    assert portal._sanitize_source_type("puml") == "plantuml"
    assert portal._sanitize_source_type("vsdx") == "visio"
    assert portal._sanitize_source_type("unknown-format") == "brd-markdown"


def test_detect_source_type_from_content_signatures() -> None:
    assert portal._detect_source_type(file_name="diagram.drawio", content="<mxfile><diagram></diagram></mxfile>") == "drawio"
    assert portal._detect_source_type(file_name="flow.txt", content="graph TD\nA-->B") == "mermaid"
    assert portal._detect_source_type(file_name="uml.txt", content="@startuml\nAlice -> Bob") == "plantuml"
    assert portal._detect_source_type(file_name="workspace.dsl", content="workspace {\n  model {\n  }\n}") == "structurizr"
    assert portal._detect_source_type(file_name="arch.json", content='{"services": ["api"]}') == "json"
    assert portal._detect_source_type(file_name="arch.yaml", content="services:\n  - api\n  - worker") == "yaml"


def test_detect_source_type_from_markdown_shape() -> None:
    brd = "# Project\n\n## Business Goal\nShip faster\n\n## Key Requirements\n- API\n"
    architecture = "# Architecture\n\n## Components\n- API\n- Worker\n\n## Data Flow\nAPI -> Queue -> Worker\n"

    assert portal._detect_source_type(file_name="brief.md", content=brd) == "brd-markdown"
    assert portal._detect_source_type(file_name="arch.md", content=architecture) == "architecture-markdown"


def test_build_generation_options_accepts_existing_target_slug(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    manifest_path = repo_root / "projects" / "demo-project" / "project-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(portal, "FACTORY_REPO_ROOT", repo_root)

    options, err = portal._build_generation_options(
        {
            "sourceType": "mermaid",
            "targetProjectSlug": "demo-project",
            "implementationLanguage": "csharp",
        }
    )

    assert err is None
    assert options["sourceType"] == "mermaid"
    assert options["targetProjectSlug"] == "demo-project"
    assert options["implementationLanguage"] == "dotnet"


def test_build_generation_options_auto_detects_from_content(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portal, "FACTORY_REPO_ROOT", repo_root)

    options, err = portal._build_generation_options(
        {"sourceType": "auto"},
        file_name="architecture.txt",
        content="graph TD\nA-->B",
    )

    assert err is None
    assert options["sourceTypeRequested"] == "auto"
    assert options["sourceTypeDetected"] == "mermaid"
    assert options["sourceType"] == "mermaid"


def test_build_generation_options_rejects_missing_target_slug(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(portal, "FACTORY_REPO_ROOT", repo_root)

    options, err = portal._build_generation_options({"targetProjectSlug": "missing-project"})

    assert options == {}
    assert err == "Project slug 'missing-project' was not found"


def test_build_generation_document_wraps_non_brd_sources() -> None:
    rendered = portal._build_generation_document(
        "sample-project.md",
        "graph TD\nA-->B",
        {
            "sourceType": "mermaid",
            "sourceFileName": "architecture.mmd",
            "targetProjectSlug": "sample-project-20260424",
            "sourceAttachment": "docs/intake/attachments/sample-project-mermaid.mmd",
        },
    )

    assert "# Sample Project" in rendered
    assert "- source_type: mermaid" in rendered
    assert "- target_project_slug: sample-project-20260424" in rendered
    assert "```mermaid" in rendered
    assert "graph TD" in rendered
    assert "## Parsed Architecture Summary" in rendered
    assert "### Relationships" in rendered


def test_summarize_architecture_source_extracts_mermaid_relationships() -> None:
    summary = portal._summarize_architecture_source("mermaid", "graph TD\nApi[API] --> Queue[Queue]\nQueue --> Worker[Worker]")

    assert any("API" in item for item in summary["components"])
    assert any("Api -> Queue" in item for item in summary["relationships"])
    assert "Mermaid graph parsed" in summary["signals"]


def test_summarize_architecture_source_extracts_structurizr_elements() -> None:
    summary = portal._summarize_architecture_source(
        "structurizr",
        'workspace {\n  model {\n    web = softwareSystem "Web App"\n    api = container "API"\n    web -> api "Calls"\n  }\n}',
    )

    assert any("Web App" in item for item in summary["components"])
    assert any("Web App -> API (Calls)" == item for item in summary["relationships"])


def test_summarize_architecture_source_extracts_drawio_labels() -> None:
    xml = (
        '<mxfile><diagram><mxGraphModel><root>'
        '<mxCell id="2" value="Frontend" vertex="1" parent="1"/>'
        '<mxCell id="3" value="API" vertex="1" parent="1"/>'
        '<mxCell id="4" edge="1" source="2" target="3" value="HTTP" parent="1"/>'
        '</root></mxGraphModel></diagram></mxfile>'
    )
    summary = portal._summarize_architecture_source("drawio", xml)

    assert "Frontend" in summary["components"]
    assert "API" in summary["components"]
    # Relationship extraction via proper XML parse
    assert any("Frontend" in r and "API" in r for r in summary["relationships"])
    # Signal indicates XML was parsed (not regex fallback)
    assert any("XML parsed" in s for s in summary["signals"])
