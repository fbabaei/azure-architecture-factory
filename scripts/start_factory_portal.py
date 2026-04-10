#!/usr/bin/env python3
"""
Dedicated Azure Architecture Factory Portal Server
Serves factory projects, BRD intake API, and project management dashboard
"""

import base64
import io
import json
import hmac
import logging
import os
import pathlib
import re
import struct
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    from local_brd_runner import process_brd_document
except ModuleNotFoundError:
    from scripts.local_brd_runner import process_brd_document


def _parse_multipart_form(content_type: str, body: bytes) -> dict:
    """Parse multipart/form-data body without the removed cgi module.
    Returns {field_name: {"data": bytes, "filename": str | None}}.
    """
    boundary = None
    for token in content_type.split(";"):
        token = token.strip()
        if token.lower().startswith("boundary="):
            boundary = token[9:].strip().strip('"')
            break
    if not boundary:
        return {}

    delimiter = ("--" + boundary).encode()
    fields: dict = {}

    for raw_part in body.split(delimiter)[1:]:
        if raw_part.startswith(b"--"):
            break  # end delimiter
        sep = b"\r\n\r\n" if b"\r\n\r\n" in raw_part else b"\n\n"
        if sep not in raw_part:
            continue
        header_bytes, data = raw_part.split(sep, 1)
        data = data.rstrip(b"\r\n")

        name: str | None = None
        filename: str | None = None
        for line in header_bytes.decode("utf-8", errors="replace").splitlines():
            if "Content-Disposition" in line:
                for tok in line.split(";"):
                    tok = tok.strip()
                    if tok.startswith("name="):
                        name = tok[5:].strip().strip('"')
                    elif tok.startswith("filename="):
                        filename = tok[9:].strip().strip('"')
        if name:
            fields[name] = {"data": data, "filename": filename}

    return fields


# Configuration
FACTORY_REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
PORT = int(os.environ.get("FACTORY_PORTAL_PORT", "5501"))
BIND_ADDRESS = os.environ.get("FACTORY_PORTAL_BIND", "127.0.0.1")
MAX_REQUEST_BYTES = 1_000_000  # 1 MB intake payload limit
ALLOWED_ORIGIN = os.environ.get("FACTORY_PORTAL_ALLOWED_ORIGIN", f"http://{BIND_ADDRESS}:{PORT}")
API_KEY_ENV = "FACTORY_PORTAL_API_KEY"
MAX_PREVIEW_BYTES = 512_000
TEXT_PREVIEW_SUFFIXES = {
    ".md", ".txt", ".py", ".json", ".yaml", ".yml", ".bicep", ".toml", ".ini",
    ".cfg", ".csv", ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".sh", ".ps1",
    ".xml", ".drawio",
}

# Entra ID (Azure AD) OAuth 2.0 configuration
# Set these env vars to enable Entra ID auth on mutation endpoints.
# When unset, Entra ID auth is skipped (local development mode).
ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID", "").strip()
ENTRA_CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID", "").strip()  # App registration Application (client) ID
ENTRA_AUDIENCE = os.environ.get("ENTRA_AUDIENCE", "").strip() or ENTRA_CLIENT_ID  # Defaults to client ID


# ── Entra ID JWT validation (stdlib + minimal base64 decode) ─────────────────

class _JwksCache:
    """Fetches and caches Microsoft OIDC signing keys."""

    def __init__(self, tenant_id: str, ttl: int = 3600):
        self._oidc_url = (
            f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
        )
        self._keys: dict[str, dict] = {}
        self._expires_at: float = 0
        self._ttl = ttl
        self._lock = threading.Lock()

    def get_key(self, kid: str) -> dict | None:
        with self._lock:
            if time.monotonic() >= self._expires_at:
                self._refresh()
            return self._keys.get(kid)

    def _refresh(self):
        try:
            oidc = json.loads(urlopen(Request(self._oidc_url), timeout=10).read())
            jwks_uri = oidc["jwks_uri"]
            jwks = json.loads(urlopen(Request(jwks_uri), timeout=10).read())
            self._keys = {k["kid"]: k for k in jwks.get("keys", [])}
            self._expires_at = time.monotonic() + self._ttl
        except (URLError, KeyError, json.JSONDecodeError) as exc:
            logging.getLogger(__name__).warning("JWKS refresh failed: %s", exc)


