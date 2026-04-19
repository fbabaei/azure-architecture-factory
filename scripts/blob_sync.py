"""Stdlib-only Azure Blob sync for portal persistence.

Uses IMDS (Container Apps managed identity) to fetch AAD tokens, then the
Blob REST API to list / get / put blobs. No SDK dependency.

Layout in the blob container (default: 'portal-data'):
  feed/factory-projects.generated.json
  owners/.portal-owners.json
  projects/{slug}/...files...

On startup we download everything to the local working copy. On write
events (new BRD → new project folder + feed update) we upload the delta.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config

BLOB_ACCOUNT = os.environ.get("FACTORY_PORTAL_BLOB_ACCOUNT", "").strip()
BLOB_CONTAINER = os.environ.get("FACTORY_PORTAL_BLOB_CONTAINER", "portal-data").strip()
BLOB_ENABLED = bool(BLOB_ACCOUNT)

_API_VERSION = "2021-12-02"
_RESOURCE = "https://storage.azure.com/"
_IMDS_ENDPOINT = os.environ.get(
    "IDENTITY_ENDPOINT"  # Container Apps sets this for MI
) or "http://169.254.169.254/metadata/identity/oauth2/token"
_IMDS_HEADER = os.environ.get("IDENTITY_HEADER", "")  # Container Apps secret header

# ---------------------------------------------------------------------------
# Token cache


_token_lock = threading.Lock()
_token_value: str | None = None
_token_exp: float = 0.0


def _fetch_token() -> str:
    global _token_value, _token_exp
    with _token_lock:
        now = time.time()
        if _token_value and _token_exp - now > 120:
            return _token_value
        # Container Apps IDENTITY_ENDPOINT uses api-version=2019-08-01 and a
        # header secret; IMDS fallback uses 2018-02-01 and a Metadata header.
        if "IDENTITY_ENDPOINT" in os.environ and _IMDS_HEADER:
            url = (f"{_IMDS_ENDPOINT}?api-version=2019-08-01"
                   f"&resource={urllib.parse.quote(_RESOURCE, safe='')}")
            req = urllib.request.Request(url, headers={"X-IDENTITY-HEADER": _IMDS_HEADER})
        else:
            url = (f"{_IMDS_ENDPOINT}?api-version=2018-02-01"
                   f"&resource={urllib.parse.quote(_RESOURCE, safe='')}")
            req = urllib.request.Request(url, headers={"Metadata": "true"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        _token_value = payload["access_token"]
        _token_exp = now + int(payload.get("expires_in", "3600"))
        return _token_value


# ---------------------------------------------------------------------------
# REST helpers


def _blob_url(blob_name: str) -> str:
    return (f"https://{BLOB_ACCOUNT}.blob.core.windows.net/"
            f"{BLOB_CONTAINER}/{urllib.parse.quote(blob_name, safe='/')}")


def _auth_headers(extra: dict | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {_fetch_token()}",
        "x-ms-version": _API_VERSION,
        "x-ms-date": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()),
    }
    if extra:
        h.update(extra)
    return h


def _list_blobs(prefix: str = "") -> list[str]:
    """Return all blob names in the container (optionally under prefix)."""
    names: list[str] = []
    marker = None
    while True:
        params = {
            "restype": "container",
            "comp": "list",
            "prefix": prefix,
            "maxresults": "5000",
        }
        if marker:
            params["marker"] = marker
        url = (f"https://{BLOB_ACCOUNT}.blob.core.windows.net/"
               f"{BLOB_CONTAINER}?{urllib.parse.urlencode(params)}")
        req = urllib.request.Request(url, headers=_auth_headers())
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
        root = ET.fromstring(body)
        for blob in root.iter("Blob"):
            name_el = blob.find("Name")
            if name_el is not None and name_el.text:
                names.append(name_el.text)
        marker_el = root.find("NextMarker")
        marker = marker_el.text if marker_el is not None and marker_el.text else None
        if not marker:
            break
    return names


def _download_blob(blob_name: str) -> bytes:
    req = urllib.request.Request(_blob_url(blob_name), headers=_auth_headers())
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _upload_blob(blob_name: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    req = urllib.request.Request(
        _blob_url(blob_name),
        data=data,
        method="PUT",
        headers=_auth_headers({
            "x-ms-blob-type": "BlockBlob",
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        }),
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        resp.read()


def _delete_blob(blob_name: str) -> None:
    req = urllib.request.Request(
        _blob_url(blob_name), method="DELETE", headers=_auth_headers()
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise


# ---------------------------------------------------------------------------
# Path conventions


FEED_BLOB = "feed/factory-projects.generated.json"
OWNERS_BLOB = "owners/.portal-owners.json"
PROJECTS_PREFIX = "projects/"


def _content_type_for(name: str) -> str:
    ext = pathlib.Path(name).suffix.lower()
    return {
        ".json": "application/json; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".py": "text/x-python; charset=utf-8",
        ".yaml": "application/yaml; charset=utf-8",
        ".yml": "application/yaml; charset=utf-8",
        ".bicep": "text/plain; charset=utf-8",
        ".drawio": "application/xml; charset=utf-8",
        ".xml": "application/xml; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
    }.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# Public API


def sync_down(repo_root: pathlib.Path) -> dict:
    """Download feed, owners, and all projects from blob to local disk.

    Returns a summary dict for logging.
    """
    if not BLOB_ENABLED:
        return {"enabled": False}
    projects_root = repo_root / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)

    counts = {"feed": 0, "owners": 0, "projects_files": 0, "skipped": 0}

    # Feed
    try:
        data = _download_blob(FEED_BLOB)
        (repo_root / "factory-projects.generated.json").write_bytes(data)
        counts["feed"] = 1
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            logger.warning("Feed download failed: %s", exc)

    # Owners
    try:
        data = _download_blob(OWNERS_BLOB)
        (repo_root / ".portal-owners.json").write_bytes(data)
        counts["owners"] = 1
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            logger.warning("Owners download failed: %s", exc)

    # Projects
    try:
        names = _list_blobs(PROJECTS_PREFIX)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Projects listing failed: %s", exc)
        return counts

    for name in names:
        rel = name[len(PROJECTS_PREFIX):]
        if not rel:
            continue
        dest = projects_root / rel
        # Basic traversal guard
        try:
            dest.resolve().relative_to(projects_root.resolve())
        except ValueError:
            counts["skipped"] += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(_download_blob(name))
            counts["projects_files"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Blob %s download failed: %s", name, exc)
            counts["skipped"] += 1

    logger.info("Blob sync-down complete: %s", counts)
    return counts


def upload_feed(feed_path: pathlib.Path) -> None:
    if not BLOB_ENABLED or not feed_path.is_file():
        return
    try:
        _upload_blob(FEED_BLOB, feed_path.read_bytes(), "application/json; charset=utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Feed upload failed: %s", exc)


def upload_owners(owners_path: pathlib.Path) -> None:
    if not BLOB_ENABLED or not owners_path.is_file():
        return
    try:
        _upload_blob(OWNERS_BLOB, owners_path.read_bytes(),
                     "application/json; charset=utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Owners upload failed: %s", exc)


def upload_project(project_dir: pathlib.Path, slug: str) -> int:
    """Upload every file under project_dir to projects/{slug}/... in blob."""
    if not BLOB_ENABLED or not project_dir.is_dir():
        return 0
    uploaded = 0
    for p in project_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(project_dir).as_posix()
        blob_name = f"{PROJECTS_PREFIX}{slug}/{rel}"
        try:
            _upload_blob(blob_name, p.read_bytes(), _content_type_for(p.name))
            uploaded += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Upload failed for %s: %s", blob_name, exc)
    logger.info("Uploaded %d file(s) for project %s", uploaded, slug)
    return uploaded
