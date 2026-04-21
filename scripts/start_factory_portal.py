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
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler

UTC = timezone.utc


def _utcnow_iso() -> str:
    """Timezone-aware UTC ISO 8601 string (Python 3.13-compatible).

    Preserves the legacy `datetime.utcnow().isoformat() + 'Z'` output format.
    """
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    from telemetry import init_otel, get_tracer
except ModuleNotFoundError:
    # Telemetry module is optional; provide no-op shims so the portal runs
    # with stdlib only when scripts/ isn't on sys.path yet.
    def init_otel(*_args, **_kwargs):
        return False

    def get_tracer(_name="aaf-portal"):
        class _Noop:
            def start_as_current_span(self, *a, **kw):
                class _S:
                    def __enter__(self_inner):
                        return self_inner

                    def __exit__(self_inner, *a):
                        return False

                    def set_attribute(self_inner, *a, **kw):
                        pass

                    def set_status(self_inner, *a, **kw):
                        pass

                    def record_exception(self_inner, *a, **kw):
                        pass

                return _S()

        return _Noop()

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

try:
    import copilot_runner
except ModuleNotFoundError:
    try:
        from scripts import copilot_runner  # type: ignore[no-redef]
    except ModuleNotFoundError:
        copilot_runner = None  # type: ignore[assignment]


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
# BRD schema bounds (applied after size check)
MIN_BRD_CONTENT_CHARS = int(os.environ.get("AAFACTORY_MIN_BRD_CHARS", "50"))
MAX_BRD_CONTENT_CHARS = int(os.environ.get("AAFACTORY_MAX_BRD_CHARS", "800000"))
MAX_BRD_FILENAME_LEN = 120
# Intake rate limit (sliding window per caller key — UPN if authenticated, else IP)
INTAKE_RATE_PER_MIN = int(os.environ.get("AAFACTORY_INTAKE_RATE_PER_MIN", "6"))
INTAKE_RATE_WINDOW_SECONDS = 60
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


class _SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter.

    Thread-safe. Keeps a deque of recent hit timestamps per caller key and
    rejects once the window count exceeds `limit`. Memory is bounded by the
    number of active callers over any given window.
    """

    def __init__(self, limit: int, window_seconds: int):
        self._limit = max(1, int(limit))
        self._window = max(1, int(window_seconds))
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds).

        retry_after_seconds is 0 when allowed; otherwise the number of seconds
        the caller should wait before the next slot frees up.
        """
        if not key:
            return True, 0
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                bucket = deque()
                self._hits[key] = bucket
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._limit:
                retry = max(1, int(self._window - (now - bucket[0])))
                return False, retry
            bucket.append(now)
            return True, 0


_INTAKE_LIMITER = _SlidingWindowRateLimiter(
    limit=INTAKE_RATE_PER_MIN,
    window_seconds=INTAKE_RATE_WINDOW_SECONDS,
)


# ---------------------------------------------------------------------------
# Readiness-probe helpers
# ---------------------------------------------------------------------------
READINESS_BLOB_CACHE_TTL_SECONDS = 30
_READINESS_BLOB_CACHE: dict = {"expiresAt": 0.0, "value": None}
_READINESS_BLOB_CACHE_LOCK = threading.Lock()


def _probe_intake_writable(intake_dir: pathlib.Path) -> bool:
    """Return True if intake_dir can be created, written to, and cleaned up."""
    try:
        intake_dir.mkdir(parents=True, exist_ok=True)
        probe = intake_dir / f".readiness-probe-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _otel_enabled() -> bool:
    """Return True if the OpenTelemetry exporter was successfully initialized."""
    try:
        import telemetry  # local module
        return bool(getattr(telemetry, "telemetry_enabled", False))
    except Exception:
        return False


