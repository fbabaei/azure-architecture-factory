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
BIND_ADDRESS = os.environ.get("FACTORY_PORTAL_BIND", "0.0.0.0")
MAX_REQUEST_BYTES = 1_000_000  # 1 MB intake payload limit
ALLOWED_ORIGIN = os.environ.get("FACTORY_PORTAL_ALLOWED_ORIGIN", f"http://localhost:{PORT}")
API_KEY_ENV = "FACTORY_PORTAL_API_KEY"
PORTAL_PATH_ALIASES = {"/portal", "/p"}
CSA_COPILOT_API_BASE = os.environ.get("CSA_COPILOT_API_BASE", "").strip().rstrip("/")
CSA_COPILOT_API_KEY = os.environ.get("CSA_COPILOT_API_KEY", "").strip()
CSA_COPILOT_TIMEOUT_SECONDS = int(os.environ.get("CSA_COPILOT_TIMEOUT_SECONDS", "20"))
# Optional: set this to a Teams Incoming Webhook URL to receive a notification
# whenever a user submits a token request.
TEAMS_WEBHOOK_URL = os.environ.get("FACTORY_PORTAL_TEAMS_WEBHOOK_URL", "")
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


# ── Issued-token helpers ─────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _notify_teams_token_request(req_id: str, sub: str, reason: str) -> None:
    """Fire-and-forget Teams Incoming Webhook notification for a new token request.

    Requires the FACTORY_PORTAL_TEAMS_WEBHOOK_URL env var to be set.
    Failures are logged but never surface to the caller.
    """
    if not TEAMS_WEBHOOK_URL:
        return
    import threading
    def _send():
        try:
            portal_url = f"http://localhost:{PORT}/factory-portal.html"
            card = {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "🔑 New Portal Token Request",
                                "weight": "Bolder",
                                "size": "Medium",
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "From",   "value": sub or "(unknown)"},
                                    {"title": "Reason", "value": reason or "(none provided)"},
                                    {"title": "ID",     "value": req_id},
                                ],
                            },
                            {
                                "type": "TextBlock",
                                "text": f"Open the admin panel on the portal to review and issue a token.",
                                "wrap": True,
                                "color": "Accent",
                            },
                        ],
                        "actions": [{
                            "type": "Action.OpenUrl",
                            "title": "Open Admin Panel",
                            "url": portal_url,
                        }],
                    },
                }],
            }
            data = json.dumps(card).encode("utf-8")
            req = Request(TEAMS_WEBHOOK_URL, data=data,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=8) as resp:  # noqa: S310
                logger.info("Teams notification sent for token request %s: HTTP %s", req_id, resp.status)
        except Exception as exc:
            logger.warning("Teams notification failed for token request %s: %s", req_id, exc)
    threading.Thread(target=_send, daemon=True).start()


def _issue_token(sub: str, ttl_seconds: int, max_uses: int, purpose: str) -> dict:
    """Create a signed, time-limited, usage-counted access token.

    Token format: <b64url(json_payload)>.<hmac_sha256_hex>
    The master FACTORY_PORTAL_API_KEY is the signing secret.
    Returns a dict with keys: token, jti, sub, exp, max_uses, purpose.
    Raises ValueError if the master key is not set.
    """
    master_key = os.environ.get(API_KEY_ENV, "").strip()
    if not master_key:
        raise ValueError("FACTORY_PORTAL_API_KEY must be set to issue tokens")

    now = time.time()
    jti = uuid.uuid4().hex
    exp = 0 if ttl_seconds == 0 else int(now + ttl_seconds)  # 0 = never expires
    payload = {
        "jti": jti,
        "sub": sub,
        "iat": int(now),
        "exp": exp,
        "max_uses": max_uses,
        "purpose": purpose,
    }
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(master_key.encode(), encoded_payload.encode(), "sha256").hexdigest()
    token = f"{encoded_payload}.{sig}"

    with _ISSUED_TOKENS_LOCK:
        _ISSUED_TOKENS[jti] = {
            "uses": 0,
            "max_uses": max_uses,
            "exp": exp,
            "sub": sub,
            "purpose": purpose,
        }

    logger.info("Issued token: jti=%s sub=%s purpose=%s max_uses=%s exp=%s",
                jti, sub, purpose, max_uses if max_uses > 0 else "unlimited", exp)
    return {"token": token, "jti": jti, "sub": sub, "exp": exp,
            "max_uses": max_uses, "purpose": purpose}


