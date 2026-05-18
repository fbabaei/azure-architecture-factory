"""Python / FastAPI language specialist (archetype-aware).

Emits a FastAPI scaffold whose shape depends on the workload archetype the
runner detected from the BRD:

* ``extraction-chat`` -- document upload + structured extraction +
  clarification loop + human-in-the-loop chat. Multi-endpoint API with
  split service modules and a sample-corpus folder.
* ``rag-qa`` -- retrieval + Q&A over a corpus. ``/qa/ask`` endpoint plus a
  corpus loader and a sample-corpus folder.
* ``api-service`` -- generic single-endpoint REST API (default fallback).

The Python package name is derived from the project slug (``mdr-support`` ->
``mdr_support``) so generated projects feel domain-owned. Falls back to
``copilot_api`` when the slug cannot be turned into a valid identifier.
"""
from __future__ import annotations

import keyword
import re
from pathlib import Path

from .base import LanguageEmitContext, LanguageEmitResult


_DEFAULT_PACKAGE_NAME = "copilot_api"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return normalized.strip("-") or "project"


def _package_name_from_slug(slug: str) -> str:
    if not slug:
        return _DEFAULT_PACKAGE_NAME
    stem = re.sub(r"-\d{14}$", "", slug.strip().lower())
    cleaned = re.sub(r"[^a-z0-9_]+", "_", stem).strip("_")
    if not cleaned or not re.match(r"[a-z_]", cleaned[0]):
        return _DEFAULT_PACKAGE_NAME
    if keyword.iskeyword(cleaned):
        return _DEFAULT_PACKAGE_NAME
    return cleaned


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Archetype: api-service (default)
# ---------------------------------------------------------------------------

_API_MAIN = (
    "from datetime import datetime, timezone\n"
    "from fastapi import FastAPI\n\n"
    "from .models import AskRequest, AskResponse\n"
    "from .services.copilot_service import build_response\n\n\n"
    "app = FastAPI(title=\"Generated Copilot API\", version=\"0.1.0\")\n\n\n"
    "@app.get(\"/health\")\n"
    "def health() -> dict:\n"
    "    return {\"status\": \"ok\", \"timestamp\": datetime.now(timezone.utc).isoformat()}\n\n\n"
    "@app.post(\"/api/copilot/ask\", response_model=AskResponse)\n"
    "def ask_copilot(payload: AskRequest) -> AskResponse:\n"
    "    return AskResponse(answer=build_response(payload.question, payload.context), source=\"generated-starter\")\n"
)

_API_MODELS = (
    "from pydantic import BaseModel, Field\n\n\n"
    "class AskRequest(BaseModel):\n"
    "    question: str = Field(min_length=3)\n"
    "    context: str = Field(default=\"\")\n\n\n"
    "class AskResponse(BaseModel):\n"
    "    answer: str\n"
    "    source: str\n"
)

_API_SERVICE = (
    "def build_response(question: str, context: str) -> str:\n"
    "    summary = context.strip()[:240]\n"
    "    if summary:\n"
    "        return \"Starter copilot response for question: '\" + question + \"'. Context summary: \" + summary + \". Replace this logic with your workload-specific orchestration.\"\n"
    "    return \"Starter copilot response for question: '\" + question + \"'. Replace this logic with your workload-specific orchestration.\"\n"
)


# ---------------------------------------------------------------------------
# Archetype: extraction-chat
# ---------------------------------------------------------------------------

