#!/usr/bin/env python3
"""
Dedicated Azure Architecture Factory Portal Server
Serves factory projects, BRD intake API, and project management dashboard
"""

import json
import logging
import pathlib
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse


# Configuration
FACTORY_REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
CSA_TEMPLATE_ROOT = (FACTORY_REPO_ROOT.parent / "csa-roadmap-template").resolve()
PORT = 5501
BIND_ADDRESS = "127.0.0.1"

# Thread-safe run tracking
RUNS = {}
RUNS_LOCK = threading.Lock()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


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

        if request_path == "/factory-projects.generated.json":
            return self._serve_json_feed()

        # Default file serving
        return super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        if urlparse(self.path).path == "/api/brd-intake":
            return self._handle_brd_intake()

        self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_brd_intake(self):
        """Handle BRD intake submission"""
        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        file_name = payload.get("fileName", "brd.md").strip()
        content = payload.get("content", "").strip()

        if not file_name or not content:
            self._send_json({"error": "Missing fileName or content"}, 400)
            return

        # Save BRD file
        brds_dir = FACTORY_REPO_ROOT / "docs" / "intake"
        brds_dir.mkdir(parents=True, exist_ok=True)
        brd_path = brds_dir / file_name

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

    def _handle_run_status(self, run_id):
        """Handle run status query"""
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run:
            self._send_json({"error": "Run not found"}, 404)
            return

        self._send_json(run, 200)

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

    def _send_json(self, payload, status=200):
        """Send JSON response"""
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(response)

    def end_headers(self):
        """Add CORS headers to all responses"""
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        """Custom logging"""
        logger.info("%s - %s" % (self.client_address[0], format % args))


def main():
    """Start the factory portal server"""
    server_address = (BIND_ADDRESS, PORT)
    httpd = HTTPServer(server_address, FactoryPortalHandler)

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
