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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    from local_brd_runner import process_brd_document
except ModuleNotFoundError:
    from scripts.local_brd_runner import process_brd_document

try:
    import blob_sync
except ModuleNotFoundError:
    try:
        from scripts import blob_sync  # type: ignore[no-redef]
    except ModuleNotFoundError:
        class _BlobSyncStub:
            BLOB_ENABLED = False
            def sync_down(self, *a, **k): return {}
            def upload_project(self, *a, **k): return None
            def upload_feed(self, *a, **k): return None
            def upload_owners(self, *a, **k): return None
        blob_sync = _BlobSyncStub()  # type: ignore[assignment]


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
SERVICE_START_EPOCH = time.time()
# Optional: set this to a Teams Incoming Webhook URL to receive a notification
# whenever a user submits a token request.
TEAMS_WEBHOOK_URL = os.environ.get("FACTORY_PORTAL_TEAMS_WEBHOOK_URL", "")

# Optional per-deployment project visibility allowlist. Comma-separated slugs.
# When set, the portal only exposes (feed + file routes) the listed projects.
# When unset or empty, all projects under projects/ are visible (local default).
# Use this on the hosted/external portal to limit which projects are public.
_visible_raw = os.environ.get("FACTORY_PORTAL_VISIBLE_SLUGS", "").strip()
VISIBLE_SLUGS: frozenset[str] | None = (
    frozenset(s.strip() for s in _visible_raw.split(",") if s.strip())
    if _visible_raw
    else None
)


def _is_slug_visible(slug: str) -> bool:
    """Return True if the slug is allowed by the visibility allowlist.

    When no allowlist is configured (VISIBLE_SLUGS is None), everything is
    visible (local dev default). When configured, only listed slugs pass.
    """
    if VISIBLE_SLUGS is None:
        return True
    return bool(slug) and slug in VISIBLE_SLUGS


# ── Per-user ownership (Entra ID via Container Apps Easy Auth) ───────────────
#
# When FACTORY_PORTAL_AUTH_MODE=entra, the portal reads the Easy Auth headers
# (X-MS-CLIENT-PRINCIPAL-NAME = the user's UPN) and filters every project the
# user can see based on the owner sidecar file: .portal-owners.json at repo
# root. Shape:
#   {
#     "admins": ["admin@contoso.com"],
#     "projects": {
#       "slug-a": ["alice@contoso.com"],
#       "slug-b": ["bob@contoso.com", "carol@contoso.com"]
#     }
#   }
# Additional admins can be provided via FACTORY_PORTAL_ADMINS (comma list).
# Admins always see every project. When AUTH_MODE is not 'entra', all users
# see everything (local dev default — the allowlist above still applies if set).

AUTH_MODE = os.environ.get("FACTORY_PORTAL_AUTH_MODE", "").strip().lower()
# Owners data source — in order of precedence:
#   1. FACTORY_PORTAL_OWNERS_JSON : inline JSON (e.g. mounted via Container App
#      secret env var). Read-only; auto-stamping submitters is skipped.
#   2. FACTORY_PORTAL_OWNERS_FILE : path override (e.g. Azure Files mount).
#   3. <repo root>/.portal-owners.json : default for local dev and image seed.
_OWNERS_JSON_ENV = os.environ.get("FACTORY_PORTAL_OWNERS_JSON", "").strip()
OWNERS_FILE = pathlib.Path(
    os.environ.get("FACTORY_PORTAL_OWNERS_FILE")
    or (FACTORY_REPO_ROOT / ".portal-owners.json")
)
_env_admins = os.environ.get("FACTORY_PORTAL_ADMINS", "")
_ENV_ADMINS: frozenset[str] = frozenset(
    a.strip().lower() for a in _env_admins.split(",") if a.strip()
)