_EXTRACTION_MAIN = '''\
"""FastAPI entrypoint for a document-extraction + clarification workload."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .models import (
    ChatRequest,
    ChatResponse,
    ClarificationBundle,
    DraftResponse,
    ExtractionDraft,
    UploadResponse,
)
from .services.clarification_service import compute_missing_fields
from .services.document_ingestion import ingest_document
from .services.extraction_service import extract_structured_data
from .services.repository import DraftRepository
from .services.session_service import SessionService


logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx", ".md"}

app = FastAPI(title="Generated Extraction + Chat API", version="0.1.0")
_repo = DraftRepository()
_sessions = SessionService()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), notes: str = Form(default="")) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix and suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=415, detail="unsupported file type")
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    ingested = ingest_document(file.filename, payload, notes=notes)
    extraction = extract_structured_data(ingested)
    document_id = str(uuid.uuid4())
    draft = ExtractionDraft(
        document_id=document_id,
        source_filename=file.filename,
        fields=extraction.fields,
        raw_excerpt=extraction.raw_excerpt,
    )
    _repo.put(draft)
    clarifications = compute_missing_fields(draft)
    logger.info("uploaded %s (%s bytes) -> %s", file.filename, len(payload), document_id)
    return UploadResponse(document_id=document_id, clarifications=clarifications, draft=draft)


@app.post("/documents/{document_id}/chat", response_model=ChatResponse)
def chat(document_id: str, payload: ChatRequest) -> ChatResponse:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    if payload.field:
        draft.fields[payload.field] = payload.answer
        _repo.put(draft)
    clarifications = compute_missing_fields(draft)
    _sessions.record_turn(document_id, payload.field or "(free-form)", payload.answer)
    return ChatResponse(document_id=document_id, draft=draft, clarifications=clarifications)


@app.get("/documents/{document_id}", response_model=ExtractionDraft)
def get_document(document_id: str) -> ExtractionDraft:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    return draft


@app.get("/documents/{document_id}/clarifications", response_model=ClarificationBundle)
def get_clarifications(document_id: str) -> ClarificationBundle:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    return ClarificationBundle(document_id=document_id, clarifications=compute_missing_fields(draft))


@app.post("/documents/{document_id}/draft", response_model=DraftResponse)
def finalize_draft(document_id: str) -> DraftResponse:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    open_items = compute_missing_fields(draft)
    if open_items:
        raise HTTPException(status_code=409, detail={"message": "mandatory fields missing", "clarifications": [c.model_dump() for c in open_items]})
    return DraftResponse(document_id=document_id, draft=draft, finalized_at=datetime.now(timezone.utc).isoformat())
'''

_EXTRACTION_MODELS = '''\
"""Domain models for the extraction + clarification workload."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Clarification(BaseModel):
    field: str = Field(description="Mandatory field name that is still missing.")
    prompt: str = Field(description="Human-facing question that will elicit the value.")


class ExtractionDraft(BaseModel):
    document_id: str
    source_filename: str
    fields: dict[str, Any] = Field(default_factory=dict)
    raw_excerpt: str = ""


class ExtractionResult(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    raw_excerpt: str = ""


class UploadResponse(BaseModel):
    document_id: str
    clarifications: list[Clarification]
    draft: ExtractionDraft


class ChatRequest(BaseModel):
    field: str | None = Field(default=None)
    answer: str = Field(min_length=1)


class ChatResponse(BaseModel):
    document_id: str
    draft: ExtractionDraft
    clarifications: list[Clarification]


class ClarificationBundle(BaseModel):
    document_id: str
    clarifications: list[Clarification]


class DraftResponse(BaseModel):
    document_id: str
    draft: ExtractionDraft
    finalized_at: str
'''

_EXTRACTION_INGESTION = '''\
"""Document ingestion stub.

Swap in Azure AI Document Intelligence / Form Recognizer in production.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IngestedDocument:
    filename: str
    content_type: str
    text_excerpt: str
    notes: str


def ingest_document(filename: str, payload: bytes, notes: str = "") -> IngestedDocument:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        content_type = "application/pdf"
        text_excerpt = "[pdf: " + str(len(payload)) + " bytes -- replace ingestion stub with OCR]"
    elif lowered.endswith((".doc", ".docx")):
        content_type = "application/msword"
        text_excerpt = "[word doc: " + str(len(payload)) + " bytes -- replace ingestion stub]"
    else:
        content_type = "text/plain"
        try:
            text_excerpt = payload.decode("utf-8", errors="replace")[:2000]
        except Exception:
            text_excerpt = ""
    return IngestedDocument(filename=filename, content_type=content_type, text_excerpt=text_excerpt, notes=notes)
'''