def _b64url_decode(data: str) -> bytes:
    """Base64url decode (no padding required)."""
    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data)


def _int_from_bytes(b: bytes) -> int:
    return int.from_bytes(b, byteorder="big")


def _rsa_verify(n_b64: str, e_b64: str, signature: bytes, message: bytes) -> bool:
    """Verify RSA PKCS#1 v1.5 signature using stdlib only.
    Constructs the public key from JWK n/e and performs raw RSA.
    """
    n = _int_from_bytes(_b64url_decode(n_b64))
    e = _int_from_bytes(_b64url_decode(e_b64))
    sig_int = _int_from_bytes(signature)
    # RSA public operation: sig^e mod n
    decrypted = pow(sig_int, e, n)
    # Convert back to bytes (same length as modulus)
    key_len = (n.bit_length() + 7) // 8
    em = decrypted.to_bytes(key_len, byteorder="big")
    # PKCS#1 v1.5: 0x00 0x01 [padding 0xff...] 0x00 [DigestInfo + hash]
    # We extract the hash from the end and compare
    import hashlib
    expected_hash = hashlib.sha256(message).digest()
    # DigestInfo prefix for SHA-256 (DER encoded)
    digest_info_prefix = bytes.fromhex(
        "3031300d060960864801650304020105000420"
    )
    expected_suffix = digest_info_prefix + expected_hash
    # Verify padding structure
    if not em.startswith(b"\x00\x01"):
        return False
    # Find 0x00 separator after padding
    sep_idx = em.index(b"\x00", 2)
    padding = em[2:sep_idx]
    if not all(b == 0xFF for b in padding):
        return False
    actual_suffix = em[sep_idx + 1:]
    return actual_suffix == expected_suffix


def _validate_entra_token(auth_header: str, jwks_cache: _JwksCache) -> dict | str:
    """Validate an Entra ID bearer token.
    Returns the decoded claims dict on success, or an error string on failure.
    """
    if not auth_header.lower().startswith("bearer "):
        return "Authorization header must use Bearer scheme"

    token = auth_header[7:].strip()
    parts = token.split(".")
    if len(parts) != 3:
        return "Malformed JWT"

    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
        signature = _b64url_decode(parts[2])
    except Exception:
        return "Failed to decode JWT"

    # Verify algorithm
    alg = header.get("alg", "")
    if alg != "RS256":
        return f"Unsupported algorithm: {alg}"

    # Look up signing key
    kid = header.get("kid", "")
    key = jwks_cache.get_key(kid)
    if not key:
        return "Signing key not found"

    # Verify signature
    message = f"{parts[0]}.{parts[1]}".encode("ascii")
    if not _rsa_verify(key["n"], key["e"], signature, message):
        return "Invalid token signature"

    # Verify claims
    now = time.time()
    if payload.get("exp", 0) < now:
        return "Token expired"
    if payload.get("nbf", 0) > now + 300:  # 5 min clock skew
        return "Token not yet valid"

    # Verify audience
    token_aud = payload.get("aud", "")
    if isinstance(token_aud, list):
        if ENTRA_AUDIENCE not in token_aud:
            return "Invalid audience"
    elif token_aud != ENTRA_AUDIENCE:
        return "Invalid audience"

    # Verify issuer (v2.0 endpoint)
    expected_issuer = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0"
    if payload.get("iss") != expected_issuer:
        return "Invalid issuer"

    return payload


# Initialize JWKS cache (only when Entra ID is configured)
_jwks_cache: _JwksCache | None = None
if ENTRA_TENANT_ID and ENTRA_CLIENT_ID:
    _jwks_cache = _JwksCache(ENTRA_TENANT_ID)