# Optional tenant allowlist. When set, only users whose Entra token 'tid' claim
# (home tenant) is in this list may access the portal — used with a
# multi-tenant app registration to accept e.g. any Microsoft employee while
# still rejecting guests from other tenants.
# Default: empty → no tenant restriction (single-tenant deployments rely on
# Easy Auth's own issuer check to enforce the tenant).
_allowed_tenants_raw = os.environ.get("FACTORY_PORTAL_ALLOWED_TENANTS", "").strip()
ALLOWED_TENANTS: frozenset[str] | None = (
    frozenset(t.strip().lower() for t in _allowed_tenants_raw.split(",") if t.strip())
    if _allowed_tenants_raw
    else None
)


def _load_owners() -> dict:
    """Load owners data; return an empty structure on any error.

    Sources in order: FACTORY_PORTAL_OWNERS_JSON env var (inline JSON, or
    base64-encoded JSON — auto-detected), then OWNERS_FILE on disk.
    """
    if _OWNERS_JSON_ENV:
        raw_text = _OWNERS_JSON_ENV
        # If the value doesn't look like JSON, try base64-decoding it.
        if not raw_text.lstrip().startswith("{"):
            try:
                raw_text = base64.b64decode(raw_text, validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                logger.warning("FACTORY_PORTAL_OWNERS_JSON b64 decode failed: %s", exc)
                raw_text = _OWNERS_JSON_ENV
        try:
            raw = json.loads(raw_text)
            if isinstance(raw, dict):
                return raw
        except json.JSONDecodeError as exc:
            logger.warning("FACTORY_PORTAL_OWNERS_JSON is not valid JSON: %s", exc)
    try:
        if OWNERS_FILE.is_file():
            raw = json.loads(OWNERS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", OWNERS_FILE.name, exc)
    return {"admins": [], "projects": {}}


def _save_owners(data: dict) -> None:
    if _OWNERS_JSON_ENV:
        # Secret-backed mode is read-only from the container; auto-stamping
        # submitters is a no-op. Admins must update the secret out-of-band.
        logger.info(
            "Skipping owners write: FACTORY_PORTAL_OWNERS_JSON is set (read-only mode)"
        )
        return
    try:
        OWNERS_FILE.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Failed to write %s: %s", OWNERS_FILE.name, exc)


def _is_admin(user: str | None) -> bool:
    if not user:
        return False
    u = user.strip().lower()
    if u in _ENV_ADMINS:
        return True
    owners = _load_owners()
    for a in owners.get("admins") or []:
        if isinstance(a, str) and a.strip().lower() == u:
            return True
    return False


def _project_owners(slug: str) -> set[str]:
    owners = _load_owners().get("projects") or {}
    raw = owners.get(slug) or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(x).strip().lower() for x in raw if str(x).strip()}


def _user_can_see_project(slug: str, user: str | None) -> bool:
    """Apply both the VISIBLE_SLUGS allowlist and per-user ownership rules."""
    if not _is_slug_visible(slug):
        return False
    if AUTH_MODE != "entra":
        return True  # local dev / unauthenticated hosted = no per-user filter
    if _is_admin(user):
        return True
    if not user:
        return False
    return user.strip().lower() in _project_owners(slug)


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

# ── Run persistence (crash-safe) ──────────────────────────────────────────────
# Runs are snapshotted to disk after every status transition so a container
# restart does not orphan in-flight or recently-finished work. The file is
# ignored by git (see .gitignore). Active runs (queued/running) are marked
# "interrupted" on startup so the UI can surface them instead of pretending
# they are still executing.
_RUNS_STATE_PATH = pathlib.Path(os.environ.get(
    "AAFACTORY_RUNS_STATE",
    str(pathlib.Path(__file__).resolve().parent.parent / "logs" / "portal-runs.state.json"),
))
_RUNS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _persist_runs_unlocked() -> None:
    """Write RUNS to disk atomically. Caller must hold RUNS_LOCK."""
    try:
        tmp = _RUNS_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(RUNS, default=str), encoding="utf-8")
        tmp.replace(_RUNS_STATE_PATH)
    except Exception:  # noqa: BLE001
        # Persistence is best-effort — never break a live request because
        # the disk is full or the path is unwritable.
        pass