_EXTRACTION_SERVICE = r'''"""Structured extraction stub.

Replace ``extract_structured_data`` with an Azure OpenAI / Foundry call
that emits the same ExtractionResult shape in production.
"""
from __future__ import annotations

import re

from ..models import ExtractionResult
from .document_ingestion import IngestedDocument

MANDATORY_FIELDS = ("reference_id", "submission_date", "jurisdiction", "summary")


def extract_structured_data(doc: IngestedDocument) -> ExtractionResult:
    text = doc.text_excerpt or ""
    fields: dict[str, str] = {}
    ref = re.search(r"\b(?:ref|reference)\s*[:#]?\s*([A-Z0-9\-]{4,})", text, re.IGNORECASE)
    if ref:
        fields["reference_id"] = ref.group(1)
    date = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if date:
        fields["submission_date"] = date.group(1)
    jurisdiction = re.search(r"\bjurisdiction\s*[:=]?\s*([A-Za-z ]{2,40})", text, re.IGNORECASE)
    if jurisdiction:
        fields["jurisdiction"] = jurisdiction.group(1).strip()
    if text:
        fields["summary"] = text[:200]
    return ExtractionResult(fields=fields, raw_excerpt=text[:500])
'''

_EXTRACTION_CLARIFICATION = '''\
"""Clarification service: compute the next missing mandatory field."""
from __future__ import annotations

from ..models import Clarification, ExtractionDraft
from .extraction_service import MANDATORY_FIELDS


_FIELD_PROMPTS: dict[str, str] = {
    "reference_id": "What is the reference ID for this submission?",
    "submission_date": "What is the submission date (YYYY-MM-DD)?",
    "jurisdiction": "Which jurisdiction does this arrangement apply to?",
    "summary": "Please provide a short summary of the arrangement.",
}


def compute_missing_fields(draft: ExtractionDraft) -> list[Clarification]:
    missing: list[Clarification] = []
    for field in MANDATORY_FIELDS:
        value = draft.fields.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(Clarification(field=field, prompt=_FIELD_PROMPTS.get(field, "Please provide a value.")))
    return missing
'''

_EXTRACTION_REPOSITORY = '''\
"""In-memory repository for ExtractionDrafts (swap for Cosmos / SQL)."""
from __future__ import annotations

from threading import Lock

from ..models import ExtractionDraft


class DraftRepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[str, ExtractionDraft] = {}

    def put(self, draft: ExtractionDraft) -> None:
        with self._lock:
            self._store[draft.document_id] = draft

    def get(self, document_id: str) -> ExtractionDraft | None:
        with self._lock:
            return self._store.get(document_id)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())
'''

_EXTRACTION_SESSION = '''\
"""Session service: records chat turns per document."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass
class ChatTurn:
    at: str
    field: str
    answer: str


@dataclass
class Session:
    document_id: str
    turns: list[ChatTurn] = field(default_factory=list)


class SessionService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, Session] = {}

    def record_turn(self, document_id: str, field: str, answer: str) -> None:
        with self._lock:
            session = self._sessions.setdefault(document_id, Session(document_id=document_id))
            session.turns.append(ChatTurn(at=datetime.now(timezone.utc).isoformat(), field=field, answer=answer))

    def get(self, document_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(document_id)
'''

_SAMPLE_CORPUS_README = """\
# Sample Corpus

Drop representative documents (PDFs, text transcripts, sample forms) here
and the generated scaffold will exercise the ingestion / loader stubs
against them. `manifest.json` is a simple index the test harness can use
to discover sample documents in a deterministic order.
"""

_SAMPLE_CORPUS_MANIFEST = '{\n  "documents": []\n}\n'


# ---------------------------------------------------------------------------
# Archetype: rag-qa
# ---------------------------------------------------------------------------

_RAG_MAIN = '''\
"""FastAPI entrypoint for a retrieval + Q&A workload."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from .models import QARequest, QAResponse
from .services.qa_service import answer_question


app = FastAPI(title="Generated RAG Q&A API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/qa/ask", response_model=QAResponse)
def ask(payload: QARequest) -> QAResponse:
    return answer_question(payload.question, payload.top_k)
'''

_RAG_MODELS = '''\
from pydantic import BaseModel, Field


class QARequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int = Field(default=3, ge=1, le=20)


class QASource(BaseModel):
    title: str
    excerpt: str


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: list[QASource]
'''