def _validate_issued_token(token: str) -> dict | str | None:
    """Validate an issued token. Returns claims dict on success, error string on failure."""
    master_key = os.environ.get(API_KEY_ENV, "").strip()
    if not master_key:
        return "No master key configured"

    if token.count(".") != 1:
        return None  # Not an issued-token format — let caller try master key

    encoded_payload, provided_sig = token.split(".", 1)
    expected_sig = hmac.new(master_key.encode(), encoded_payload.encode(), "sha256").hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return "Invalid token signature"

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except Exception:
        return "Failed to decode token payload"

    token_exp = payload.get("exp", 0)
    if token_exp != 0 and token_exp < time.time():
        return "Token expired"

    jti = payload.get("jti", "")
    max_uses = payload.get("max_uses", 0)

    with _ISSUED_TOKENS_LOCK:
        if jti not in _ISSUED_TOKENS:
            # Server restarted — re-register; counter resets to 0 (acceptable trade-off)
            _ISSUED_TOKENS[jti] = {
                "uses": 0,
                "max_uses": max_uses,
                "exp": payload.get("exp", 0),
                "sub": payload.get("sub", ""),
                "purpose": payload.get("purpose", ""),
            }
        entry = _ISSUED_TOKENS[jti]
        if max_uses > 0 and entry["uses"] >= max_uses:
            return f"Token usage limit reached ({max_uses} uses)"
        entry["uses"] += 1
        current_uses = entry["uses"]

    logger.info("Token used: jti=%s sub=%s purpose=%s uses=%d/%s",
                jti, payload.get("sub"), payload.get("purpose"),
                current_uses, max_uses if max_uses > 0 else "unlimited")
    return payload


# Initialize JWKS cache (only when Entra ID is configured)
_jwks_cache: _JwksCache | None = None
if ENTRA_TENANT_ID and ENTRA_CLIENT_ID:
    _jwks_cache = _JwksCache(ENTRA_TENANT_ID)

# Thread-safe run tracking
RUNS = {}
RUNS_LOCK = threading.Lock()

# ── Issued-token store (in-memory, usage-counted) ─────────────────────────────
# Structure: { jti: { "uses": int, "max_uses": int, "exp": float, "sub": str, "purpose": str } }
# Note: resets on server restart — intended for short-lived tokens only.
_ISSUED_TOKENS: dict = {}
_ISSUED_TOKENS_LOCK = threading.Lock()

# ── Token request queue (in-memory) ─────────────────────────────────────
# Structure: [ { "id": str, "sub": str, "reason": str, "requested_at": float, "status": str } ]
_TOKEN_REQUESTS: list = []
_TOKEN_REQUESTS_LOCK = threading.Lock()

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