def _probe_blob_storage_cached() -> dict:
    """HEAD the configured blob container. Result cached for 30s to keep the
    readiness probe cheap and avoid hammering storage on every Kubernetes tick.
    """
    now = time.monotonic()
    with _READINESS_BLOB_CACHE_LOCK:
        cached = _READINESS_BLOB_CACHE.get("value")
        if cached is not None and _READINESS_BLOB_CACHE["expiresAt"] > now:
            return cached

    result: dict = {"ok": False, "checkedAt": _utcnow_iso()}
    try:
        import urllib.request
        account = os.environ.get("FACTORY_PORTAL_BLOB_ACCOUNT", "").strip()
        container = os.environ.get("FACTORY_PORTAL_BLOB_CONTAINER", "portal-state").strip() or "portal-state"
        if not account:
            result["error"] = "no account configured"
        else:
            # Unauthenticated HEAD — we only care that the endpoint reachable.
            # A 401/403 still proves storage DNS + TLS + TCP are healthy.
            url = f"https://{account}.blob.core.windows.net/{container}?restype=container"
            req = urllib.request.Request(url, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    result["ok"] = True
                    result["statusCode"] = resp.status
            except urllib.error.HTTPError as http_exc:
                # 401/403 = reachable but we're not authorized (expected).
                if http_exc.code in (401, 403, 404):
                    result["ok"] = True
                    result["statusCode"] = http_exc.code
                else:
                    result["statusCode"] = http_exc.code
                    result["error"] = f"HTTP {http_exc.code}"
    except Exception as exc:  # noqa: BLE001 - probe must never crash caller
        result["error"] = f"{type(exc).__name__}: {exc}"

    with _READINESS_BLOB_CACHE_LOCK:
        _READINESS_BLOB_CACHE["value"] = result
        _READINESS_BLOB_CACHE["expiresAt"] = now + READINESS_BLOB_CACHE_TTL_SECONDS
    return result


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

# When the portal runs behind Azure Container Apps / App Service EasyAuth,
# the ingress strips any caller-supplied X-MS-CLIENT-PRINCIPAL* headers and
# replaces them with values from the validated session. Setting this env var
# tells the portal it is safe to trust those headers as proof of an
# authenticated Entra user (browser UI flow — no Bearer token required).
# NEVER enable this when the portal is exposed without EasyAuth in front.
TRUST_EASYAUTH_HEADERS = os.environ.get("TRUST_EASYAUTH_HEADERS", "").strip().lower() in ("1", "true", "yes")

# Optional per-endpoint allowlist for BRD intake mutations. Comma-separated
# list of principals (UPN/email or object id). Matches against the
# `preferred_username` and `oid` claims on the authenticated caller.
# When empty, any authenticated user may submit BRDs (Entra/EasyAuth still gates sign-in).
def _parse_principal_allowlist(raw: str) -> set[str]:
    return {p.strip().lower() for p in (raw or "").split(",") if p.strip()}

BRD_INTAKE_ALLOWED_PRINCIPALS = _parse_principal_allowlist(
    os.environ.get("BRD_INTAKE_ALLOWED_PRINCIPALS", "")
)

# File-backed overlay for the allowlist so admins can edit it from the portal
# without redeploying. The file is merged with BRD_INTAKE_ALLOWED_PRINCIPALS;
# removing an env-baked entry requires changing the env var (env is the seed).
BRD_ALLOWLIST_FILE = pathlib.Path(
    os.environ.get("BRD_INTAKE_ALLOWLIST_FILE")
    or (FACTORY_REPO_ROOT / ".brd-allowlist.json")
)


def _load_brd_allowlist_file() -> set[str]:
    try:
        if BRD_ALLOWLIST_FILE.is_file():
            raw = json.loads(BRD_ALLOWLIST_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return {str(x).strip().lower() for x in raw if str(x).strip()}
            if isinstance(raw, dict) and isinstance(raw.get("principals"), list):
                return {str(x).strip().lower() for x in raw["principals"] if str(x).strip()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", BRD_ALLOWLIST_FILE.name, exc)
    return set()


def _save_brd_allowlist_file(principals: set[str]) -> None:
    try:
        BRD_ALLOWLIST_FILE.write_text(
            json.dumps({"principals": sorted(principals)}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to write %s: %s", BRD_ALLOWLIST_FILE.name, exc)


def _current_brd_allowlist() -> set[str]:
    """Effective allowlist = env seed ∪ file overlay."""
    return BRD_INTAKE_ALLOWED_PRINCIPALS | _load_brd_allowlist_file()


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
    now = _utcnow_iso()
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

# ── Stuck-run watchdog ────────────────────────────────────────────────────────
# A pipeline run whose worker thread dies (segfault, OOM, process SIGKILL)
# leaves its RUNS entry in "running" forever because only the happy path
# transitions the status. The watchdog scans periodically and marks any run
# whose startedAt is older than the threshold as "failed" with a clear
# stderr marker, so the UI surfaces it instead of spinning forever.
_PIPELINE_STUCK_MINUTES = int(os.environ.get("AAFACTORY_PIPELINE_STUCK_MINUTES", "30"))
_PIPELINE_WATCHDOG_INTERVAL_SECONDS = int(
    os.environ.get("AAFACTORY_PIPELINE_WATCHDOG_INTERVAL_SECONDS", "60")
)
_PIPELINE_WATCHDOG_STARTED = False
_PIPELINE_WATCHDOG_LOCK = threading.Lock()


def _parse_iso_z(stamp: str) -> datetime | None:
    """Parse our _utcnow_iso() output back into a tz-aware UTC datetime."""
    if not isinstance(stamp, str) or not stamp.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(stamp[:-1]).replace(tzinfo=UTC)
    except Exception:
        return None


def _sweep_stuck_runs(now_utc: datetime | None = None) -> int:
    """Mark runs stuck in queued/running past the threshold as failed.

    Returns the number of runs transitioned. Called by the watchdog thread
    and directly by unit tests.
    """
    now_utc = now_utc or datetime.now(UTC)
    threshold = now_utc - timedelta(minutes=_PIPELINE_STUCK_MINUTES)
    transitioned = 0
    with RUNS_LOCK:
        for run_id, run in RUNS.items():
            if not isinstance(run, dict):
                continue
            if run.get("status") not in {"queued", "running"}:
                continue
            anchor_raw = run.get("startedAt") or run.get("createdAt")
            anchor = _parse_iso_z(anchor_raw) if anchor_raw else None
            if anchor is None or anchor >= threshold:
                continue
            logger.warning(
                "Stuck run detected: %s status=%s anchor=%s minutes=%d",
                run_id, run.get("status"), anchor_raw, _PIPELINE_STUCK_MINUTES,
            )
            run["status"] = "failed"
            run["finishedAt"] = _utcnow_iso()
            run["returnCode"] = -2
            run["stderr"] = (
                (run.get("stderr") or "")
                + f"\n[watchdog] Run exceeded {_PIPELINE_STUCK_MINUTES} minutes "
                  "without completion — marked failed."
            )
            if not isinstance(run.get("result"), dict):
                run["result"] = {}
            run["result"].setdefault(
                "message",
                f"Run exceeded {_PIPELINE_STUCK_MINUTES}-minute watchdog threshold.",
            )
            run["result"].setdefault("status", "failed")
            transitioned += 1
        if transitioned:
            _persist_runs_unlocked()
    return transitioned


def _watchdog_loop() -> None:
    while True:
        try:
            time.sleep(_PIPELINE_WATCHDOG_INTERVAL_SECONDS)
            n = _sweep_stuck_runs()
            if n:
                logger.info("Watchdog transitioned %d stuck run(s) to failed", n)
        except Exception as exc:  # noqa: BLE001 - must never die
            logger.warning("Watchdog iteration failed: %s", exc)


def _start_watchdog() -> None:
    """Start the stuck-run watchdog thread once per process."""
    global _PIPELINE_WATCHDOG_STARTED
    with _PIPELINE_WATCHDOG_LOCK:
        if _PIPELINE_WATCHDOG_STARTED:
            return
        _PIPELINE_WATCHDOG_STARTED = True
    t = threading.Thread(
        target=_watchdog_loop, name="aaf-watchdog", daemon=True
    )
    t.start()
    logger.info(
        "Pipeline watchdog started (interval=%ds, stuck-threshold=%dm)",
        _PIPELINE_WATCHDOG_INTERVAL_SECONDS, _PIPELINE_STUCK_MINUTES,
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
class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Fields: ts (ISO-8601 UTC), level, logger, msg. Any attributes added via
    `logger.info("...", extra={...})` are merged as top-level keys, so calls
    like `logger.info("run started", extra={"run_id": rid, "owner": upn})`
    produce `{"ts": ..., "msg": "run started", "run_id": ..., "owner": ...}`.
    Exceptions are rendered as a single-string `exc` field.
    """

    # Attributes stdlib LogRecord sets itself; anything outside this set is
    # considered an `extra` key contributed by the caller.
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
                .replace(tzinfo=None).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            # Best-effort serialization; fall back to repr.
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    level_name = os.environ.get("AAFACTORY_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Auto-enable JSON in container environments (ACA sets CONTAINER_APP_NAME)
    # unless explicitly overridden.
    json_env = os.environ.get("AAFACTORY_LOG_JSON", "").strip().lower()
    if json_env in ("1", "true", "yes"):
        use_json = True
    elif json_env in ("0", "false", "no"):
        use_json = False
    else:
        use_json = bool(os.environ.get("CONTAINER_APP_NAME", "").strip())

    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
        )
    root = logging.getLogger()
    # Clear prior handlers so repeated calls (tests) don't stack output.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)


_configure_logging()
logger = logging.getLogger(__name__)


# ── Azure OpenAI auth header ────────────────────────────────────────────────
# Supports two auth modes:
#   1. API key  (AZURE_OPENAI_API_KEY env var)
#   2. Entra ID (DefaultAzureCredential) — used when azure-identity is importable
#      AND no API key is set. This is how we reach Cognitive Services accounts
#      that have `disableLocalAuth=true`.
# Returns (header_name, header_value) or None when neither auth method works.

_entra_token_cache: dict = {"token": None, "expires_at": 0.0}
_entra_token_lock = threading.Lock()


def _aoai_auth_header() -> tuple[str, str] | None:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    if api_key:
        return ("api-key", api_key)

    # Fall back to Entra ID via DefaultAzureCredential.
    try:
        from azure.identity import DefaultAzureCredential  # type: ignore
    except ImportError:
        return None

    now = time.time()
    with _entra_token_lock:
        if (_entra_token_cache["token"]
                and _entra_token_cache["expires_at"] - 60 > now):
            return ("Authorization", f"Bearer {_entra_token_cache['token']}")
        try:
            cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
            tok = cred.get_token("https://cognitiveservices.azure.com/.default")
            _entra_token_cache["token"] = tok.token
            _entra_token_cache["expires_at"] = float(tok.expires_on)
            return ("Authorization", f"Bearer {tok.token}")
        except Exception as e:
            logger.warning("Entra token for AOAI failed: %s", e)
            return None


def _aoai_urlopen(req: Request, *, timeout: int = 60) -> bytes:
    """POST to Azure OpenAI with a single retry on transient disconnects.

    AOAI occasionally closes an idle HTTPS keep-alive between requests,
    which surfaces to stdlib urllib as ``RemoteDisconnected`` or
    ``ConnectionResetError``. A single immediate retry fixes it.
    """
    import http.client
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (http.client.RemoteDisconnected,
                http.client.IncompleteRead,
                ConnectionResetError) as e:
            last_exc = e
            logger.warning("AOAI transient disconnect (attempt %d): %s",
                           attempt + 1, e)
            continue
    # Both attempts failed — re-raise the last error.
    raise last_exc  # type: ignore[misc]


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


def _validate_brd_content(raw: object) -> tuple[str | None, str | None]:
    """Validate a BRD content payload.

    Returns ``(content, None)`` on success or ``(None, error_message)`` on
    failure. Enforces: must be a string, UTF-8 decodable (already, since we
    got a str), no NUL or other C0 control bytes (except tab/newline/CR),
    and within the configured min/max length bounds after stripping.
    """
    if not isinstance(raw, str):
        return None, "content must be a string"
    content = raw.strip()
    if not content:
        return None, "content is empty"
    # Reject embedded NUL and other C0 control characters that are neither
    # whitespace nor standard line terminators. These frequently appear in
    # obfuscated payloads and can break downstream tooling.
    for ch in content:
        code = ord(ch)
        if code < 0x20 and ch not in ("\t", "\n", "\r"):
            return None, "content contains disallowed control characters"
    if len(content) < MIN_BRD_CONTENT_CHARS:
        return None, f"BRD content too short (min {MIN_BRD_CONTENT_CHARS} characters)"
    if len(content) > MAX_BRD_CONTENT_CHARS:
        return None, f"BRD content too long (max {MAX_BRD_CONTENT_CHARS} characters)"
    return content, None


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
            # Prefer claims in a deterministic priority order so that for B2B
            # guests we land on the user's original email (preferred_username /
            # email) rather than the mangled `user_domain.com#EXT#@tenant` UPN.
            claim_priority = [
                "preferred_username",
                "email",
                "emails",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "upn",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
            ]
            by_type: dict[str, str] = {}
            for claim in principal.get("claims") or []:
                typ = (claim.get("typ") or claim.get("type") or "").lower()
                val = claim.get("val") or claim.get("value")
                if typ and val and "@" in str(val) and typ not in by_type:
                    by_type[typ] = str(val).strip()
            for typ in claim_priority:
                if typ in by_type:
                    return by_type[typ]
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
        # /api/me, /health, /ready, and the login/logout endpoints are exempt
        # so probes and the user can see a friendly message and sign out.
        # Static browser assets (css/js/images) stay accessible to avoid
        # breaking the error page.
        if (AUTH_MODE == "entra"
                and ALLOWED_TENANTS is not None
                and not self._tenant_allowed()
                and not request_path.startswith(("/.auth/", "/api/me", "/health",
                                                  "/ready",
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

        if request_path == "/api/admin/brd-allowlist":
            if not self._require_brd_admin():
                return
            return self._handle_brd_allowlist_list()

        # Copilot CLI runs — per-project endpoints.
        # GET /api/projects/<slug>/copilot-runtime    -> availability + config
        # GET /api/projects/<slug>/copilot-runs       -> list runs
        # GET /api/projects/<slug>/copilot-runs/<id>  -> single run status
        # GET /api/projects/<slug>/copilot-runs/<id>/log -> tail log
        if request_path.startswith("/api/projects/") and "/copilot" in request_path:
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_get(request_path)

        # Repo-root Copilot CLI endpoints (not scoped to any project).
        # GET /api/copilot-runtime
        # GET /api/copilot-agents
        # GET /api/copilot-runs[/<id>[/log|/diff]]
        if (
            request_path == "/api/copilot-runtime"
            or request_path == "/api/copilot-agents"
            or request_path == "/api/copilot-runs"
            or request_path.startswith("/api/copilot-runs/")
        ):
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_root_get(request_path)

        # Default file serving
        return super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        path = urlparse(self.path).path
        if path == "/api/brd-intake":
            if not self._require_auth_for_mutation():
                return
            if not self._require_brd_intake_principal():
                return
            return self._handle_brd_intake()
        if path == "/api/brd-upload":
            if not self._require_auth_for_mutation():
                return
            if not self._require_brd_intake_principal():
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
        if path == "/api/admin/brd-allowlist":
            if not self._require_brd_admin():
                return
            return self._handle_brd_allowlist_update()
        if path == "/api/token-request":
            return self._handle_submit_token_request()
        if path == "/api/csa-copilot/ask":
            if not self._require_auth_for_mutation():
                return
            return self._handle_csa_copilot_ask()
        if path == "/api/brd-chat":
            if not self._require_auth_for_mutation():
                return
            return self._handle_brd_chat()
        if path.startswith("/api/projects/") and path.endswith("/chat"):
            if not self._require_auth_for_mutation():
                return
            # path = /api/projects/<slug>/chat
            parts = path.split("/")
            if len(parts) == 5 and parts[3]:
                return self._handle_project_chat(parts[3])
            self._send_json({"error": "Invalid project chat path"}, 400)
            return
        if path == "/api/guide/refresh":
            if not self._require_auth_for_mutation():
                return
            return self._handle_guide_refresh()

        # Copilot CLI runs — per-project endpoints.
        # POST /api/projects/<slug>/copilot-runs           -> start run
        # POST /api/projects/<slug>/copilot-runs/<id>/cancel -> cancel
        if path.startswith("/api/projects/") and "/copilot-runs" in path:
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_post(path)

        # Repo-root Copilot CLI endpoints.
        # POST /api/copilot-runs                 -> start run at repo root
        # POST /api/copilot-runs/<id>/cancel     -> cancel
        if path == "/api/copilot-runs" or path.startswith("/api/copilot-runs/"):
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_root_post(path)

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
           (or, if TRUST_EASYAUTH_HEADERS=1, accept EasyAuth's forwarded
           X-MS-CLIENT-PRINCIPAL-* headers from the browser session)
        2. Else if API key env var is set:
           a. X-Factory-Api-Key contains a '.' → treat as issued token (HMAC-signed, expirable, usage-counted)
           b. Otherwise → compare directly as master key
        3. If neither is set → allow (local development mode)
        """
        # --- Entra ID (preferred) ---
        if _jwks_cache is not None:
            # Defense-in-depth: if EasyAuth is in front and has already
            # validated the browser session, it forwards principal headers
            # that a forged caller cannot inject (EasyAuth strips incoming
            # copies before forwarding). Trust them only when explicitly
            # opted in.
            if TRUST_EASYAUTH_HEADERS:
                principal_id = self.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "").strip()
                principal_idp = self.headers.get("X-MS-CLIENT-PRINCIPAL-IDP", "").strip().lower()
                if principal_id and principal_idp in ("aad", "azureactivedirectory"):
                    principal_name = self.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "").strip()
                    self._entra_claims = {
                        "oid": principal_id,
                        "preferred_username": principal_name,
                        "source": "easyauth",
                    }
                    return True

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

    def _require_brd_intake_principal(self) -> bool:
        """Enforce BRD allowlist (env seed + file overlay) against the authenticated caller.

        Must be called AFTER `_require_auth_for_mutation`, so `self._entra_claims`
        is populated. If the effective allowlist is empty, any authenticated user is allowed.
        """
        effective = _current_brd_allowlist()
        if not effective:
            return True  # No allowlist configured

        if self._caller_principals() & effective:
            return True

        self._send_json(
            {"error": "BRD intake is restricted. Contact an admin to be added to the allowlist."},
            403,
        )
        return False

    def _caller_principals(self) -> set[str]:
        """Lowercased identifiers that can match an allowlist entry."""
        claims = getattr(self, "_entra_claims", None) or {}
        values = {
            str(claims.get("preferred_username", "")).strip().lower(),
            str(claims.get("upn", "")).strip().lower(),
            str(claims.get("email", "")).strip().lower(),
            str(claims.get("oid", "")).strip().lower(),
            str(claims.get("sub", "")).strip().lower(),
        }
        values.discard("")
        return values

    def _require_brd_admin(self) -> bool:
        """Allow BRD allowlist management for: master API key, portal admins,
        OR any user already on the BRD allowlist (bootstraps self-service)."""
        # Master key still works
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if expected_key:
            provided = self.headers.get("X-Factory-Api-Key", "")
            if provided and hmac.compare_digest(provided, expected_key):
                return True

        # Require auth if Entra is configured
        if _jwks_cache is not None:
            if not self._require_auth_for_mutation():
                return False
            caller = self._caller_principals()
            # Portal-level admins
            for principal in caller:
                if _is_admin(principal):
                    return True
            # Current allowlist members can manage the list
            if caller & _current_brd_allowlist():
                return True
            self._send_json(
                {
                    "error": "Only portal admins or current BRD allowlist members can manage the allowlist.",
                    "yourPrincipals": sorted(caller),
                    "currentAllowlist": sorted(_current_brd_allowlist()),
                    "hint": "Ask an admin to add one of 'yourPrincipals' to BRD_INTAKE_ALLOWED_PRINCIPALS env var or FACTORY_PORTAL_ADMINS.",
                },
                403,
            )
            return False

        # No auth configured — local dev
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

    def _handle_brd_allowlist_list(self):
        """GET /api/admin/brd-allowlist — effective allowlist + source breakdown."""
        env_seed = sorted(BRD_INTAKE_ALLOWED_PRINCIPALS)
        file_overlay = sorted(_load_brd_allowlist_file())
        effective = sorted(_current_brd_allowlist())
        self._send_json({
            "envSeed": env_seed,
            "fileOverlay": file_overlay,
            "effective": effective,
            "allowlistFile": str(BRD_ALLOWLIST_FILE),
            "note": "env seed is read-only (set BRD_INTAKE_ALLOWED_PRINCIPALS). file overlay is editable here.",
        })

    def _handle_brd_allowlist_update(self):
        """POST /api/admin/brd-allowlist — add/remove/set principals in the file overlay."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception as exc:
            self._send_json({"error": f"Invalid request: {exc}"}, 400)
            return

        action = str(payload.get("action", "add")).strip().lower() or "add"
        raw = payload.get("principals")
        if raw is None and "principal" in payload:
            raw = [payload.get("principal")]
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            raw = []
        cleaned = []
        for p in raw:
            if isinstance(p, str):
                norm = p.strip().lower()
                if norm and norm not in cleaned:
                    cleaned.append(norm)

        if action not in {"add", "remove", "set"}:
            self._send_json({"error": "action must be add, remove, or set"}, 400)
            return
        if action in {"add", "remove"} and not cleaned:
            self._send_json({"error": "principals list cannot be empty for add/remove"}, 400)
            return

        current = _load_brd_allowlist_file()
        if action == "add":
            current |= set(cleaned)
        elif action == "remove":
            current -= set(cleaned)
        else:
            current = set(cleaned)

        _save_brd_allowlist_file(current)
        self._send_json({
            "ok": True,
            "action": action,
            "fileOverlay": sorted(current),
            "effective": sorted(BRD_INTAKE_ALLOWED_PRINCIPALS | current),
        })

    # ---- Copilot CLI run handlers ---------------------------------------

    def _handle_copilot_get(self, request_path: str):
        """Route GET /api/projects/<slug>/copilot* paths."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        parts = request_path.split("/")
        # ['', 'api', 'projects', '<slug>', 'copilot-<suffix>', ...]
        if len(parts) < 5:
            self._send_json({"error": "Invalid copilot path"}, 400)
            return
        slug = parts[3]
        action = parts[4]

        project_root = self._resolve_project_root(slug)
        if project_root is None:
            self._send_json({"error": "Project not found"}, 404)
            return

        if action == "copilot-runtime" and len(parts) == 5:
            info = copilot_runner.runtime_info()
            self._send_json(info)
            return

        if action == "copilot-runs":
            if len(parts) == 5:
                runs = copilot_runner.list_runs(project_root)
                self._send_json({"slug": slug, "runs": runs})
                return
            # /copilot-runs/<runId>[/log|/diff]
            run_id = parts[5]
            if len(parts) == 6:
                run = copilot_runner.get_run(project_root, run_id)
                if run is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(run)
                return
            if len(parts) == 7 and parts[6] == "log":
                tail = copilot_runner.read_log_tail(project_root, run_id)
                if tail is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                body = tail.encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if len(parts) == 7 and parts[6] == "diff":
                diff = copilot_runner.diff_run(project_root, run_id)
                if diff is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(diff)
                return

        self._send_json({"error": "Invalid copilot path"}, 400)

    def _handle_copilot_post(self, path: str):
        """Route POST /api/projects/<slug>/copilot-runs[/<id>/cancel]."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        parts = path.split("/")
        # ['', 'api', 'projects', '<slug>', 'copilot-runs', ...]
        if len(parts) < 5:
            self._send_json({"error": "Invalid copilot path"}, 400)
            return
        slug = parts[3]
        project_root = self._resolve_project_root(slug)
        if project_root is None:
            self._send_json({"error": "Project not found"}, 404)
            return

        # Cancel: /copilot-runs/<runId>/cancel
        if len(parts) == 7 and parts[4] == "copilot-runs" and parts[6] == "cancel":
            run_id = parts[5]
            result = copilot_runner.cancel_run(project_root, run_id)
            if result is None:
                self._send_json({"error": "Run not found"}, 404)
                return
            self._send_json({"ok": True, "run": result})
            return

        # Start: /copilot-runs
        if len(parts) == 5 and parts[4] == "copilot-runs":
            content_length = self._safe_content_length()
            if content_length is None:
                return
            try:
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body) if body else {}
            except Exception as exc:
                self._send_json({"error": f"Invalid request: {exc}"}, 400)
                return

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send_json({"error": "prompt is required"}, 400)
                return

            model_raw = str(payload.get("model", "") or "").strip()
            session_raw = str(payload.get("sessionId", "") or "").strip()
            agent_raw = str(payload.get("agent", "") or "").strip()
            # Reject obviously unsafe values — model names are alnum + .- only,
            # session IDs are UUIDs.
            if model_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", model_raw):
                self._send_json({"error": "Invalid model name"}, 400)
                return
            if session_raw and not re.fullmatch(r"[A-Fa-f0-9\-]{8,64}", session_raw):
                self._send_json({"error": "Invalid sessionId"}, 400)
                return
            if agent_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", agent_raw):
                self._send_json({"error": "Invalid agent name"}, 400)
                return

            try:
                metadata = copilot_runner.start_run(
                    project_root,
                    prompt,
                    requested_by=self._authorized_user() or "",
                    model=model_raw or None,
                    session_id=session_raw or None,
                    agent=agent_raw or None,
                )
            except copilot_runner.CopilotRunError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Copilot run start failed for %s", slug)
                self._send_json({"error": f"Failed to start run: {exc}"}, 500)
                return

            self._send_json({"ok": True, "run": metadata}, 202)
            return

        self._send_json({"error": "Invalid copilot path"}, 400)

    # --- Repo-root Copilot CLI handlers ------------------------------------

    def _handle_copilot_root_get(self, request_path: str):
        """Route GET /api/copilot-runtime, /api/copilot-agents, /api/copilot-runs[...]."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        if request_path == "/api/copilot-runtime":
            info = copilot_runner.runtime_info()
            info["scope"] = "repo"
            info["repoRoot"] = str(FACTORY_REPO_ROOT)
            self._send_json(info)
            return

        if request_path == "/api/copilot-agents":
            try:
                agents = copilot_runner.list_agents(FACTORY_REPO_ROOT)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Copilot agent discovery failed")
                self._send_json({"error": f"Failed to list agents: {exc}"}, 500)
                return
            self._send_json({"agents": agents})
            return

        parts = request_path.split("/")
        # ['', 'api', 'copilot-runs', ...]
        if len(parts) >= 3 and parts[2] == "copilot-runs":
            if len(parts) == 3:
                runs = copilot_runner.list_runs(FACTORY_REPO_ROOT)
                self._send_json({"scope": "repo", "runs": runs})
                return
            run_id = parts[3]
            if len(parts) == 4:
                run = copilot_runner.get_run(FACTORY_REPO_ROOT, run_id)
                if run is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(run)
                return
            if len(parts) == 5 and parts[4] == "log":
                tail = copilot_runner.read_log_tail(FACTORY_REPO_ROOT, run_id)
                if tail is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                body = tail.encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if len(parts) == 5 and parts[4] == "diff":
                diff = copilot_runner.diff_run(FACTORY_REPO_ROOT, run_id)
                if diff is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(diff)
                return

        self._send_json({"error": "Invalid copilot path"}, 400)

    def _handle_copilot_root_post(self, path: str):
        """Route POST /api/copilot-runs[/<id>/cancel] — repo-root scope."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        parts = path.split("/")
        # Cancel: /api/copilot-runs/<runId>/cancel
        if len(parts) == 5 and parts[2] == "copilot-runs" and parts[4] == "cancel":
            run_id = parts[3]
            result = copilot_runner.cancel_run(FACTORY_REPO_ROOT, run_id)
            if result is None:
                self._send_json({"error": "Run not found"}, 404)
                return
            self._send_json({"ok": True, "run": result})
            return

        # Start: /api/copilot-runs
        if len(parts) == 3 and parts[2] == "copilot-runs":
            content_length = self._safe_content_length()
            if content_length is None:
                return
            try:
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body) if body else {}
            except Exception as exc:
                self._send_json({"error": f"Invalid request: {exc}"}, 400)
                return

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send_json({"error": "prompt is required"}, 400)
                return

            model_raw = str(payload.get("model", "") or "").strip()
            session_raw = str(payload.get("sessionId", "") or "").strip()
            agent_raw = str(payload.get("agent", "") or "").strip()
            if model_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", model_raw):
                self._send_json({"error": "Invalid model name"}, 400)
                return
            if session_raw and not re.fullmatch(r"[A-Fa-f0-9\-]{8,64}", session_raw):
                self._send_json({"error": "Invalid sessionId"}, 400)
                return
            if agent_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", agent_raw):
                self._send_json({"error": "Invalid agent name"}, 400)
                return

            try:
                metadata = copilot_runner.start_run(
                    FACTORY_REPO_ROOT,
                    prompt,
                    requested_by=self._authorized_user() or "",
                    model=model_raw or None,
                    session_id=session_raw or None,
                    agent=agent_raw or None,
                )
            except copilot_runner.CopilotRunError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Repo-root Copilot run start failed")
                self._send_json({"error": f"Failed to start run: {exc}"}, 500)
                return

            self._send_json({"ok": True, "run": metadata}, 202)
            return

        self._send_json({"error": "Invalid copilot path"}, 400)

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

    # ---------------------------------------------------------------------
    # BRD Copilot (Phase 1 prototype) — grounded chat that drafts BRDs
    # ---------------------------------------------------------------------
    _BRD_CHAT_SYSTEM_PROMPT = (
        "You are BRD Copilot, an assistant embedded in the Azure Architecture Factory (AAF) portal. "
        "Your job is to help a user author a Business Requirements Document (BRD) that AAF can turn "
        "into an Azure architecture, service code, and infrastructure-as-code.\n\n"
        "AAF CAPABILITIES:\n"
        "- Languages: Python 3.11 / FastAPI  OR  .NET 8 / ASP.NET Core Minimal APIs.\n"
        "- Infrastructure-as-Code: Bicep (Azure-native) OR Terraform (azurerm ~> 4.14).\n"
        "- Network tiers: public (default) | vnet-integrated | private.\n"
        "- Archetypes (auto-detected from BRD content): extraction-chat (LLM extraction/chat over "
        "customer documents), rag-qa (retrieval-augmented Q&A), api-service (generic backend).\n"
        "- Optional toggles: generateInfra, runSecurityAudit, enableObservability.\n\n"
        "GOOD BRD STRUCTURE:\n"
        "# Project: <name>\n"
        "## Business Goal\n## Key Requirements\n## Success Criteria\n## Out of Scope\n"
        "## Timeline\n"
        "Optional hint lines the factory understands:\n"
        "  Implementation language: python | dotnet\n"
        "  Infrastructure as code: bicep | terraform\n"
        "  Network tier: public | vnet-integrated | private\n\n"
        "INTERACTION RULES:\n"
        "1. Ask clarifying questions only when the request is genuinely ambiguous. Otherwise draft.\n"
        "2. Prefer concrete, narrow scope. Do not invent requirements the user did not imply.\n"
        "3. When you have enough to draft, return a BRD in `brd_draft`. You can revise on follow-ups.\n"
        "4. Suggest language/IaC/network based on the workload: "
        "Python for AI/ML and RAG; .NET for heavy throughput enterprise APIs; "
        "Terraform when the user mentions multi-cloud or existing Terraform estate; "
        "vnet-integrated or private when they mention regulated data, HIPAA, PCI, or on-prem integration.\n"
        "5. Slugify project name to kebab-case for `suggested_slug` (lowercase, alphanumeric + hyphens).\n\n"
        "REVIEW MODE — triggered when the user pastes an existing BRD and asks for evaluation, "
        "readiness, gaps, or missing information:\n"
        "  a. Score the BRD against this readiness rubric (1 point per item, max 10):\n"
        "     [1] Clear business goal in one sentence\n"
        "     [2] Named primary users / personas and their job-to-be-done\n"
        "     [3] Concrete key requirements (verbs + nouns, not aspirations)\n"
        "     [4] Measurable success criteria (numbers, SLOs, adoption targets)\n"
        "     [5] Explicit out-of-scope section (what we are NOT building)\n"
        "     [6] Data sources and data sensitivity identified (PII / PHI / PCI / public)\n"
        "     [7] Integration points with existing systems listed\n"
        "     [8] Non-functional requirements (performance, availability, security, compliance)\n"
        "     [9] Timeline or milestone expectations\n"
        "     [10] Factory hints stated or inferable (language, IaC, network tier)\n"
        "  b. In `reply`, output a markdown scorecard: total score, per-item ✅/⚠️/❌ with a "
        "one-line justification, then a 'Missing information' section listing targeted "
        "questions the user should answer. Ask those questions directly — do not hedge.\n"
        "  c. In `brd_draft`, return an IMPROVED version of the BRD that fills safe gaps "
        "(structure, section headers, normalized hints) and flags the user-answerable gaps "
        "with `TODO:` markers inline so the user can complete them. Do NOT fabricate domain "
        "facts (users, SLAs, data sources) — use `TODO:` instead.\n"
        "  d. If the user follows up with answers, revise `brd_draft` by replacing the "
        "corresponding TODOs. Re-score and show the delta.\n\n"
        "RESPONSE FORMAT: You MUST respond with a single JSON object with these keys:\n"
        '  "reply": string — your chat message to the user (concise, markdown allowed).\n'
        '  "brd_draft": string | null — full BRD markdown ready to paste, or null if not yet drafting.\n'
        '  "suggested_slug": string | null — kebab-case project slug, or null.\n'
        '  "suggested_options": object | null — any of: implementation_language ("python"|"dotnet"), '
        'iac_tool ("bicep"|"terraform"), network_tier ("public"|"vnet-integrated"|"private"). Omit keys you cannot justify.\n'
        "No prose outside the JSON object.\n\n"
        "SELF-AWARENESS: You are **BRD Copilot**, focused on authoring and reviewing BRDs. A separate "
        "copilot, **Project Copilot** (🛠️ per-project, bottom-right), is tool-enabled and answers "
        "questions about an already-generated project (architecture, cost, observability, deploy commands). "
        "You do NOT have tools; you do NOT read project files. If the user asks about an existing project's "
        "cost, observability, or deployment, tell them to use Project Copilot from that project's card. "
        "Full reference: `docs/COPILOT_GUIDE.md`."
    )

    def _handle_brd_chat(self):
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        raw_messages = payload.get("messages", [])
        if not isinstance(raw_messages, list) or not raw_messages:
            self._send_json({"error": "messages must be a non-empty list"}, 400)
            return

        # Sanitize: keep only {role, content} strings, cap length/count.
        cleaned: list[dict] = []
        for m in raw_messages[-20:]:  # last 20 turns max
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", "")).strip().lower()
            content = str(m.get("content", "")).strip()
            if role not in ("user", "assistant") or not content:
                continue
            cleaned.append({"role": role, "content": content[:4000]})

        if not cleaned:
            self._send_json({"error": "messages must contain at least one user turn"}, 400)
            return

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
        auth = _aoai_auth_header()

        # Graceful fallback when Azure OpenAI is not configured — prototype still visible.
        if not (endpoint and deployment and auth):
            self._send_json(
                {
                    "reply": (
                        "**BRD Copilot is not configured on this portal.**\n\n"
                        "To enable it, set these environment variables on the portal server and restart:\n\n"
                        "- `AZURE_OPENAI_ENDPOINT`\n"
                        "- `AZURE_OPENAI_DEPLOYMENT` (e.g., `gpt-4o`, `gpt-4o-mini`)\n"
                        "- `AZURE_OPENAI_API_KEY`\n\n"
                        "Until then, you can still author BRDs manually in the form above. The portal "
                        "dropdowns (language, IaC tool, network tier) already let you override anything "
                        "the factory would auto-detect."
                    ),
                    "brd_draft": None,
                    "suggested_slug": None,
                    "suggested_options": None,
                    "stub_mode": True,
                },
                200,
            )
            return

        chat_messages = [{"role": "system", "content": self._BRD_CHAT_SYSTEM_PROMPT}] + cleaned

        request_body = json.dumps(
            {
                "messages": chat_messages,
                "temperature": 0.3,
                "max_tokens": 1800,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        req = Request(url, data=request_body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header(auth[0], auth[1])

        try:
            with urlopen(req, timeout=45) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
        except URLError as e:
            logging.warning("BRD chat upstream error: %s", e)
            self._send_json({"error": f"Azure OpenAI call failed: {e}"}, 502)
            return
        except Exception as e:
            logging.warning("BRD chat unexpected error: %s", e)
            self._send_json({"error": f"Azure OpenAI call failed: {e}"}, 502)
            return

        try:
            raw_content = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_content)
        except Exception as e:
            logging.warning("BRD chat response parse error: %s; raw=%r", e, data)
            self._send_json(
                {
                    "reply": (
                        "I couldn't parse a structured reply this time. Could you rephrase? "
                        "(The model returned free text instead of JSON.)"
                    ),
                    "brd_draft": None,
                    "suggested_slug": None,
                    "suggested_options": None,
                },
                200,
            )
            return

        # Narrow response to the documented contract; drop anything unexpected.
        reply = str(parsed.get("reply", "")).strip() or "(no reply)"
        brd_draft = parsed.get("brd_draft")
        if brd_draft is not None and not isinstance(brd_draft, str):
            brd_draft = None
        suggested_slug = parsed.get("suggested_slug")
        if suggested_slug is not None and not isinstance(suggested_slug, str):
            suggested_slug = None
        opts = parsed.get("suggested_options")
        clean_opts: dict = {}
        if isinstance(opts, dict):
            il = opts.get("implementation_language")
            if il in ("python", "dotnet"):
                clean_opts["implementation_language"] = il
            iac = opts.get("iac_tool")
            if iac in ("bicep", "terraform"):
                clean_opts["iac_tool"] = iac
            nt = opts.get("network_tier")
            if nt in ("public", "vnet-integrated", "private"):
                clean_opts["network_tier"] = nt

        self._send_json(
            {
                "reply": reply,
                "brd_draft": brd_draft,
                "suggested_slug": suggested_slug,
                "suggested_options": clean_opts or None,
            },
            200,
        )

    # ---------------------------------------------------------------------
    # Per-project Copilot (Phase 2 prototype)
    # - Architecture Q&A  - Cost evaluation  - Operations  - Observability
    # ---------------------------------------------------------------------
    _PROJECT_CHAT_SYSTEM_PROMPT = (
        "You are Project Copilot, embedded in the Azure Architecture Factory (AAF) portal. "
        "You answer questions about ONE specific generated project. You have access to a "
        "READ-ONLY context bundle (project-manifest.json excerpts, doc excerpts, infra "
        "excerpts) injected below by the server. You are an expert on:\n"
        "  1. Architecture & code — what services exist, how they connect, which archetype was used.\n"
        "  2. Cost evaluation — estimate monthly Azure spend from the infra resources and offer "
        "concrete cost-reduction moves (tier downgrade, autoscale, reserved capacity, serverless).\n"
        "  3. Operations — deployment, rollout strategy, rollback, incident response, health probes, "
        "scaling, backup/restore, disaster recovery.\n"
        "  4. Observability — Application Insights wiring, Log Analytics, KQL queries, alert rules, "
        "dashboards, SLOs/SLIs, distributed tracing.\n\n"
        "RULES:\n"
        "- Ground every answer in the provided CONTEXT. If the context does not contain the answer, "
        "say so plainly and suggest what file the user should look at.\n"
        "- When asked about cost, always list assumptions (region, traffic, retention) and give a "
        "rough monthly USD range per resource. Prefer Azure list prices (East US 2) unless the "
        "manifest says otherwise.\n"
        "- Never invent file paths, resource names, or SKUs that are not in the context.\n"
        "- Keep responses under ~500 words unless the user explicitly asks for more depth.\n"
        "- Use concise markdown: short paragraphs, bullet lists, tables for cost/ops summaries.\n"
        "- When suggesting changes, reference the exact file path the user would edit "
        "(e.g., `infra/modules/compute/containerapp.bicep`)."
    )

    # Per-project file budget — keep total prompt bounded.
    _PROJECT_CHAT_MAX_CONTEXT_CHARS = 18_000
    _PROJECT_CHAT_DOC_FILES = (
        "docs/architecture-overview.md",
        "docs/detailed-architecture.md",
        "docs/production-readiness.md",
        "docs/governance-model.md",
        "docs/traceability-matrix.md",
        "docs/delivery-milestones.md",
        "docs/success-criteria.md",
        "README.md",
        "DEPLOY.md",
    )
    _PROJECT_CHAT_INFRA_GLOBS = ("main.bicep", "main.tf", "main.bicepparam")

    def _build_project_chat_context(self, project_root: pathlib.Path) -> str:
        """Read a bounded bundle of project files and format as a system context block."""
        budget = self._PROJECT_CHAT_MAX_CONTEXT_CHARS
        chunks: list[str] = []

        def _add(label: str, body: str) -> None:
            nonlocal budget
            if budget <= 0 or not body:
                return
            body = body.strip()
            if len(body) > budget:
                body = body[: max(0, budget - 40)] + "\n…[truncated]"
            chunk = f"### {label}\n\n{body}\n"
            chunks.append(chunk)
            budget -= len(chunk)

        # 1. Manifest (compact — drop verbose prose fields).
        manifest_path = project_root / "project-manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                compact = {
                    "project": manifest.get("project"),
                    "title": manifest.get("title"),
                    "status": manifest.get("status"),
                    "capabilities": manifest.get("capabilities"),
                    "generation_options": manifest.get("generation_options"),
                    "analysis": manifest.get("analysis"),
                    "implementation_language": manifest.get("implementation_language"),
                    "iac_tool": manifest.get("iac_tool"),
                    "services": manifest.get("services"),
                    "architecture": manifest.get("architecture"),
                }
                compact = {k: v for k, v in compact.items() if v is not None}
                _add("project-manifest.json (compact)", json.dumps(compact, indent=2))
            except Exception:
                pass

        # 2. Doc excerpts.
        for rel in self._PROJECT_CHAT_DOC_FILES:
            if budget <= 0:
                break
            path = project_root / rel
            if path.is_file():
                try:
                    _add(rel, path.read_text(encoding="utf-8"))
                except Exception:
                    continue

        # 3. Infra — scan infra/ for the known roots.
        infra_dir = project_root / "infra"
        if infra_dir.is_dir() and budget > 0:
            for name in self._PROJECT_CHAT_INFRA_GLOBS:
                if budget <= 0:
                    break
                for infra_path in sorted(infra_dir.rglob(name)):
                    if budget <= 0:
                        break
                    try:
                        rel = infra_path.relative_to(project_root).as_posix()
                        _add(rel, infra_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue

        # 4. Dir listing (so the model can point the user at files it didn't ingest).
        if budget > 0:
            try:
                listing: list[str] = []
                for entry in sorted(project_root.rglob("*")):
                    if entry.is_dir():
                        continue
                    rel = entry.relative_to(project_root).as_posix()
                    # Skip heavyweight dirs we would never cite.
                    if rel.startswith(("logs/", ".git/", "node_modules/", "__pycache__/")):
                        continue
                    listing.append(rel)
                    if len(listing) >= 200:
                        break
                _add("file-tree (paths only, up to 200)", "\n".join(listing))
            except Exception:
                pass

        return "\n".join(chunks) if chunks else "(no project context available)"

    # ---------------------------------------------------------------------
    # Phase 3: Tool-calling for Project Copilot
    # All tools are READ-ONLY. No deploys. No writes. Paths are clamped
    # to the project root to prevent directory traversal.
    # ---------------------------------------------------------------------
    _PROJECT_CHAT_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "describe_my_capabilities",
                "description": (
                    "Return a machine-readable description of THIS copilot: who it is, what tools "
                    "it has, what it will not do, and pointers to the user-facing guide. Call this "
                    "whenever the user asks what you can do, what tools you have, how you work, "
                    "or what your limits are. The return value is authoritative — do not paraphrase "
                    "from memory, summarize the fields."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_project_file",
                "description": (
                    "Read the contents of a single file inside the current project. "
                    "Use this to inspect a file not included in the initial context "
                    "bundle. Returns up to 20 KB of text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path inside the project, e.g. 'infra/modules/compute/containerapp.bicep' or 'src/main.py'.",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_project_files",
                "description": (
                    "List files in the project matching a glob relative to the project root. "
                    "Returns up to 200 paths. Use this to discover files before calling read_project_file."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "glob": {
                            "type": "string",
                            "description": "Glob pattern, e.g. 'infra/**/*.bicep', 'src/**/*.py', 'docs/*.md'.",
                        }
                    },
                    "required": ["glob"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scan_cost_resources",
                "description": (
                    "Scan the project's infra files (Bicep and Terraform) and return a structured list "
                    "of billable Azure resources with their SKUs, kinds, and the file they were declared in. "
                    "Use this as the factual basis for cost estimation. Never invent resources not in the output."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scan_observability",
                "description": (
                    "Deterministic scan of infra + code for observability signals: Application Insights, "
                    "Log Analytics workspace, health probe endpoints, structured logging, alert rules, "
                    "OpenTelemetry wiring. Returns a checklist with present / missing items."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "prepare_deploy_commands",
                "description": (
                    "Return the copy-paste Azure CLI / azd commands to deploy this project, based on the "
                    "detected IaC tool (Bicep or Terraform). Does NOT execute anything. The user runs the "
                    "commands themselves in a terminal."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resource_group": {
                            "type": "string",
                            "description": "Target Azure resource group name. If unknown, pass 'rg-<slug>'.",
                        },
                        "location": {
                            "type": "string",
                            "description": "Azure region, e.g. 'eastus2'. Defaults to 'eastus2' if omitted.",
                        },
                    },
                    "required": [],
                },
            },
        },
    ]

    _PROJECT_CHAT_TOOL_MAX_FILE_BYTES = 20_000
    _PROJECT_CHAT_TOOL_MAX_ITERATIONS = 5

    def _tool_describe_my_capabilities(self, project_root: pathlib.Path, args: dict) -> str:
        return json.dumps({
            "name": "Project Copilot",
            "icon": "🛠️",
            "scope": "one specific factory-generated project",
            "grounding": "18 KB context bundle per turn (manifest + docs/*.md + infra/**/*.bicep|tf|bicepparam + src/ tests/ file tree)",
            "tool_calling": {
                "enabled": True,
                "max_iterations_per_turn": self._PROJECT_CHAT_TOOL_MAX_ITERATIONS,
                "tools": [
                    {"name": "describe_my_capabilities", "purpose": "self-introspection"},
                    {"name": "read_project_file", "purpose": "read a file (up to 20 KB), path clamped to project root"},
                    {"name": "list_project_files", "purpose": "glob the project tree (up to 200 paths)"},
                    {"name": "scan_cost_resources", "purpose": "deterministic infra scan returning billable resources + heuristic $/month"},
                    {"name": "scan_observability", "purpose": "deterministic 7-point observability checklist"},
                    {"name": "prepare_deploy_commands", "purpose": "return copy-paste az/azd/terraform CLI; does NOT execute"},
                ],
            },
            "safety": {
                "read_only": True,
                "path_traversal_blocked": True,
                "no_writes": True,
                "no_shell_execution": True,
                "no_azure_api_calls": True,
                "no_cross_project_access": True,
                "max_file_read_bytes": self._PROJECT_CHAT_TOOL_MAX_FILE_BYTES,
                "max_list_results": 200,
            },
            "cannot_do": [
                "Edit BRD, infra, or source code",
                "Run terraform apply, az deployment, azd up, or any shell command",
                "Call live Azure APIs, GitHub APIs, or any external HTTP",
                "Access files in other projects",
                "Persist conversation history (session only, cleared on refresh)",
            ],
            "sibling_copilot": {
                "name": "BRD Copilot",
                "scope": "BRD authoring + review",
                "how_to_reach": "bottom-left 💬 button on the portal (a separate copilot, not me)",
            },
            "user_guide": "/docs/COPILOT_GUIDE.md",
            "footer_shown_when_tools_used": "🛠️ Used: <tool_names>",
        })

    def _tool_read_project_file(self, project_root: pathlib.Path, args: dict) -> str:
        rel = str(args.get("path", "")).strip().lstrip("/\\")
        if not rel or ".." in rel.split("/") or ".." in rel.split("\\"):
            return json.dumps({"error": "invalid path"})
        target = (project_root / rel).resolve()
        if project_root.resolve() not in target.parents and target != project_root.resolve():
            return json.dumps({"error": "path escapes project root"})
        if not target.exists() or not target.is_file():
            return json.dumps({"error": f"file not found: {rel}"})
        try:
            data = target.read_bytes()
        except Exception as e:
            return json.dumps({"error": f"read failed: {e}"})
        truncated = False
        if len(data) > self._PROJECT_CHAT_TOOL_MAX_FILE_BYTES:
            data = data[: self._PROJECT_CHAT_TOOL_MAX_FILE_BYTES]
            truncated = True
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return json.dumps({"path": rel, "truncated": truncated, "content": text})

    def _tool_list_project_files(self, project_root: pathlib.Path, args: dict) -> str:
        glob = str(args.get("glob", "")).strip().lstrip("/\\")
        if not glob or ".." in glob:
            return json.dumps({"error": "invalid glob"})
        try:
            matches: list[str] = []
            for p in project_root.glob(glob):
                if p.is_file():
                    rel = p.relative_to(project_root).as_posix()
                    matches.append(rel)
                    if len(matches) >= 200:
                        break
            return json.dumps({"glob": glob, "count": len(matches), "paths": matches})
        except Exception as e:
            return json.dumps({"error": f"glob failed: {e}"})

    # Heuristic resource-cost table — rough list prices in USD/month, eastus2.
    # These are deliberately approximate; the chat model is instructed to show
    # assumptions and cite this as "heuristic, verify with Azure Pricing Calc".
    _COST_HEURISTICS_USD_MONTH = {
        "Microsoft.App/containerApps": (15, 120),
        "Microsoft.Web/sites": (13, 200),
        "Microsoft.Web/serverfarms": (13, 300),
        "Microsoft.DocumentDB/databaseAccounts": (25, 300),
        "Microsoft.Storage/storageAccounts": (2, 40),
        "Microsoft.KeyVault/vaults": (0, 5),
        "Microsoft.CognitiveServices/accounts": (20, 500),
        "Microsoft.Insights/components": (0, 50),
        "Microsoft.OperationalInsights/workspaces": (0, 80),
        "Microsoft.ContainerRegistry/registries": (5, 50),
        "Microsoft.ServiceBus/namespaces": (10, 100),
        "Microsoft.EventHub/namespaces": (10, 150),
        "Microsoft.Sql/servers": (0, 0),
        "Microsoft.Sql/servers/databases": (5, 200),
        "Microsoft.Cache/Redis": (17, 200),
        "Microsoft.ApiManagement/service": (150, 2700),
        "Microsoft.Network/virtualNetworks": (0, 0),
        "Microsoft.Network/networkSecurityGroups": (0, 0),
        "Microsoft.Network/privateEndpoints": (8, 12),
        "Microsoft.Search/searchServices": (75, 1000),
    }

    def _tool_scan_cost_resources(self, project_root: pathlib.Path, args: dict) -> str:
        infra = project_root / "infra"
        if not infra.is_dir():
            return json.dumps({"resources": [], "note": "No infra/ directory found."})

        resources: list[dict] = []
        # Bicep: match `resource <symbol> 'Microsoft.Foo/bar@<api>' = {`
        bicep_re = re.compile(
            r"resource\s+(\w+)\s+'([A-Za-z0-9.]+/[A-Za-z0-9/]+)@[^']+'\s*=",
        )
        # Terraform: match `resource "azurerm_<type>" "<name>"`
        tf_re = re.compile(r'resource\s+"(azurerm_[a-z0-9_]+)"\s+"([A-Za-z0-9_-]+)"')
        # Try to pull SKU / tier hints if nearby.
        sku_re = re.compile(r"(?i)\b(?:sku|tier|kind)\s*[:=]\s*['\"]?([A-Za-z0-9_.-]+)")

        for path in sorted(infra.rglob("*")):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not (name.endswith(".bicep") or name.endswith(".tf")):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = path.relative_to(project_root).as_posix()
            if name.endswith(".bicep"):
                for m in bicep_re.finditer(text):
                    symbol, rtype = m.group(1), m.group(2)
                    # Look ahead 400 chars for SKU/tier/kind
                    window = text[m.end(): m.end() + 400]
                    sku_match = sku_re.search(window)
                    low, high = self._COST_HEURISTICS_USD_MONTH.get(rtype, (0, 0))
                    resources.append({
                        "symbol": symbol,
                        "type": rtype,
                        "file": rel,
                        "sku_hint": sku_match.group(1) if sku_match else None,
                        "monthly_usd_low": low,
                        "monthly_usd_high": high,
                    })
            else:
                for m in tf_re.finditer(text):
                    tf_type, tf_name = m.group(1), m.group(2)
                    resources.append({
                        "symbol": tf_name,
                        "type": tf_type,
                        "file": rel,
                        "sku_hint": None,
                        "monthly_usd_low": 0,  # TF list would need a separate mapping
                        "monthly_usd_high": 0,
                    })

        total_low = sum(r["monthly_usd_low"] for r in resources)
        total_high = sum(r["monthly_usd_high"] for r in resources)
        return json.dumps({
            "resources": resources,
            "count": len(resources),
            "monthly_total_usd_low": total_low,
            "monthly_total_usd_high": total_high,
            "assumptions": [
                "Region: East US 2",
                "Consumption / Standard SKUs where not specified",
                "Low traffic (under 1M requests/mo, <10 GB egress)",
                "Log retention: 30 days",
                "Figures are heuristic. Verify with Azure Pricing Calculator before committing to budget.",
            ],
        })

    def _tool_scan_observability(self, project_root: pathlib.Path, args: dict) -> str:
        signals = {
            "application_insights": False,
            "log_analytics_workspace": False,
            "health_probe_endpoint": False,
            "structured_logging": False,
            "alert_rules": False,
            "opentelemetry": False,
            "diagnostic_settings": False,
        }
        evidence: dict[str, list[str]] = {k: [] for k in signals}

        # Scan infra
        infra = project_root / "infra"
        if infra.is_dir():
            for path in infra.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in (".bicep", ".tf", ".bicepparam"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                rel = path.relative_to(project_root).as_posix()
                lower = text.lower()
                if "microsoft.insights/components" in lower or "azurerm_application_insights" in lower:
                    signals["application_insights"] = True
                    evidence["application_insights"].append(rel)
                if "microsoft.operationalinsights/workspaces" in lower or "azurerm_log_analytics_workspace" in lower:
                    signals["log_analytics_workspace"] = True
                    evidence["log_analytics_workspace"].append(rel)
                if "microsoft.insights/metricalerts" in lower or "azurerm_monitor_metric_alert" in lower or "microsoft.insights/scheduledqueryrules" in lower:
                    signals["alert_rules"] = True
                    evidence["alert_rules"].append(rel)
                if "microsoft.insights/diagnosticsettings" in lower or "azurerm_monitor_diagnostic_setting" in lower:
                    signals["diagnostic_settings"] = True
                    evidence["diagnostic_settings"].append(rel)

        # Scan code for health probe + OTel + structured logging hints
        src = project_root / "src"
        if src.is_dir():
            for path in src.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in (".py", ".cs", ".ts", ".js"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                rel = path.relative_to(project_root).as_posix()
                lower = text.lower()
                if "/health" in lower or "/healthz" in lower or "healthcheck" in lower or "addhealthchecks" in lower:
                    signals["health_probe_endpoint"] = True
                    evidence["health_probe_endpoint"].append(rel)
                if "opentelemetry" in lower or "otlp" in lower or "addopentelemetry" in lower:
                    signals["opentelemetry"] = True
                    evidence["opentelemetry"].append(rel)
                if "ilogger<" in lower or "structlog" in lower or "logging.getlogger" in lower or "applicationinsights" in lower:
                    signals["structured_logging"] = True
                    evidence["structured_logging"].append(rel)

        # Cap evidence lists to 5 entries each for brevity.
        for k in evidence:
            evidence[k] = evidence[k][:5]

        return json.dumps({
            "signals": signals,
            "evidence": evidence,
            "score": f"{sum(1 for v in signals.values() if v)}/{len(signals)}",
        })

    def _tool_prepare_deploy_commands(self, project_root: pathlib.Path, slug: str, args: dict) -> str:
        rg = str(args.get("resource_group", "")).strip() or f"rg-{slug}"
        loc = str(args.get("location", "")).strip() or "eastus2"

        infra = project_root / "infra"
        has_bicep = infra.is_dir() and any(infra.rglob("main.bicep"))
        has_tf = infra.is_dir() and any(infra.rglob("main.tf"))
        has_azure_yaml = (project_root / "azure.yaml").is_file()

        blocks: list[dict] = []

        if has_azure_yaml:
            blocks.append({
                "tool": "azd",
                "title": "Deploy with Azure Developer CLI",
                "commands": [
                    "azd auth login",
                    f"azd env new {slug} --location {loc}",
                    "azd up",
                ],
            })

        if has_bicep:
            blocks.append({
                "tool": "az bicep",
                "title": "Deploy with Azure CLI + Bicep",
                "commands": [
                    "az login",
                    f"az group create --name {rg} --location {loc}",
                    f"az deployment group create --resource-group {rg} "
                    f"--template-file infra/main.bicep "
                    f"--parameters @infra/params/main.bicepparam",
                ],
            })

        if has_tf:
            blocks.append({
                "tool": "terraform",
                "title": "Deploy with Terraform",
                "commands": [
                    "az login",
                    "cd infra",
                    "terraform init",
                    "terraform validate",
                    f"terraform plan -var=\"resource_group_name={rg}\" -var=\"location={loc}\"",
                    "terraform apply",
                ],
            })

        if not blocks:
            blocks.append({
                "tool": "none",
                "title": "No deployment artifacts detected",
                "commands": [
                    "# This project does not contain infra/ or azure.yaml.",
                    "# Was it generated with generate_infra=false?",
                ],
            })

        return json.dumps({
            "resource_group": rg,
            "location": loc,
            "blocks": blocks,
            "note": "These commands are not executed by the portal — copy-paste into a terminal.",
        })

    def _execute_project_chat_tool(
        self,
        project_root: pathlib.Path,
        slug: str,
        tool_name: str,
        args: dict,
    ) -> str:
        try:
            if tool_name == "describe_my_capabilities":
                return self._tool_describe_my_capabilities(project_root, args)
            if tool_name == "read_project_file":
                return self._tool_read_project_file(project_root, args)
            if tool_name == "list_project_files":
                return self._tool_list_project_files(project_root, args)
            if tool_name == "scan_cost_resources":
                return self._tool_scan_cost_resources(project_root, args)
            if tool_name == "scan_observability":
                return self._tool_scan_observability(project_root, args)
            if tool_name == "prepare_deploy_commands":
                return self._tool_prepare_deploy_commands(project_root, slug, args)
            return json.dumps({"error": f"unknown tool: {tool_name}"})
        except Exception as e:
            logging.warning("Tool %s failed: %s", tool_name, e)
            return json.dumps({"error": f"tool {tool_name} failed: {e}"})

    def _call_aoai_raw(self, messages: list, *, tools: list | None = None,
                       max_tokens: int = 1500, temperature: float = 0.2) -> tuple[int, dict | str]:
        """Low-level AOAI call that returns the raw first-choice message dict (or error string)."""
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
        auth = _aoai_auth_header()

        if not (endpoint and deployment and auth):
            return 200, {
                "role": "assistant",
                "content": (
                    "**Project Copilot is not configured on this portal.**\n\n"
                    "Set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT` on the portal "
                    "server. For auth, either set `AZURE_OPENAI_API_KEY`, or install "
                    "`azure-identity` and sign in with `az login` so the portal can use "
                    "your Entra ID identity (works with `disableLocalAuth=true` accounts)."
                ),
            }

        req_body: dict = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            req_body["tools"] = tools
            req_body["tool_choice"] = "auto"

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        req = Request(url, data=json.dumps(req_body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header(auth[0], auth[1])

        try:
            data = json.loads(_aoai_urlopen(req, timeout=60).decode("utf-8"))
            return 200, data["choices"][0]["message"]
        except URLError as e:
            logging.warning("Azure OpenAI call failed: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"
        except Exception as e:
            logging.warning("Azure OpenAI unexpected error: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"

    def _handle_project_chat(self, slug: str):
        project_root = self._resolve_project_root(slug)
        if not project_root:
            self._send_json({"error": "Project not found"}, 404)
            return

        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        raw_messages = payload.get("messages", [])
        if not isinstance(raw_messages, list) or not raw_messages:
            self._send_json({"error": "messages must be a non-empty list"}, 400)
            return

        cleaned: list[dict] = []
        for m in raw_messages[-20:]:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", "")).strip().lower()
            content = str(m.get("content", "")).strip()
            if role not in ("user", "assistant") or not content:
                continue
            cleaned.append({"role": role, "content": content[:4000]})

        if not cleaned:
            self._send_json({"error": "messages must contain at least one user turn"}, 400)
            return

        context_block = self._build_project_chat_context(project_root)
        system_prompt = (
            f"{self._PROJECT_CHAT_SYSTEM_PROMPT}\n\n"
            f"### CURRENT PROJECT\n\nslug: `{slug}`\n\n"
            f"### CONTEXT\n\n{context_block}\n\n"
            "### TOOLS\n\n"
            "You have read-only tools to explore files, scan cost, audit observability, and prepare "
            "deploy commands. Prefer calling tools over guessing. Use `scan_cost_resources` before "
            "estimating cost, `scan_observability` before answering observability questions, and "
            "`prepare_deploy_commands` for any deployment request. Use `read_project_file` only when "
            "the context bundle does not already contain what you need.\n\n"
            "### SELF-AWARENESS\n\n"
            "You are **Project Copilot**, the tool-enabled per-project assistant. A separate copilot "
            "(**BRD Copilot**, bottom-left of the portal) handles BRD authoring and review — you do not. "
            "When the user asks what you can do, what tools you have, how you work, what you cannot do, "
            "or how you compare to the BRD Copilot, CALL `describe_my_capabilities` and summarize its "
            "return value. Never invent capabilities. The canonical user guide is `docs/COPILOT_GUIDE.md`."
        )

        chat_messages: list = [{"role": "system", "content": system_prompt}] + cleaned

        tools_used: list[dict] = []
        final_text: str = ""
        status_code = 200

        for iteration in range(self._PROJECT_CHAT_TOOL_MAX_ITERATIONS):
            status_code, msg = self._call_aoai_raw(
                chat_messages,
                tools=self._PROJECT_CHAT_TOOLS,
                max_tokens=1500,
                temperature=0.2,
            )
            if status_code != 200:
                final_text = msg if isinstance(msg, str) else str(msg)
                break
            if isinstance(msg, str):
                final_text = msg
                break

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                final_text = str(msg.get("content") or "").strip()
                break

            # Append the assistant's tool-call turn, then execute each tool.
            chat_messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
            })
            for call in tool_calls:
                tool_name = str(call.get("function", {}).get("name", ""))
                raw_args = str(call.get("function", {}).get("arguments", "{}"))
                try:
                    args = json.loads(raw_args) if raw_args else {}
                    if not isinstance(args, dict):
                        args = {}
                except Exception:
                    args = {}
                result = self._execute_project_chat_tool(project_root, slug, tool_name, args)
                tools_used.append({"name": tool_name, "args": args})
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": result,
                })
        else:
            # Loop exhausted without a terminal assistant message.
            final_text = (
                final_text
                or "⚠️ I used up my tool-call budget before I could finish. "
                "Try breaking the question into smaller pieces."
            )

        self._send_json(
            {
                "reply": final_text or "(no reply)",
                "slug": slug,
                "context_size": len(context_block),
                "tools_used": tools_used,
            },
            status_code,
        )

    # Shared Azure OpenAI caller used by BRD Copilot and Project Copilot.
    def _call_azure_openai(
        self,
        messages: list,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> tuple[int, str]:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
        auth = _aoai_auth_header()

        if not (endpoint and deployment and auth):
            return (
                200,
                "**Project Copilot is not configured on this portal.**\n\n"
                "Set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT` on the portal "
                "server. For auth, either set `AZURE_OPENAI_API_KEY`, or install "
                "`azure-identity` and sign in with `az login` so the portal can use "
                "your Entra ID identity.",
            )

        req_body: dict = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            req_body["response_format"] = response_format

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        req = Request(url, data=json.dumps(req_body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header(auth[0], auth[1])

        try:
            data = json.loads(_aoai_urlopen(req, timeout=60).decode("utf-8"))
            return 200, str(data["choices"][0]["message"]["content"]).strip()
        except URLError as e:
            logging.warning("Azure OpenAI call failed: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"
        except Exception as e:
            logging.warning("Azure OpenAI unexpected error: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"

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

    def _client_ip(self) -> str:
        """Best-effort caller IP. Honors X-Forwarded-For if present (Easy Auth / ACA)."""
        fwd = self.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()
        try:
            return self.client_address[0]
        except Exception:
            return "unknown"

    def _rate_limit_key(self) -> str:
        """Prefer authenticated UPN; fall back to client IP."""
        upn = None
        try:
            upn = self._authorized_user()
        except Exception:
            upn = None
        return f"user:{upn}" if upn else f"ip:{self._client_ip()}"

    def _check_intake_rate_limit(self) -> bool:
        """Return True if the caller is allowed; otherwise emit 429 and return False."""
        allowed, retry_after = _INTAKE_LIMITER.check(self._rate_limit_key())
        if allowed:
            return True
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Retry-After", str(retry_after))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Vary", "Origin")
        self.end_headers()
        body = json.dumps(
            {
                "error": "Rate limit exceeded",
                "limit": INTAKE_RATE_PER_MIN,
                "windowSeconds": INTAKE_RATE_WINDOW_SECONDS,
                "retryAfterSeconds": retry_after,
            }
        ).encode("utf-8")
        try:
            self.wfile.write(body)
        except Exception:
            pass
        return False

    def _handle_brd_intake(self):
        """Handle BRD intake submission (JSON body)"""
        if not self._check_intake_rate_limit():
            return
        content_type = self.headers.get("Content-Type", "")
        # Accept application/json with optional charset parameter. Reject
        # other content types outright so form posts can't bypass the JSON
        # schema check below.
        if not content_type.lower().split(";", 1)[0].strip() == "application/json":
            self._send_json({"error": "Expected Content-Type: application/json"}, 415)
            return
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        raw_file_name = payload.get("fileName", "brd.md")
        if not isinstance(raw_file_name, str) or len(raw_file_name) > MAX_BRD_FILENAME_LEN:
            self._send_json(
                {"error": f"fileName must be a string of at most {MAX_BRD_FILENAME_LEN} characters"},
                400,
            )
            return

        try:
            file_name = _sanitize_brd_filename(raw_file_name)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        raw_content = payload.get("content", "")
        content, err = _validate_brd_content(raw_content)
        if err is not None:
            self._send_json({"error": err}, 400)
            return

        if not file_name or not content:
            self._send_json({"error": "Missing fileName or content"}, 400)
            return

        generation_options = {
            "enableObservability": _coerce_bool(payload.get("enableObservability"), default=True),
            "generateInfra": _coerce_bool(payload.get("generateInfra"), default=True),
            "runSecurityAudit": _coerce_bool(payload.get("runSecurityAudit"), default=True),
            "networkTier": _sanitize_network_tier(payload.get("networkTier", "public")),
        }
        impl_lang = str(payload.get("implementationLanguage") or "").strip().lower()
        if impl_lang:
            generation_options["implementationLanguage"] = impl_lang
        iac_tool = str(payload.get("iacTool") or "").strip().lower()
        if iac_tool:
            generation_options["iacTool"] = iac_tool

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
                "createdAt": _utcnow_iso(),
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
        tracer = get_tracer("aaf-portal.pipeline")
        with tracer.start_as_current_span("brd.pipeline") as span:
            span.set_attribute("aaf.run_id", run_id)
            span.set_attribute("aaf.brd_path", str(brd_path))
            if owner:
                span.set_attribute("aaf.owner", owner)

            with RUNS_LOCK:
                RUNS[run_id]["status"] = "running"
                RUNS[run_id]["startedAt"] = _utcnow_iso()
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
                            "finishedAt": _utcnow_iso(),
                            "returnCode": 0,
                            "stdout": None,
                            "stderr": None,
                            "command": "azure_native_factory_runner",
                            "result": output,
                        }
                    )
                    _persist_runs_unlocked()

                span.set_attribute("aaf.status", "completed")
                logger.info(f"Pipeline completed for run {run_id}: returnCode=0")
            except Exception as e:
                logger.exception(f"Pipeline error for run {run_id}: {e}")
                span.set_attribute("aaf.status", "failed")
                span.record_exception(e)
                with RUNS_LOCK:
                    RUNS[run_id].update(
                        {
                            "status": "failed",
                            "finishedAt": _utcnow_iso(),
                            "returnCode": -1,
                            "stderr": str(e),
                            "result": {"status": "failed", "message": str(e)},
                        }
                    )
                    _persist_runs_unlocked()

    def _handle_brd_upload(self):
        """Handle multipart/form-data BRD file upload."""
        if not self._check_intake_rate_limit():
            return
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
        generate_infra_field = (fields.get("generate_infra") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        run_security_audit_field = (fields.get("run_security_audit") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        network_tier_field = (fields.get("network_tier") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        implementation_language_field = (fields.get("implementation_language") or {}).get("data", b"").decode("utf-8", errors="replace").strip().lower()
        iac_tool_field = (fields.get("iac_tool") or {}).get("data", b"").decode("utf-8", errors="replace").strip().lower()
        brd_field = fields.get("brd_file")

        if not brd_field:
            self._send_json({"error": "Missing brd_file field"}, 400)
            return

        try:
            raw_decoded = brd_field["data"].decode("utf-8")
        except UnicodeDecodeError:
            self._send_json({"error": "BRD file must be UTF-8 encoded text"}, 400)
            return

        content, err = _validate_brd_content(raw_decoded)
        if err is not None:
            self._send_json({"error": err}, 400)
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
            "generateInfra": _coerce_bool(generate_infra_field, default=True),
            "runSecurityAudit": _coerce_bool(run_security_audit_field, default=True),
            "networkTier": _sanitize_network_tier(network_tier_field),
        }
        if implementation_language_field:
            generation_options["implementationLanguage"] = implementation_language_field
        if iac_tool_field:
            generation_options["iacTool"] = iac_tool_field

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

        # Drop ghost entries: persisted feed sometimes lists slugs whose
        # projects/<slug>/ directory was deleted or never synced. If the UI
        # links users to those slugs, every subsequent API call (chat, files,
        # analysis) 404s. Filter them out here so the feed only ever advertises
        # projects we can actually serve.
        if projects_dir.is_dir():
            merged = [p for p in merged if (projects_dir / (p.get("slug") or "")).is_dir()]

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
                "timeUtc": _utcnow_iso(),
                "uptimeSeconds": uptime_seconds,
            },
            200,
        )

    def _handle_ready(self):
        """Readiness probe verifying portal can actually serve intake traffic.

        Critical checks (gate 503):
          - portalHtml: factory-portal.html is present
          - projectsDir: projects/ directory exists
          - intakeDirWritable: docs/intake/ can be written + deleted

        Informational (reported but do not gate):
          - otelEnabled: OpenTelemetry exporter initialized
          - rateLimiterActive: always True when reached (proves module loaded)
          - blobStorage: cached HEAD probe against container when BLOB_ENABLED
        """
        portal_file = FACTORY_REPO_ROOT / "factory-portal.html"
        projects_dir = FACTORY_REPO_ROOT / "projects"
        intake_dir = FACTORY_REPO_ROOT / "docs" / "intake"

        checks: dict = {
            "portalHtml": portal_file.is_file(),
            "projectsDir": projects_dir.is_dir(),
            "intakeDirWritable": _probe_intake_writable(intake_dir),
        }
        critical_ok = all(checks.values())

        info: dict = {
            "otelEnabled": _otel_enabled(),
            "rateLimiterActive": _INTAKE_LIMITER is not None,
        }
        if blob_sync.BLOB_ENABLED:
            info["blobStorage"] = _probe_blob_storage_cached()

        ready = critical_ok
        status = 200 if ready else 503
        return self._send_json(
            {
                "status": "ready" if ready else "not_ready",
                "service": "azure-architecture-factory-portal",
                "probe": "readiness",
                "timeUtc": _utcnow_iso(),
                "checks": checks,
                "info": info,
            },
            status,
        )

    # Extensions/paths the browser can safely cache for a few seconds.
    # Short max-age lets F5 inside the window serve from memory-cache instantly
    # without a conditional request, while still picking up edits within ~10s.
    _STATIC_CACHE_EXTS = (".html", ".css", ".js", ".svg", ".png", ".jpg",
                          ".jpeg", ".gif", ".ico", ".woff", ".woff2")

    def _is_static_cacheable(self) -> bool:
        try:
            path = urlparse(self.path).path.lower()
        except Exception:
            return False
        if path.startswith("/api/") or path.startswith("/.auth/"):
            return False
        return path.endswith(self._STATIC_CACHE_EXTS)

    def end_headers(self):
        """Add CORS headers to all responses"""
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key, Authorization")
        self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self._is_static_cacheable():
            # Short, must-revalidate window so rapid reloads are instant but
            # real edits are picked up on the next poll.
            self.send_header("Cache-Control", "private, max-age=10, must-revalidate")
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

    # Initialize OpenTelemetry / Azure Monitor. Safe no-op when deps are not
    # installed or APPLICATIONINSIGHTS_CONNECTION_STRING is not set.
    if init_otel(service_name="aaf-portal", service_version=os.environ.get("AAFACTORY_VERSION", "dev")):
        logger.info("OpenTelemetry initialized (Azure Monitor exporter active)")
    else:
        logger.info("OpenTelemetry not initialized (no connection string or deps missing)")

    # ThreadingHTTPServer handles concurrent HTTP requests instead of serializing
    # them. Previously a single slow request blocked every other client on the
    # TCP accept loop; this is particularly visible under burst load or when
    # several users poll status at once.
    _restore_runs_on_startup()
    _start_watchdog()
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