_RAG_QA_SERVICE = '''\
"""Q&A service stub -- replace with Azure AI Search + Azure OpenAI."""
from __future__ import annotations

from ..models import QAResponse, QASource
from .corpus_loader import load_corpus


def answer_question(question: str, top_k: int) -> QAResponse:
    corpus = load_corpus()
    q_terms = {term.lower() for term in question.split() if len(term) > 3}
    scored = []
    for doc in corpus:
        score = sum(1 for term in q_terms if term in doc.text.lower())
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    selected = scored[:top_k]
    sources = [QASource(title=doc.title, excerpt=doc.text[:240]) for _, doc in selected]
    if selected:
        answer = "Found " + str(len(selected)) + " matching document(s). Replace this stub with an LLM call."
    else:
        answer = "No matching documents in sample corpus. Populate sample-corpus/ or wire up your index."
    return QAResponse(question=question, answer=answer, sources=sources)
'''

_RAG_CORPUS_LOADER = '''\
"""Corpus loader stub: reads sample-corpus/ -- swap for Azure AI Search."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CorpusDoc:
    title: str
    text: str


def _corpus_root() -> Path:
    return Path(__file__).resolve().parents[3] / "sample-corpus"


def load_corpus() -> list[CorpusDoc]:
    root = _corpus_root()
    if not root.exists():
        return []
    docs: list[CorpusDoc] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            docs.append(CorpusDoc(title=path.stem, text=text))
    return docs
'''


# ---------------------------------------------------------------------------
# Shared builders
# ---------------------------------------------------------------------------


def _build_pyproject(title: str, archetype: str) -> str:
    normalized = _slugify(title).replace("-", "_")
    deps = ['"fastapi==0.116.1"', '"uvicorn[standard]==0.32.1"', '"pydantic==2.10.3"']
    if archetype == "extraction-chat":
        deps.append('"python-multipart==0.0.17"')
    return (
        "[project]\n"
        f"name = \"{normalized}\"\n"
        "version = \"0.1.0\"\n"
        f"description = \"Generated starter project for {title}\"\n"
        "requires-python = \">=3.11\"\n"
        "dependencies = [\n"
        + "".join(f"  {d},\n" for d in deps)
        + "]\n"
    )


def _build_requirements(archetype: str) -> str:
    base = "fastapi==0.116.1\nuvicorn[standard]==0.32.1\npydantic==2.10.3\n"
    if archetype == "extraction-chat":
        base += "python-multipart==0.0.17\n"
    return base


def _required_paths(package_name: str, archetype: str) -> list[str]:
    common = [
        "root / 'README.md'",
        "root / 'DEPLOY.md'",
        "root / 'requirements.txt'",
        f"root / 'src' / '{package_name}' / 'main.py'",
        f"root / 'src' / '{package_name}' / 'models.py'",
        "root / 'docs' / 'architecture-overview.md'",
        "root / 'docs' / 'governance-model.md'",
        "root / 'docs' / 'delivery-milestones.md'",
        "root / 'docs' / 'success-criteria.md'",
        "root / 'docs' / 'traceability-matrix.md'",
        "root / 'diagrams' / (root.name + '.md')",
        "root / 'project-manifest.json'",
    ]
    if archetype == "extraction-chat":
        common.extend([
            f"root / 'src' / '{package_name}' / 'services' / 'document_ingestion.py'",
            f"root / 'src' / '{package_name}' / 'services' / 'extraction_service.py'",
            f"root / 'src' / '{package_name}' / 'services' / 'clarification_service.py'",
            f"root / 'src' / '{package_name}' / 'services' / 'repository.py'",
            f"root / 'src' / '{package_name}' / 'services' / 'session_service.py'",
            "root / 'sample-corpus' / 'manifest.json'",
            "root / 'docs' / 'detailed-architecture.md'",
        ])
    elif archetype == "rag-qa":
        common.extend([
            f"root / 'src' / '{package_name}' / 'services' / 'qa_service.py'",
            f"root / 'src' / '{package_name}' / 'services' / 'corpus_loader.py'",
            "root / 'sample-corpus' / 'manifest.json'",
            "root / 'docs' / 'detailed-architecture.md'",
        ])
    else:
        common.append(f"root / 'src' / '{package_name}' / 'services' / 'copilot_service.py'")
    return common


