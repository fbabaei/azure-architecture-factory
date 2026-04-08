#!/usr/bin/env python3
"""
Dedicated Azure Architecture Factory Portal Server
Serves factory projects, BRD intake API, and project management dashboard
"""

import json
import hmac
import logging
import os
import pathlib
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse


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
CSA_TEMPLATE_ROOT = (FACTORY_REPO_ROOT.parent / "csa-roadmap-template").resolve()
PORT = 5501
BIND_ADDRESS = "127.0.0.1"
MAX_REQUEST_BYTES = 1_000_000  # 1 MB intake payload limit
ALLOWED_ORIGIN = os.environ.get("FACTORY_PORTAL_ALLOWED_ORIGIN", f"http://{BIND_ADDRESS}:{PORT}")
API_KEY_ENV = "FACTORY_PORTAL_API_KEY"

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

        if request_path.startswith("/api/brd-runs/"):
            run_id = request_path.split("/")[-1]
            return self._handle_run_status(run_id)

        if request_path.startswith("/api/project-analysis/"):
            slug = request_path.split("/")[-1]
            return self._handle_project_analysis(slug)

        if request_path == "/factory-projects.generated.json":
            return self._serve_json_feed()

        # Default file serving
        return super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        path = urlparse(self.path).path
        if path == "/api/brd-intake":
            if not self._require_api_key_for_mutation():
                return
            return self._handle_brd_intake()
        if path == "/api/brd-upload":
            if not self._require_api_key_for_mutation():
                return
            return self._handle_brd_upload()

        self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _require_api_key_for_mutation(self) -> bool:
        """Optionally require API key for mutation endpoints when configured."""
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if not expected_key:
            return True

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
                "brdFile": str(brd_path),
            },
            202,
        )

    def _run_pipeline(self, run_id, brd_path):
        """Execute the pipeline in background"""
        pipeline_script = (
            FACTORY_REPO_ROOT / ".." / "csa-roadmap-template" / "scripts" / "process_brd_pipeline.py"
        ).resolve()

        with RUNS_LOCK:
            RUNS[run_id]["status"] = "running"
            RUNS[run_id]["startedAt"] = datetime.utcnow().isoformat() + "Z"

        try:
            python_exe = sys.executable
            cmd = [python_exe, str(pipeline_script), "--brd", brd_path]

            result = subprocess.run(
                cmd,
                cwd=str(FACTORY_REPO_ROOT.parent / "csa-roadmap-template"),
                capture_output=True,
                text=True,
                check=False,
            )

            with RUNS_LOCK:
                RUNS[run_id].update(
                    {
                        "status": "completed",
                        "finishedAt": datetime.utcnow().isoformat() + "Z",
                        "returnCode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "command": " ".join(cmd),
                    }
                )

                # Parse pipeline result
                if result.returncode == 0 and result.stdout:
                    try:
                        output = json.loads(result.stdout)
                        RUNS[run_id]["result"] = output
                    except json.JSONDecodeError:
                        RUNS[run_id]["result"] = {"status": "error", "message": "Invalid output"}

            logger.info(f"Pipeline completed for run {run_id}: returnCode={result.returncode}")
        except Exception as e:
            logger.exception(f"Pipeline error for run {run_id}: {e}")
            with RUNS_LOCK:
                RUNS[run_id].update(
                    {
                        "status": "failed",
                        "finishedAt": datetime.utcnow().isoformat() + "Z",
                        "returnCode": -1,
                        "stderr": str(e),
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

    def _serve_json_feed(self):
        """Serve the generated project feed from the CSA roadmap repo."""
        feed_path = CSA_TEMPLATE_ROOT / "factory-projects.generated.json"

        if not feed_path.exists():
            return self._send_json({"generatedAt": None, "projects": []}, 200)

        try:
            payload = json.loads(feed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to read project feed: %s", exc)
            return self._send_json({"error": "Invalid project feed"}, 500)

        return self._send_json(payload, 200)

    def _handle_project_analysis(self, slug):
        """Generate and serve analysis for a project by slug."""
        feed_path = CSA_TEMPLATE_ROOT / "factory-projects.generated.json"
        
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key")
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