def _coerce_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


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

        if request_path in PORTAL_PATH_ALIASES:
            self.send_response(302)
            self.send_header("Location", "/factory-portal.html")
            self.end_headers()
            return

        if request_path == "/api/brd-runs":
            return self._handle_runs_list()

        if request_path == "/api/csa-copilot/tools":
            if not self._require_auth_for_mutation():
                return
            return self._handle_csa_copilot_tools()

        if request_path.startswith("/api/brd-runs/") and request_path.endswith("/project"):
            run_id = request_path.split("/")[-2]
            return self._handle_run_project(run_id)

        if request_path.startswith("/api/brd-runs/"):
            run_id = request_path.split("/")[-1]
            return self._handle_run_status(run_id)

        if request_path.startswith("/api/project-analysis/"):
            slug = request_path.split("/")[-1]
            return self._handle_project_analysis(slug)

        if request_path.startswith("/api/project-operations/"):
            slug = request_path.split("/")[-1]
            return self._handle_project_operations(slug)

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

        if request_path == "/api/admin/tokens":
            if not self._require_admin_key():
                return
            return self._handle_token_list()

        if request_path == "/api/admin/token-requests":
            if not self._require_admin_key():
                return
            return self._handle_token_request_list()

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
        if path == "/api/admin/issue-token":
            if not self._require_admin_key():
                return
            return self._handle_issue_token()
        if path == "/api/token-request":
            return self._handle_submit_token_request()
        if path == "/api/csa-copilot/ask":
            if not self._require_auth_for_mutation():
                return
            return self._handle_csa_copilot_ask()

        self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key, Authorization")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _require_auth_for_mutation(self) -> bool:
        """Require Entra ID bearer token, issued token, or master API key.

        Auth precedence:
        1. If Entra ID env vars are set → validate Bearer token
        2. Else if API key env var is set:
           a. X-Factory-Api-Key contains a '.' → treat as issued token (HMAC-signed, expirable, usage-counted)
           b. Otherwise → compare directly as master key
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
            self._entra_claims = result
            return True

        # --- Issued token or master API key ---
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if not expected_key:
            return True  # No auth configured — local dev mode

        provided = self.headers.get("X-Factory-Api-Key", "")
        if not provided:
            self._send_json({"error": "Unauthorized"}, 401)
            return False

        # Issued tokens contain exactly one '.' (b64payload.hmac_hex)
        if provided.count(".") == 1:
            result = _validate_issued_token(provided)
            if isinstance(result, str):
                self._send_json({"error": result}, 401)
                return False
            if result is None:
                # Dot in string but not a valid issued-token format — fall through to master key check
                pass
            else:
                return True

        # Master key comparison
        if not hmac.compare_digest(provided, expected_key):
            self._send_json({"error": "Unauthorized"}, 401)
            return False
        return True

    def _require_admin_key(self) -> bool:
        """Require the master API key (not an issued token) for admin operations."""
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if not expected_key:
            return True  # No auth — local dev mode
        provided = self.headers.get("X-Factory-Api-Key", "")
        if not hmac.compare_digest(provided, expected_key):
            self._send_json({"error": "Admin access requires master API key"}, 403)
            return False
        return True

    def _handle_issue_token(self):
        """POST /api/admin/issue-token — create a signed, usage-counted token."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        sub = str(payload.get("sub", "")).strip()
        purpose = str(payload.get("purpose", "manual")).strip() or "manual"
        try:
            ttl_seconds = int(payload.get("ttl_seconds", 86400))
            max_uses = int(payload.get("max_uses", 5))
        except (TypeError, ValueError):
            self._send_json({"error": "ttl_seconds and max_uses must be integers"}, 400)
            return

        if ttl_seconds < 0 or ttl_seconds > 60 * 60 * 24 * 3650:  # 0 = never; max 10 years
            self._send_json({"error": "ttl_seconds must be 0 (never expires) or 1–315360000 (max 10 years)"}, 400)
            return
        if max_uses < 0 or max_uses > 10000:
            self._send_json({"error": "max_uses must be between 0 and 10000"}, 400)
            return

        try:
            result = _issue_token(sub, ttl_seconds, max_uses, purpose)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 500)
            return

        self._send_json(result, 201)

    def _handle_token_request_list(self):
        """GET /api/admin/token-requests — return all pending token requests."""
        with _TOKEN_REQUESTS_LOCK:
            requests_copy = list(_TOKEN_REQUESTS)
        self._send_json({"requests": requests_copy})

    def _handle_submit_token_request(self):
        """POST /api/token-request — public endpoint, no auth required."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        sub = str(payload.get("sub", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if not sub:
            self._send_json({"error": "sub (name or email) is required"}, 400)
            return

        # Enforce a simple request-rate limit: max 3 pending requests per sub
        with _TOKEN_REQUESTS_LOCK:
            pending_from_sub = sum(
                1 for r in _TOKEN_REQUESTS
                if r["sub"].lower() == sub.lower() and r["status"] == "pending"
            )
            if pending_from_sub >= 3:
                self._send_json({"error": "Too many pending requests from this address"}, 429)
                return
            req_id = uuid.uuid4().hex[:12]
            _TOKEN_REQUESTS.append({
                "id": req_id,
                "sub": sub,
                "reason": reason[:500],
                "requested_at": time.time(),
                "status": "pending",
            })

        logger.info("Token request submitted: id=%s sub=%s", req_id, sub)
        _notify_teams_token_request(req_id, sub, reason)
        self._send_json({"ok": True, "id": req_id,
                         "message": "Request submitted. You will receive your token via the admin."})

    def _handle_token_list(self):
        """GET /api/admin/tokens — return all issued tokens and their usage counters."""
        now = time.time()
        with _ISSUED_TOKENS_LOCK:
            tokens = [
                {
                    "jti": jti,
                    "sub": entry["sub"],
                    "purpose": entry["purpose"],
                    "uses": entry["uses"],
                    "max_uses": entry["max_uses"],
                    "exp": entry["exp"],
                    "expired": entry["exp"] != 0 and entry["exp"] < now,
                }
                for jti, entry in _ISSUED_TOKENS.items()
            ]
        tokens.sort(key=lambda t: t["exp"], reverse=True)
        self._send_json({"tokens": tokens})

    def _call_csa_companion(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        if not CSA_COPILOT_API_BASE:
            return 503, {"error": "CSA companion service is not configured."}

        url = f"{CSA_COPILOT_API_BASE}{path}"
        headers = {"Content-Type": "application/json"}
        if CSA_COPILOT_API_KEY:
            headers["x-api-key"] = CSA_COPILOT_API_KEY
        request_id = self.headers.get("x-request-id", str(uuid.uuid4()))
        headers["x-request-id"] = request_id

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        try:
            req = Request(url=url, data=data, method=method, headers=headers)
            with urlopen(req, timeout=CSA_COPILOT_TIMEOUT_SECONDS) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body)
        except URLError as exc:
            logger.warning("CSA companion request failed: %s %s (%s)", method, url, exc)
            return 502, {"error": "Failed to reach CSA companion service."}
        except json.JSONDecodeError:
            return 502, {"error": "CSA companion returned invalid JSON."}

    def _handle_csa_copilot_tools(self):
        status_code, payload = self._call_csa_companion("GET", "/api/copilot/tools")
        self._send_json(payload, status_code)

    def _handle_csa_copilot_ask(self):
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        question = str(payload.get("question", "")).strip()
        context = str(payload.get("context", "")).strip()
        session_id = str(payload.get("session_id", "")).strip()
        user_id = str(payload.get("user_id", "portal-user")).strip() or "portal-user"

        if len(question) < 3:
            self._send_json({"error": "question must be at least 3 characters"}, 400)
            return

        upstream_payload = {
            "question": question,
            "context": context,
            "session_id": session_id,
            "user_id": user_id,
        }
        status_code, response_payload = self._call_csa_companion("POST", "/api/copilot/ask", upstream_payload)
        self._send_json(response_payload, status_code)

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
        generation_options = {
            "enableObservability": _coerce_bool(payload.get("enableObservability"), default=True)
        }

        if not file_name or not content:
            self._send_json({"error": "Missing fileName or content"}, 400)
            return

        return self._save_and_start_run(file_name, content, generation_options)

    def _save_and_start_run(self, file_name: str, content: str, generation_options: dict | None = None):
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
                "generationOptions": generation_options or {},
            }

        # Spawn pipeline worker thread
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(run_id, str(brd_path), generation_options or {}),
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

    def _run_pipeline(self, run_id, brd_path, generation_options=None):
        """Execute the pipeline in background"""
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "running"
            RUNS[run_id]["startedAt"] = datetime.utcnow().isoformat() + "Z"

        try:
            output = process_brd_document(
                FACTORY_REPO_ROOT,
                pathlib.Path(brd_path),
                run_id,
                generation_options or {},
            )

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
        enable_observability_field = (fields.get("enable_observability") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
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

        generation_options = {
            "enableObservability": _coerce_bool(enable_observability_field, default=True)
        }

        return self._save_and_start_run(file_name, content, generation_options)

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

    def _handle_project_operations(self, slug):
        """Generate and serve operations/monitoring view for a project by slug."""
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"

        if not feed_path.exists():
            return self._send_json({"error": "Project feed not found"}, 404)

        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
            projects = feed.get("projects", [])
            project = next((p for p in projects if p.get("slug") == slug), None)

            if not project:
                return self._send_json({"error": f"Project '{slug}' not found"}, 404)

            operations = self._generate_project_operations(project)
            return self._send_json(operations, 200)
        except json.JSONDecodeError:
            return self._send_json({"error": "Invalid project feed"}, 500)

    def _generate_project_operations(self, project):
        """Generate operations metadata for portal display."""
        enable_observability = bool((project.get("options") or {}).get("enableObservability", False))
        monitoring_resources = [
            "Log Analytics Workspace",
            "Application Insights (workspace-based)",
            "Optional Azure Monitor Action Group",
        ] if enable_observability else [
            "No monitoring resources requested during intake",
        ]

        checklist = [
            "Deploy infra/main.bicep and capture deployment outputs",
            "Wire app telemetry to APPINSIGHTS_CONNECTION_STRING",
            "Validate /health endpoint and request traces",
            "Assign operations owner and alert routing",
        ] if enable_observability else [
            "Decide whether to enable observability for this project",
            "Add Application Insights and Log Analytics before production",
            "Define alert routing and operational ownership",
        ]

        return {
            "projectSlug": project.get("slug", ""),
            "title": project.get("title", project.get("slug", "Unknown")),
            "enableObservability": enable_observability,
            "monitoringResources": monitoring_resources,
            "checklist": checklist,
            "links": project.get("links", {}),
        }

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
    display_host = "localhost" if BIND_ADDRESS in {"0.0.0.0", "::"} else BIND_ADDRESS

    print("\n" + "=" * 80)
    print("AZURE ARCHITECTURE FACTORY - DEDICATED PORTAL")
    print("=" * 80)
    print(f"\nFactory Portal:     http://{display_host}:{PORT}/factory-portal.html")
    print(f"Friendly Alias:     http://{display_host}:{PORT}/portal")
    print(f"BRD Intake API:     http://{display_host}:{PORT}/api/brd-intake")
    print(f"CSA Companion API:  {CSA_COPILOT_API_BASE or '(not configured)'}")
    print(f"Project Directory:  http://{BIND_ADDRESS}:{PORT}/projects/")
    if display_host != BIND_ADDRESS:
        print(f"Listening On:       http://{BIND_ADDRESS}:{PORT} (all interfaces)")
    if _jwks_cache:
        print(f"Auth:               Entra ID (tenant={ENTRA_TENANT_ID}, client={ENTRA_CLIENT_ID})")
    elif os.environ.get(API_KEY_ENV, "").strip():
        print("Auth:               Master API key + issued HMAC tokens (usage-counted)")
        print(f"Token Admin:        POST http://{display_host}:{PORT}/api/admin/issue-token")
        print(f"Token Usage:        GET  http://{display_host}:{PORT}/api/admin/tokens")
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