def _build_test(package_name: str, archetype: str) -> str:
    paths = _required_paths(package_name, archetype)
    block = ",\n        ".join(paths)
    return (
        "from pathlib import Path\n\n\n"
        "def test_generated_project_docs_exist():\n"
        "    root = Path(__file__).resolve().parents[1]\n"
        "    required = [\n"
        f"        {block},\n"
        "    ]\n"
        "    missing = [str(path) for path in required if not path.exists()]\n"
        "    assert not missing, f'Missing generated docs: {missing}'\n"
    )


def _build_readme(title: str, source_brd: str, slug: str, requirements: list[str],
                  enable_observability: bool, package_name: str, archetype: str,
                  emitted_files: list[str]) -> str:
    highlights = "\n".join(f"- {item}" for item in requirements[:10])
    observability_line = (
        "- Monitoring and observability wiring requested: Yes"
        if enable_observability
        else "- Monitoring and observability wiring requested: No"
    )
    archetype_labels = {
        "extraction-chat": "Document extraction + clarification loop + human-in-the-loop chat",
        "rag-qa": "Retrieval-augmented Q&A over a document corpus",
        "api-service": "Generic REST API",
    }
    archetype_line = archetype_labels.get(archetype, archetype_labels["api-service"])
    emitted_block = "\n".join(f"- `{p}`" for p in emitted_files)
    return (
        f"# {title}\n\n"
        f"Generated from BRD `{source_brd}` by the Azure-native factory runner (Python specialist).\n\n"
        f"## Implementation Language\n\n"
        f"**Python 3.11+ (FastAPI)**\n\n"
        f"## Detected Archetype\n\n"
        f"**{archetype}** -- {archetype_line}\n\n"
        f"## What Was Generated\n"
        f"- `docs/architecture-overview.md`\n"
        f"- `docs/governance-model.md`\n"
        f"- `docs/delivery-milestones.md`\n"
        f"- `docs/success-criteria.md`\n"
        f"- `docs/traceability-matrix.md`\n"
        f"- `diagrams/{slug}.md`\n"
        f"- `diagrams/{slug}.drawio`\n"
        f"{emitted_block}\n\n"
        f"## Selected Generation Options\n{observability_line}\n\n"
        f"## BRD Requirement Highlights\n{highlights}\n"
    )


def _build_deploy(slug: str, enable_observability: bool, package_name: str) -> str:
    steps = [
        "1. Review and customize `infra/main.bicep`.",
        "2. Provision hosting, identity, Key Vault access, and Application Insights.",
        "3. Configure application settings for the generated API.",
        f"4. Deploy the project from `projects/{slug}`.",
        "5. Validate `/health` after deployment.",
    ]
    if enable_observability:
        steps[1] = "2. Provision hosting, identity, Key Vault access, Application Insights, and Log Analytics."
        steps.insert(3, "4. Configure health probes, alerts, dashboards, and operational ownership for the generated workload.")
        steps[4] = f"5. Deploy the project from `projects/{slug}`."
        steps[5] = "6. Validate `/health` after deployment and confirm telemetry reaches Azure Monitor."
    return (
        "# Deploy\n\n"
        "## Prerequisites\n"
        "- Python 3.11+\n"
        "- Azure CLI authenticated\n"
        "- Target Azure subscription and resource group\n\n"
        "## Local Validation\n"
        "```bash\n"
        "python -m venv .venv\n"
        ".venv\\Scripts\\activate\n"
        "python -m pip install -r requirements.txt\n"
        "python -m pytest tests -q\n"
        "```\n\n"
        "## Local Run\n"
        "```bash\n"
        f"python -m uvicorn src.{package_name}.main:app --host 127.0.0.1 --port 8000 --reload\n"
        "```\n\n"
        "## Azure Deployment Outline\n"
        + "\n".join(steps)
        + "\n"
    )