def persist_runs() -> None:
    """Acquire the lock and snapshot RUNS to disk."""
    with RUNS_LOCK:
        _persist_runs_unlocked()


def _restore_runs_on_startup() -> None:
    """Load RUNS from disk at boot. Mark any queued/running entries as interrupted."""
    if not _RUNS_STATE_PATH.exists():
        return
    try:
        data = json.loads(_RUNS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    if not isinstance(data, dict):
        return
    now = datetime.utcnow().isoformat() + "Z"
    with RUNS_LOCK:
        for run_id, run in data.items():
            if not isinstance(run, dict):
                continue
            if run.get("status") in {"queued", "running"}:
                run["status"] = "interrupted"
                run["finishedAt"] = now
                run["stderr"] = (run.get("stderr") or "") + "\n[portal restart] run interrupted by container restart"
            RUNS[run_id] = run
        _persist_runs_unlocked()


# ── Bounded pipeline worker pool ──────────────────────────────────────────────
# Every BRD submission used to spawn a raw daemon thread, which meant 50
# concurrent submissions spawned 50 threads competing for CPU. A bounded pool
# queues extra submissions instead of saturating the container.
_PIPELINE_MAX_WORKERS = int(os.environ.get("AAFACTORY_PIPELINE_MAX_WORKERS", "4"))
_PIPELINE_POOL = ThreadPoolExecutor(
    max_workers=_PIPELINE_MAX_WORKERS,
    thread_name_prefix="aaf-pipeline",
)

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


_VALID_NETWORK_TIERS = frozenset({"public", "vnet-integrated", "private"})


def _sanitize_network_tier(value) -> str:
    """Return a validated network tier string, defaulting to 'public'."""
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _VALID_NETWORK_TIERS else "public"


class FactoryPortalHandler(SimpleHTTPRequestHandler):
    """HTTP handler for factory portal with BRD intake API"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FACTORY_REPO_ROOT), **kwargs)

    def _current_user(self) -> str | None:
        """Return the authenticated user's UPN from Easy Auth headers, or None.

        Container Apps Easy Auth forwards two headers on every authenticated
        request:
          X-MS-CLIENT-PRINCIPAL-NAME → identity "name" (sometimes display name,
                                       sometimes UPN — depends on the token)
          X-MS-CLIENT-PRINCIPAL      → base64-encoded JSON principal with full
                                       claim list.
        Because X-MS-CLIENT-PRINCIPAL-NAME can be a display name like
        "MOD Administrator" rather than an email, we prefer the
        preferred_username / upn / email claim from the decoded principal,
        and only fall back to the header if those are absent.
        """
        principal = self._decoded_principal()
        if principal:
            preferred_claim_types = {
                "preferred_username",
                "upn",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
                "email",
                "emails",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            }
            for claim in principal.get("claims") or []:
                typ = (claim.get("typ") or claim.get("type") or "").lower()
                if typ in preferred_claim_types:
                    val = claim.get("val") or claim.get("value")
                    if val and "@" in str(val):
                        return str(val).strip()
            # Some principals expose the UPN at top-level.
            for key in ("userPrincipalName", "userDetails"):
                val = principal.get(key)
                if val and "@" in str(val):
                    return str(val).strip()
        upn = self.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        if upn and "@" in upn:
            return upn.strip()
        return None

    def _decoded_principal(self) -> dict | None:
        """Decode X-MS-CLIENT-PRINCIPAL once per request; cache on the handler."""
        cached = getattr(self, "_cached_principal", False)
        if cached is not False:
            return cached  # may be None
        raw = self.headers.get("X-MS-CLIENT-PRINCIPAL")
        principal: dict | None = None
        if raw:
            try:
                padded = raw + "=" * (-len(raw) % 4)
                decoded = json.loads(base64.b64decode(padded).decode("utf-8"))
                if isinstance(decoded, dict):
                    principal = decoded
            except Exception:
                principal = None
        self._cached_principal = principal
        return principal

    def _current_tenant(self) -> str | None:
        """Return the user's home tenant id (the 'tid' claim) from Easy Auth.

        Easy Auth forwards a base64-encoded JSON principal in
        X-MS-CLIENT-PRINCIPAL. We decode it and pluck the 'tid' claim so we
        can enforce a per-deployment tenant allowlist independently of the
        app registration's sign-in audience.
        """
        principal = self._decoded_principal()
        if not principal:
            return None
        for claim in principal.get("claims") or []:
            typ = (claim.get("typ") or claim.get("type") or "").lower()
            if typ in {"tid", "http://schemas.microsoft.com/identity/claims/tenantid"}:
                val = claim.get("val") or claim.get("value")
                if val:
                    return str(val).strip().lower()
        return None

    def _tenant_allowed(self) -> bool:
        """True when no tenant allowlist is configured, or the request's tenant is in it."""
        if ALLOWED_TENANTS is None:
            return True
        tid = self._current_tenant()
        return bool(tid) and tid in ALLOWED_TENANTS

    def _authorized_user(self) -> str | None:
        """Return the current user only when tenant policy allows them.

        Users from disallowed tenants are treated as anonymous — they cannot
        see any project. This is enforced above Easy Auth, so even if a guest
        account from another tenant successfully signs in, they still get
        zero access.
        """
        if not self._tenant_allowed():
            return None
        return self._current_user()

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

        if request_path == "/health":
            return self._handle_health()

        if request_path == "/api/me":
            user = self._current_user()
            tenant = self._current_tenant()
            return self._send_json({
                "authMode": AUTH_MODE or "none",
                "authenticated": bool(user),
                "user": user,
                "tenantId": tenant,
                "tenantAllowed": self._tenant_allowed(),
                "isAdmin": _is_admin(user) and self._tenant_allowed(),
            }, 200)

        # Hard-deny requests whose token 'tid' is not in the tenant allowlist.
        # /api/me, /health, and the login/logout endpoints are exempt so the
        # user can see a friendly message and sign out. Static browser assets
        # (css/js/images) stay accessible to avoid breaking the error page.
        if (AUTH_MODE == "entra"
                and ALLOWED_TENANTS is not None
                and not self._tenant_allowed()
                and not request_path.startswith(("/.auth/", "/api/me", "/health",
                                                  "/assets/", "/favicon"))
                and request_path != "/factory-portal.html"):
            if request_path.startswith("/api/") or request_path.endswith(".json"):
                return self._send_json({"error": "Tenant not authorized for this portal."}, 403)
            self.send_response(403)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<!doctype html><meta charset='utf-8'><title>Access denied</title>"
                b"<body style='font-family:Segoe UI,sans-serif;padding:3rem;max-width:640px'>"
                b"<h1>Access denied</h1>"
                b"<p>This portal is restricted to specific Microsoft Entra tenants. "
                b"Your account is authenticated, but your home tenant is not in the "
                b"allowlist for this deployment.</p>"
                b"<p><a href='/.auth/logout'>Sign out</a> and try a different account.</p>"
                b"</body>")
            return

        if request_path == "/ready":
            return self._handle_ready()

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

        # Block direct browsing of the scripts directory (internal tooling only)
        if request_path.startswith("/scripts/") or request_path == "/scripts":
            self.send_error(403, "Forbidden")
            return

        # Enforce per-deployment project visibility for direct /projects/<slug>/...
        # file access. When an allowlist is configured, hidden slugs return 404.
        if request_path.startswith("/projects/"):
            parts = request_path.split("/", 3)  # ['', 'projects', '<slug>', 'rest...']
            if len(parts) >= 3 and parts[2]:
                if not _user_can_see_project(parts[2], self._authorized_user()):
                    self.send_error(404, "Not Found")
                    return

        if request_path == "/api/admin/tokens":
            if not self._require_admin_key():
                return
            return self._handle_token_list()

        if request_path == "/api/admin/token-requests":
            if not self._require_admin_key():
                return
            return self._handle_token_request_list()

        if request_path == "/api/admin/project-owners":
            if not self._require_admin_key():
                return
            return self._handle_project_owners_list(parsed.query)

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
        if path == "/api/admin/project-owners":
            if not self._require_admin_key():
                return
            return self._handle_project_owners_update()
        if path == "/api/token-request":
            return self._handle_submit_token_request()
        if path == "/api/csa-copilot/ask":
            if not self._require_auth_for_mutation():
                return
            return self._handle_csa_copilot_ask()
        if path == "/api/guide/refresh":
            if not self._require_auth_for_mutation():
                return
            return self._handle_guide_refresh()

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

    def _handle_project_owners_list(self, query: str):
        """GET /api/admin/project-owners[?slug=...] — list owners.

        Returns {"admins": [...], "projects": {slug: [users]}} when slug is
        omitted, or {"slug": ..., "owners": [users]} when a slug is provided.
        """
        params = parse_qs(query or "")
        slug = (params.get("slug", [""])[0] or "").strip()
        owners = _load_owners()
        if slug:
            if not _is_slug_visible(slug):
                self._send_json({"error": "Unknown project"}, 404)
                return
            project_owners = sorted(_project_owners(slug))
            self._send_json({"slug": slug, "owners": project_owners})
            return
        projects = owners.get("projects") or {}
        normalized = {
            s: sorted({str(x).strip().lower() for x in (v if isinstance(v, list) else [v]) if str(x).strip()})
            for s, v in projects.items()
        }
        self._send_json({
            "admins": sorted({str(a).strip().lower() for a in (owners.get("admins") or []) if str(a).strip()}),
            "projects": normalized,
            "readOnly": bool(_OWNERS_JSON_ENV),
        })

    def _handle_project_owners_update(self):
        """POST /api/admin/project-owners — add/remove/set users for a project.

        Body: {"slug": "...", "users": ["a@b.com", ...], "action": "add"|"remove"|"set"}
        Default action is "add". Emails are case-insensitive and de-duplicated.
        """
        if _OWNERS_JSON_ENV:
            self._send_json({
                "error": "Owners are read-only: FACTORY_PORTAL_OWNERS_JSON is set. "
                         "Update the secret and restart the portal."
            }, 409)
            return

        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception as exc:
            self._send_json({"error": f"Invalid request: {exc}"}, 400)
            return

        slug = str(payload.get("slug", "")).strip()
        action = str(payload.get("action", "add")).strip().lower() or "add"
        raw_users = payload.get("users")
        if raw_users is None and "user" in payload:
            raw_users = [payload.get("user")]
        if isinstance(raw_users, str):
            raw_users = [raw_users]
        if not isinstance(raw_users, list):
            raw_users = []
        users = []
        for u in raw_users:
            if not isinstance(u, str):
                continue
            u_norm = u.strip().lower()
            if u_norm and u_norm not in users:
                users.append(u_norm)

        if not slug:
            self._send_json({"error": "slug is required"}, 400)
            return
        if action not in {"add", "remove", "set"}:
            self._send_json({"error": "action must be add, remove, or set"}, 400)
            return
        if action in {"add", "remove"} and not users:
            self._send_json({"error": "users list cannot be empty for add/remove"}, 400)
            return
        if not _is_slug_visible(slug):
            self._send_json({"error": "Unknown project slug"}, 404)
            return

        data = _load_owners()
        if not isinstance(data.get("projects"), dict):
            data["projects"] = {}
        current_raw = data["projects"].get(slug) or []
        if isinstance(current_raw, str):
            current_raw = [current_raw]
        current = []
        for u in current_raw:
            if not isinstance(u, str):
                continue
            u_norm = u.strip().lower()
            if u_norm and u_norm not in current:
                current.append(u_norm)

        if action == "add":
            for u in users:
                if u not in current:
                    current.append(u)
        elif action == "remove":
            current = [u for u in current if u not in set(users)]
        else:  # set
            current = list(users)

        data["projects"][slug] = sorted(current)
        _save_owners(data)

        # Mirror to blob so other replicas / restarts pick it up.
        try:
            blob_sync.upload_owners(OWNERS_FILE)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Owners blob upload failed: %s", exc)

        self._send_json({
            "slug": slug,
            "action": action,
            "owners": sorted(current),
        }, 200)

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
            "enableObservability": _coerce_bool(payload.get("enableObservability"), default=True),
            "networkTier": _sanitize_network_tier(payload.get("networkTier", "public")),
        }

        if not file_name or not content:
            self._send_json({"error": "Missing fileName or content"}, 400)
            return

        return self._save_and_start_run(
            file_name, content, generation_options, owner=self._authorized_user()
        )

    def _save_and_start_run(self, file_name: str, content: str, generation_options: dict | None = None, owner: str | None = None):
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
                "owner": owner,
            }

        # Snapshot queued state and dispatch to bounded pipeline pool
        persist_runs()
        _PIPELINE_POOL.submit(
            self._run_pipeline,
            run_id,
            str(brd_path),
            generation_options or {},
            owner,
        )

        self._send_json(
            {
                "id": run_id,
                "status": "queued",
                "message": "BRD received and pipeline started.",
                "brdFile": f"docs/intake/{file_name}",
            },
            202,
        )

    def _run_pipeline(self, run_id, brd_path, generation_options=None, owner: str | None = None):
        """Execute the pipeline in background"""
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "running"
            RUNS[run_id]["startedAt"] = datetime.utcnow().isoformat() + "Z"
            _persist_runs_unlocked()

        try:
            output = process_brd_document(
                FACTORY_REPO_ROOT,
                pathlib.Path(brd_path),
                run_id,
                generation_options or {},
            )

            # Stamp the submitter as owner of the generated project so per-user
            # filtering (Entra auth mode) gives them access. Best-effort only.
            if owner and isinstance(output, dict):
                slug = output.get("slug") or output.get("projectSlug")
                if slug:
                    try:
                        data = _load_owners()
                        projects = data.setdefault("projects", {})
                        existing = projects.get(slug) or []
                        if isinstance(existing, str):
                            existing = [existing]
                        lowered = {e.strip().lower() for e in existing if isinstance(e, str)}
                        if owner.strip().lower() not in lowered:
                            existing.append(owner)
                            projects[slug] = existing
                            _save_owners(data)
                            logger.info("Recorded owner %s for project %s", owner, slug)
                    except Exception as exc:  # noqa: BLE001 - best-effort
                        logger.warning("Failed to persist owner for %s: %s", slug, exc)

            # Persist the new project artifacts + updated feed + owners to
            # blob storage so they survive container restarts. No-op when
            # FACTORY_PORTAL_BLOB_ACCOUNT is unset (local dev).
            if blob_sync.BLOB_ENABLED and isinstance(output, dict):
                slug = output.get("slug") or output.get("projectSlug")
                try:
                    if slug:
                        project_dir = FACTORY_REPO_ROOT / "projects" / slug
                        blob_sync.upload_project(project_dir, slug)
                    blob_sync.upload_feed(
                        FACTORY_REPO_ROOT / "factory-projects.generated.json"
                    )
                    if OWNERS_FILE.is_file():
                        blob_sync.upload_owners(OWNERS_FILE)
                except Exception as exc:  # noqa: BLE001 - best-effort
                    logger.warning("Blob upload after run %s failed: %s", run_id, exc)

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
                _persist_runs_unlocked()

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
                _persist_runs_unlocked()

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
        network_tier_field = (fields.get("network_tier") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
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
            "enableObservability": _coerce_bool(enable_observability_field, default=True),
            "networkTier": _sanitize_network_tier(network_tier_field),
        }

        return self._save_and_start_run(
            file_name, content, generation_options, owner=self._authorized_user()
        )

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
        """Serve the generated project feed.

        Merges two sources so the feed is always live:
        1. factory-projects.generated.json — baked-in snapshot or persisted feed
        2. Live scan of the projects/ directory — picks up any project whose
           project-manifest.json exists but isn't yet recorded in the JSON file.

        This means newly generated projects appear immediately without requiring
        a container rebuild or volume mount on remote deployments.
        """
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"

        # Load the persisted feed (may be the baked-in image snapshot or empty).
        baked_projects: list[dict] = []
        generated_at: str | None = None
        if feed_path.exists() and feed_path.is_file():
            try:
                persisted = json.loads(feed_path.read_text(encoding="utf-8"))
                baked_projects = persisted.get("projects") or []
                generated_at = persisted.get("generatedAt")
            except json.JSONDecodeError as exc:
                logger.warning("Failed to read project feed: %s", exc)

        # Build a slug→record index from the baked feed.
        index: dict[str, dict] = {p["slug"]: p for p in baked_projects if p.get("slug")}

        # Live scan: visit every subdirectory of projects/ that has a manifest.
        projects_dir = FACTORY_REPO_ROOT / "projects"
        if projects_dir.is_dir():
            for manifest_path in sorted(projects_dir.glob("*/project-manifest.json")):
                slug = manifest_path.parent.name
                if slug in index:
                    continue  # already present from persisted feed
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                # Reconstruct a minimal project record from the manifest.
                index[slug] = {
                    "slug": slug,
                    "title": manifest.get("title", slug),
                    "status": manifest.get("status", "Ready"),
                    "generatedFrom": manifest.get("source_brd", ""),
                    "generatedAt": manifest.get("created_at", ""),
                    "options": manifest.get("generation_options", {}),
                    "links": {},
                }

        # Sort newest-first by generatedAt.
        merged = sorted(
            index.values(),
            key=lambda p: p.get("generatedAt") or "",
            reverse=True,
        )

        # Apply per-deployment visibility allowlist (hides hidden projects on
        # the hosted/external portal). No-op when unset.
        if VISIBLE_SLUGS is not None:
            merged = [p for p in merged if _is_slug_visible(p.get("slug", ""))]

        # Apply per-user ownership filtering when Entra auth is active.
        if AUTH_MODE == "entra":
            user = self._authorized_user()
            merged = [p for p in merged if _user_can_see_project(p.get("slug", ""), user)]
            # Annotate each record with the current user's role for UI hints.
            for p in merged:
                p["_yours"] = bool(user) and user.strip().lower() in _project_owners(p.get("slug", ""))

        payload = {
            "generatedAt": generated_at,
            "projects": merged,
        }
        return self._send_json(payload, 200)

    def _resolve_project_root(self, slug: str) -> pathlib.Path | None:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", slug or ""):
            return None
        if not _user_can_see_project(slug, self._authorized_user()):
            return None
        project_root = (FACTORY_REPO_ROOT / "projects" / slug).resolve()
        projects_root = (FACTORY_REPO_ROOT / "projects").resolve()
        if projects_root not in project_root.parents:
            return None
        if not project_root.exists() or not project_root.is_dir():
            return None
        return project_root

    def _handle_guide_refresh(self):
        """Regenerate docs/guide-report.md for a project and patch the feed."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception as exc:
            return self._send_json({"error": f"Invalid request: {exc}"}, 400)

        slug = str(payload.get("slug", "")).strip()
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        try:
            from generate_guide_report import generate_guide_report  # type: ignore
        except ModuleNotFoundError:
            from scripts.generate_guide_report import generate_guide_report  # type: ignore

        try:
            info = generate_guide_report(project_root)
        except Exception as exc:  # pragma: no cover - defensive
            return self._send_json({"error": f"Guide generation failed: {exc}"}, 500)

        # Convert report path to a repo-relative forward-slash URL for the portal.
        try:
            rel_path = str(
                pathlib.Path(info["report_path"]).resolve().relative_to(FACTORY_REPO_ROOT)
            ).replace("\\", "/")
        except ValueError:
            rel_path = info["report_path"]

        guide_block = {
            "path": rel_path,
            "generated_at": info.get("generated_at"),
            "severity_counts": info.get("severity_counts", {}),
        }

        # Patch project-manifest.json.
        manifest_path = project_root / "project-manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = {}
            manifest["guide_report"] = guide_block
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

        # Patch factory-projects.generated.json if the project has a feed entry.
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"
        if feed_path.is_file():
            try:
                feed = json.loads(feed_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                feed = {}
            changed = False
            for record in feed.get("projects") or []:
                if isinstance(record, dict) and record.get("slug") == slug:
                    record["guideReport"] = guide_block
                    record.setdefault("links", {})["guideReport"] = rel_path
                    changed = True
                    break
            if changed:
                feed_path.write_text(
                    json.dumps(feed, indent=2) + "\n", encoding="utf-8"
                )

        return self._send_json({"status": "ok", "slug": slug, "guideReport": guide_block}, 200)

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
        network_tier = _sanitize_network_tier((project.get("options") or {}).get("networkTier", "public"))
        network_tier_label = {
            "public": "Public (internet-facing)",
            "vnet-integrated": "VNet-integrated (NSG + subnet delegation)",
            "private": "Private (internal LB + private endpoints)",
        }.get(network_tier, network_tier)
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
            "networkTier": network_tier,
            "networkTierLabel": network_tier_label,
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

    def _handle_health(self):
        """Lightweight liveness probe with no external dependency checks."""
        uptime_seconds = int(max(0, time.time() - SERVICE_START_EPOCH))
        return self._send_json(
            {
                "status": "ok",
                "service": "azure-architecture-factory-portal",
                "probe": "liveness",
                "timeUtc": datetime.utcnow().isoformat() + "Z",
                "uptimeSeconds": uptime_seconds,
            },
            200,
        )

    def _handle_ready(self):
        """Readiness probe that verifies local portal assets are available."""
        portal_file = FACTORY_REPO_ROOT / "factory-portal.html"
        projects_dir = FACTORY_REPO_ROOT / "projects"
        checks = {
            "portalHtml": portal_file.is_file(),
            "projectsDir": projects_dir.is_dir(),
        }
        ready = all(checks.values())
        status = 200 if ready else 503
        return self._send_json(
            {
                "status": "ready" if ready else "not_ready",
                "service": "azure-architecture-factory-portal",
                "probe": "readiness",
                "timeUtc": datetime.utcnow().isoformat() + "Z",
                "checks": checks,
            },
            status,
        )

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
    # Pull persisted state (projects, feed, owners) from blob storage before
    # serving any traffic. No-op when FACTORY_PORTAL_BLOB_ACCOUNT is unset.
    if blob_sync.BLOB_ENABLED:
        try:
            summary = blob_sync.sync_down(FACTORY_REPO_ROOT)
            logger.info("Blob sync-down summary: %s", summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Blob sync-down failed: %s", exc)

    # ThreadingHTTPServer handles concurrent HTTP requests instead of serializing
    # them. Previously a single slow request blocked every other client on the
    # TCP accept loop; this is particularly visible under burst load or when
    # several users poll status at once.
    _restore_runs_on_startup()
    httpd = ThreadingHTTPServer((BIND_ADDRESS, PORT), FactoryPortalHandler)
    httpd.daemon_threads = True
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