# Thread-safe run tracking
RUNS = {}
RUNS_LOCK = threading.Lock()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def _sanitize_brd_filename(raw_name: str) -> str:
    """Return a safe BRD filename constrained to a simple .md basename."""
    name = pathlib.Path((raw_name or "brd.md").strip()).name
    if not name:
        raise ValueError("Filename is empty")
    if not name.lower().endswith(".md"):
        name = f"{name}.md"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise ValueError("Filename contains invalid characters")
    return name


class FactoryPortalHandler(SimpleHTTPRequestHandler):
    """HTTP handler for factory portal with BRD intake API"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FACTORY_REPO_ROOT), **kwargs)

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        request_path = parsed.path

        if request_path == "/":
            self.send_response(302)
            self.send_header("Location", "/factory-portal.html")
            self.end_headers()
            return

        if request_path == "/api/brd-runs":
            return self._handle_runs_list()

        if request_path.startswith("/api/brd-runs/") and request_path.endswith("/project"):
            run_id = request_path.split("/")[-2]
            return self._handle_run_project(run_id)

        if request_path.startswith("/api/brd-runs/"):
            run_id = request_path.split("/")[-1]
            return self._handle_run_status(run_id)

        if request_path.startswith("/api/project-analysis/"):
            slug = request_path.split("/")[-1]
            return self._handle_project_analysis(slug)

        if request_path.startswith("/api/projects/") and request_path.endswith("/files"):
            if not self._require_auth_for_mutation():
                return
            slug = request_path.split("/")[-2]
            return self._handle_project_files(slug)

        if request_path.startswith("/api/projects/") and request_path.endswith("/download"):
            if not self._require_auth_for_mutation():
                return
            slug = request_path.split("/")[-2]
            return self._handle_project_download(slug)

        if request_path.startswith("/api/projects/") and request_path.endswith("/file"):
            if not self._require_auth_for_mutation():
                return
            slug = request_path.split("/")[-2]
            return self._handle_project_file_preview(slug, parsed.query)

        if request_path == "/factory-projects.generated.json":
            return self._serve_json_feed()

        # Default file serving
        return super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        path = urlparse(self.path).path
        if path == "/api/brd-intake":
            if not self._require_auth_for_mutation():
                return
            return self._handle_brd_intake()
        if path == "/api/brd-upload":
            if not self._require_auth_for_mutation():
                return
            return self._handle_brd_upload()

        self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key, Authorization")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _require_auth_for_mutation(self) -> bool:
        """Require Entra ID bearer token or API key for mutation endpoints.

        Auth precedence:
        1. If Entra ID env vars are set → validate Bearer token
        2. Else if API key env var is set → validate X-Factory-Api-Key header
        3. If neither is set → allow (local development mode)
        """
        # --- Entra ID (preferred) ---
        if _jwks_cache is not None:
            auth_header = self.headers.get("Authorization", "")
            if not auth_header:
                self._send_json(
                    {"error": "Missing Authorization header. Provide a Bearer token."},
                    401,
                )
                return False
            result = _validate_entra_token(auth_header, _jwks_cache)
            if isinstance(result, str):
                self._send_json({"error": result}, 401)
                return False
            # Token is valid — attach claims for downstream use
            self._entra_claims = result
            return True

        # --- Static API key (fallback) ---
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if not expected_key:
            return True  # No auth configured — local dev mode

        provided_key = self.headers.get("X-Factory-Api-Key", "")
        if not hmac.compare_digest(provided_key, expected_key):
            self._send_json({"error": "Unauthorized"}, 401)
            return False
        return True

    def _safe_content_length(self) -> int | None:
        """Return validated content length or emit an error response."""
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "Invalid Content-Length"}, 400)
            return None

        if content_length <= 0:
            self._send_json({"error": "Missing request body"}, 400)
            return None

        if content_length > MAX_REQUEST_BYTES:
            self._send_json({"error": f"Payload too large (max {MAX_REQUEST_BYTES} bytes)"}, 413)
            return None

        return content_length

    def _handle_brd_intake(self):
        """Handle BRD intake submission (JSON body)"""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        try:
            file_name = _sanitize_brd_filename(payload.get("fileName", "brd.md"))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        content = payload.get("content", "").strip()

        if not file_name or not content:
            self._send_json({"error": "Missing fileName or content"}, 400)
            return

        return self._save_and_start_run(file_name, content)

    def _save_and_start_run(self, file_name: str, content: str):
        """Save BRD file and launch pipeline worker thread."""
        brds_dir = FACTORY_REPO_ROOT / "docs" / "intake"
        brds_dir.mkdir(parents=True, exist_ok=True)
        brd_path = (brds_dir / file_name).resolve()

        if brds_dir.resolve() not in brd_path.parents:
            self._send_json({"error": "Resolved BRD path is outside intake directory"}, 400)
            return

        try:
            brd_path.write_text(content, encoding="utf-8")
            logger.info(f"Saved BRD: {brd_path}")
        except Exception as e:
            self._send_json({"error": f"Failed to save BRD: {e}"}, 500)
            return

        # Create run entry
        run_id = str(uuid.uuid4())
        with RUNS_LOCK:
            RUNS[run_id] = {
                "id": run_id,
                "status": "queued",
                "createdAt": datetime.utcnow().isoformat() + "Z",
                "brdFile": str(brd_path),
                "startedAt": None,
                "finishedAt": None,
                "returnCode": None,
                "stdout": None,
                "stderr": None,
                "command": None,
                "result": None,
            }

        # Spawn pipeline worker thread
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(run_id, str(brd_path)),
            daemon=True,
        )
        thread.start()

        self._send_json(
            {
                "id": run_id,
                "status": "queued",
                "message": "BRD received and pipeline started.",
                "brdFile": f"docs/intake/{file_name}",
            },
            202,
        )

    def _run_pipeline(self, run_id, brd_path):
        """Execute the pipeline in background"""
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "running"
            RUNS[run_id]["startedAt"] = datetime.utcnow().isoformat() + "Z"

        try:
            output = process_brd_document(FACTORY_REPO_ROOT, pathlib.Path(brd_path), run_id)

            with RUNS_LOCK:
                RUNS[run_id].update(
                    {
                        "status": "completed",
                        "finishedAt": datetime.utcnow().isoformat() + "Z",
                        "returnCode": 0,
                        "stdout": None,
                        "stderr": None,
                        "command": "azure_native_factory_runner",
                        "result": output,
                    }
                )

            logger.info(f"Pipeline completed for run {run_id}: returnCode=0")
        except Exception as e:
            logger.exception(f"Pipeline error for run {run_id}: {e}")
            with RUNS_LOCK:
                RUNS[run_id].update(
                    {
                        "status": "failed",
                        "finishedAt": datetime.utcnow().isoformat() + "Z",
                        "returnCode": -1,
                        "stderr": str(e),
                        "result": {"status": "failed", "message": str(e)},
                    }
                )

    def _handle_brd_upload(self):
        """Handle multipart/form-data BRD file upload."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json({"error": "Expected multipart/form-data"}, 415)
            return

        content_length = self._safe_content_length()
        if content_length is None:
            return
        raw_body = self.rfile.read(content_length)

        try:
            fields = _parse_multipart_form(content_type, raw_body)
        except Exception as exc:
            self._send_json({"error": f"Failed to parse multipart body: {exc}"}, 400)
            return

        project_name_field = (fields.get("project_name") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        brd_field = fields.get("brd_file")

        if not brd_field:
            self._send_json({"error": "Missing brd_file field"}, 400)
            return

        try:
            content = brd_field["data"].decode("utf-8")
        except UnicodeDecodeError:
            self._send_json({"error": "BRD file must be UTF-8 encoded text"}, 400)
            return

        if not content.strip():
            self._send_json({"error": "Uploaded BRD file is empty"}, 400)
            return

        uploaded_filename = brd_field.get("filename") or "brd.md"
        try:
            if project_name_field:
                file_name = _sanitize_brd_filename(project_name_field)
            else:
                file_name = _sanitize_brd_filename(uploaded_filename)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        return self._save_and_start_run(file_name, content)

    def _handle_run_status(self, run_id):
        """Handle run status query"""
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run:
            self._send_json({"error": "Run not found"}, 404)
            return

        # Return a sanitized status payload to avoid leaking command output and local paths.
        safe_run = {
            "id": run.get("id"),
            "status": run.get("status"),
            "createdAt": run.get("createdAt"),
            "startedAt": run.get("startedAt"),
            "finishedAt": run.get("finishedAt"),
            "returnCode": run.get("returnCode"),
            "result": run.get("result"),
        }
        self._send_json(safe_run, 200)

    def _handle_runs_list(self):
        """Handle list of all tracked runs."""
        with RUNS_LOCK:
            runs = list(RUNS.values())

        safe_runs = []
        for run in sorted(runs, key=lambda item: item.get("createdAt") or "", reverse=True):
            safe_runs.append(
                {
                    "id": run.get("id"),
                    "brdFile": pathlib.Path(run.get("brdFile") or "").name,
                    "status": run.get("status"),
                    "createdAt": run.get("createdAt"),
                    "startedAt": run.get("startedAt"),
                    "finishedAt": run.get("finishedAt"),
                    "returnCode": run.get("returnCode"),
                }
            )

        self._send_json({"runs": safe_runs}, 200)

    def _handle_run_project(self, run_id):
        """Return the generated project payload for a specific run."""
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run:
            self._send_json({"error": "Run not found"}, 404)
            return

        safe_run = {
            "id": run.get("id"),
            "status": run.get("status"),
            "createdAt": run.get("createdAt"),
            "startedAt": run.get("startedAt"),
            "finishedAt": run.get("finishedAt"),
            "returnCode": run.get("returnCode"),
            "result": run.get("result"),
        }

        result = run.get("result") or {}
        response = {
            "run": safe_run,
            "project": result.get("project"),
            "analysis": result.get("analysis"),
        }

        if run.get("status") in {"queued", "running"}:
            self._send_json(response, 202)
            return

        if not result:
            response["warning"] = "Run completed without a project payload"

        self._send_json(response, 200)

    def _serve_json_feed(self):
        """Serve the generated project feed from the factory repo."""
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"

        if not feed_path.exists():
            return self._send_json({"generatedAt": None, "projects": []}, 200)

        try:
            payload = json.loads(feed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to read project feed: %s", exc)
            return self._send_json({"error": "Invalid project feed"}, 500)

        return self._send_json(payload, 200)

    def _resolve_project_root(self, slug: str) -> pathlib.Path | None:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", slug or ""):
            return None
        project_root = (FACTORY_REPO_ROOT / "projects" / slug).resolve()
        projects_root = (FACTORY_REPO_ROOT / "projects").resolve()
        if projects_root not in project_root.parents:
            return None
        if not project_root.exists() or not project_root.is_dir():
            return None
        return project_root

    def _handle_project_files(self, slug: str):
        """Return a recursive file listing for a generated project."""
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        files = []
        for file_path in sorted(project_root.rglob("*")):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(project_root).as_posix()
            files.append(
                {
                    "path": relative,
                    "size": file_path.stat().st_size,
                    "previewable": file_path.suffix.lower() in TEXT_PREVIEW_SUFFIXES,
                }
            )

        return self._send_json({"project": slug, "files": files}, 200)

    def _handle_project_file_preview(self, slug: str, query: str):
        """Return a text preview for a project file."""
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        relative_path = (parse_qs(query).get("path") or [""])[0]
        if not relative_path:
            return self._send_json({"error": "Missing path query parameter"}, 400)

        requested_path = (project_root / relative_path).resolve()
        if project_root not in requested_path.parents or not requested_path.is_file():
            return self._send_json({"error": "File not found"}, 404)

        if requested_path.suffix.lower() not in TEXT_PREVIEW_SUFFIXES:
            return self._send_json({"error": "File type is not previewable"}, 415)

        if requested_path.stat().st_size > MAX_PREVIEW_BYTES:
            return self._send_json({"error": f"File too large to preview (max {MAX_PREVIEW_BYTES} bytes)"}, 413)

        try:
            content = requested_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._send_json({"error": "Preview supports UTF-8 text files only"}, 415)

        return self._send_json(
            {
                "project": slug,
                "path": requested_path.relative_to(project_root).as_posix(),
                "content": content,
            },
            200,
        )

    def _handle_project_download(self, slug: str):
        """Stream a ZIP archive for a generated project."""
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(project_root.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, arcname=f"{slug}/{file_path.relative_to(project_root).as_posix()}")

        payload = archive_buffer.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{slug}.zip"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        return

    def _handle_project_analysis(self, slug):
        """Generate and serve analysis for a project by slug."""
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"
        
        if not feed_path.exists():
            return self._send_json({"error": "Project feed not found"}, 404)
        
        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
            projects = feed.get("projects", [])
            project = next((p for p in projects if p.get("slug") == slug), None)
            
            if not project:
                return self._send_json({"error": f"Project '{slug}' not found"}, 404)
            
            # Generate analysis from project metadata
            analysis = self._generate_project_analysis(project)
            return self._send_json(analysis, 200)
        except json.JSONDecodeError:
            return self._send_json({"error": "Invalid project feed"}, 500)

    def _generate_project_analysis(self, project):
        """Generate analysis content for a project from its metadata."""
        title = project.get("title", project.get("slug", "Unknown"))
        generated_from = project.get("generatedFrom", "Unknown BRD")
        status = project.get("status", "Unknown")
        
        # Build generic analysis based on project metadata
        analysis = {
            "title": title,
            "projectSlug": project.get("slug", ""),
            "generatedFrom": generated_from,
            "designChoice": f"Generated from: {generated_from}",
            "benefits": [
                "Automated architecture generation from business requirements",
                "Consistent application of Azure best practices",
                "Infrastructure as Code generated and validated",
            ],
            "alternativeConsidered": "Manual architecture design (rejected for time and consistency)",
            "status": status,
        }
        
        return analysis

    def _send_json(self, payload, status=200):
        """Send JSON response"""
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def end_headers(self):
        """Add CORS headers to all responses"""
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key, Authorization")
        self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format, *args):
        """Custom logging"""
        logger.info("%s - %s" % (self.client_address[0], format % args))


def main():
    httpd = HTTPServer((BIND_ADDRESS, PORT), FactoryPortalHandler)
    httpd.allow_reuse_address = True

    print("\n" + "=" * 80)
    print("AZURE ARCHITECTURE FACTORY - DEDICATED PORTAL")
    print("=" * 80)
    print(f"\nFactory Portal:     http://{BIND_ADDRESS}:{PORT}/factory-portal.html")
    print(f"BRD Intake API:     http://{BIND_ADDRESS}:{PORT}/api/brd-intake")
    print(f"Project Directory:  http://{BIND_ADDRESS}:{PORT}/projects/")
    if _jwks_cache:
        print(f"Auth:               Entra ID (tenant={ENTRA_TENANT_ID}, client={ENTRA_CLIENT_ID})")
    elif os.environ.get(API_KEY_ENV, "").strip():
        print("Auth:               Static API key")
    else:
        print("Auth:               None (local dev mode)")
    print("\nYou can now:")
    print("  • Submit BRDs via the portal")
    print("  • View generated projects in real-time")
    print("  • Monitor pipeline execution status")
    print("  • Access project documentation and architecture")
    print("\nTip: Press Ctrl+C to stop the server.")
    print("=" * 80 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