def _build_detailed_architecture(title: str, archetype: str, package_name: str) -> str:
    if archetype == "extraction-chat":
        return (
            f"# {title} -- Detailed Architecture (extraction-chat)\n\n"
            "## Service boundaries\n\n"
            "| Module | Responsibility | Replace with |\n"
            "|---|---|---|\n"
            f"| `src/{package_name}/services/document_ingestion.py` | Parse uploaded bytes into a text excerpt. | Azure AI Document Intelligence |\n"
            f"| `src/{package_name}/services/extraction_service.py` | Extract structured fields from the excerpt. | Azure OpenAI / Foundry agent with JSON mode |\n"
            f"| `src/{package_name}/services/clarification_service.py` | Compute the next missing mandatory field. | Keep deterministic; feed prompts into chat UX. |\n"
            f"| `src/{package_name}/services/repository.py` | Persist drafts across chat turns. | Cosmos DB / Azure SQL |\n"
            f"| `src/{package_name}/services/session_service.py` | Track human-in-the-loop conversation history. | Cosmos DB / App Insights custom events |\n\n"
            "## Data flow\n\n"
            "1. `POST /documents/upload` -> ingestion -> extraction -> persist draft + clarifications.\n"
            "2. UI polls `GET /documents/{id}/clarifications` and asks the next question.\n"
            "3. Answers posted to `POST /documents/{id}/chat` merge into the draft; clarifications recomputed.\n"
            "4. `POST /documents/{id}/draft` finalizes when clarifications is empty.\n\n"
            "## Azure mapping (suggested)\n\n"
            "- Container Apps / App Service for FastAPI (`/health` probe on port 8000).\n"
            "- Blob Storage for raw uploads; Cosmos DB / Azure SQL for drafts.\n"
            "- Azure OpenAI or Azure AI Foundry Agent Service for extraction + clarification.\n"
            "- Application Insights + Log Analytics for telemetry.\n"
        )
    if archetype == "rag-qa":
        return (
            f"# {title} -- Detailed Architecture (rag-qa)\n\n"
            "## Service boundaries\n\n"
            "| Module | Responsibility | Replace with |\n"
            "|---|---|---|\n"
            f"| `src/{package_name}/services/corpus_loader.py` | Enumerate `sample-corpus/`. | Azure AI Search / Cognitive Search client. |\n"
            f"| `src/{package_name}/services/qa_service.py` | Rank documents and produce an answer. | Azure OpenAI chat completions with retrieved context. |\n\n"
            "## Data flow\n\n"
            "1. `POST /qa/ask` -> `qa_service.answer_question` -> `corpus_loader.load_corpus`.\n"
            "2. Naive keyword ranker picks top-k; returned sources include title + excerpt.\n"
            "3. Production wiring replaces loader with an index client and ranker with an LLM call.\n\n"
            "## Azure mapping (suggested)\n\n"
            "- Container Apps / App Service for FastAPI.\n"
            "- Azure AI Search for the corpus index; Blob Storage for source docs.\n"
            "- Azure OpenAI for synthesis; Application Insights for telemetry.\n"
        )
    return f"# {title} -- Detailed Architecture\n\nSee `docs/architecture-overview.md` for the current scaffold view.\n"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PythonAgent:
    name = "python"
    display_name = "Python (FastAPI)"

    def emit(self, ctx: LanguageEmitContext) -> LanguageEmitResult:
        project_root = ctx.project_root
        package_name = _package_name_from_slug(ctx.slug)
        src_dir = project_root / "src" / package_name
        services_dir = src_dir / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        ctx.tests_dir.mkdir(parents=True, exist_ok=True)

        archetype = ctx.archetype if ctx.archetype in {"extraction-chat", "rag-qa", "api-service"} else "api-service"

        _write_text(src_dir / "__init__.py", "")
        _write_text(services_dir / "__init__.py", "")

        files: list[str] = [
            f"src/{package_name}/__init__.py",
            f"src/{package_name}/services/__init__.py",
        ]

        if archetype == "extraction-chat":
            _write_text(src_dir / "main.py", _EXTRACTION_MAIN)
            _write_text(src_dir / "models.py", _EXTRACTION_MODELS)
            _write_text(services_dir / "document_ingestion.py", _EXTRACTION_INGESTION)
            _write_text(services_dir / "extraction_service.py", _EXTRACTION_SERVICE)
            _write_text(services_dir / "clarification_service.py", _EXTRACTION_CLARIFICATION)
            _write_text(services_dir / "repository.py", _EXTRACTION_REPOSITORY)
            _write_text(services_dir / "session_service.py", _EXTRACTION_SESSION)
            corpus_dir = project_root / "sample-corpus"
            corpus_dir.mkdir(parents=True, exist_ok=True)
            _write_text(corpus_dir / "README.md", _SAMPLE_CORPUS_README)
            _write_text(corpus_dir / "manifest.json", _SAMPLE_CORPUS_MANIFEST)
            files.extend([
                f"src/{package_name}/main.py",
                f"src/{package_name}/models.py",
                f"src/{package_name}/services/document_ingestion.py",
                f"src/{package_name}/services/extraction_service.py",
                f"src/{package_name}/services/clarification_service.py",
                f"src/{package_name}/services/repository.py",
                f"src/{package_name}/services/session_service.py",
                "sample-corpus/README.md",
                "sample-corpus/manifest.json",
            ])
        elif archetype == "rag-qa":
            _write_text(src_dir / "main.py", _RAG_MAIN)
            _write_text(src_dir / "models.py", _RAG_MODELS)
            _write_text(services_dir / "qa_service.py", _RAG_QA_SERVICE)
            _write_text(services_dir / "corpus_loader.py", _RAG_CORPUS_LOADER)
            corpus_dir = project_root / "sample-corpus"
            corpus_dir.mkdir(parents=True, exist_ok=True)
            _write_text(corpus_dir / "README.md", _SAMPLE_CORPUS_README)
            _write_text(corpus_dir / "manifest.json", _SAMPLE_CORPUS_MANIFEST)
            files.extend([
                f"src/{package_name}/main.py",
                f"src/{package_name}/models.py",
                f"src/{package_name}/services/qa_service.py",
                f"src/{package_name}/services/corpus_loader.py",
                "sample-corpus/README.md",
                "sample-corpus/manifest.json",
            ])
        else:
            _write_text(src_dir / "main.py", _API_MAIN)
            _write_text(src_dir / "models.py", _API_MODELS)
            _write_text(services_dir / "copilot_service.py", _API_SERVICE)
            files.extend([
                f"src/{package_name}/main.py",
                f"src/{package_name}/models.py",
                f"src/{package_name}/services/copilot_service.py",
            ])

        _write_text(project_root / "requirements.txt", _build_requirements(archetype))
        _write_text(project_root / "pyproject.toml", _build_pyproject(ctx.title, archetype))
        _write_text(ctx.tests_dir / "test_generated_project.py", _build_test(package_name, archetype))
        _write_text(
            project_root / "README.md",
            _build_readme(ctx.title, ctx.source_brd, ctx.slug, ctx.requirements,
                          ctx.enable_observability, package_name, archetype, files),
        )
        _write_text(project_root / "DEPLOY.md", _build_deploy(ctx.slug, ctx.enable_observability, package_name))

        if archetype in {"extraction-chat", "rag-qa"}:
            _write_text(
                project_root / "docs" / "detailed-architecture.md",
                _build_detailed_architecture(ctx.title, archetype, package_name),
            )

        files.extend([
            "requirements.txt",
            "pyproject.toml",
            "tests/test_generated_project.py",
            "README.md",
            "DEPLOY.md",
        ])

        bullets = {
            "extraction-chat": [
                "- Document upload + structured extraction + clarification loop + chat endpoints",
                "- In-memory repository and session services (swap for Cosmos DB / Azure SQL)",
                "- Sample corpus folder and detailed-architecture doc",
            ],
            "rag-qa": [
                "- /qa/ask endpoint with keyword-rank QA stub + corpus loader",
                "- Sample corpus folder and detailed-architecture doc",
            ],
            "api-service": [
                "- Python 3.11+ FastAPI starter with health endpoint",
                "- pytest scaffold validating generated project shape",
            ],
        }

        return LanguageEmitResult(
            files_written=files,
            readme_bullets=bullets.get(archetype, bullets["api-service"]),
            primary_source_path=f"src/{package_name}/main.py",
        )


AGENT = PythonAgent()
