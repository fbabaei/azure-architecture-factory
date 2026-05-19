"""AAF (Azure Architecture Factory) integration tool adapter.

Callable by the Architect agent to:
  1. POST a BRD payload to the AAF intake API.
  2. Poll for architecture diagram + Bicep scaffold output.
  3. Return the artifact paths/URLs back to the agent context.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

AAF_BASE_URL = os.getenv("AAF_API_BASE_URL", "http://localhost:5501")
AAF_API_KEY = os.getenv("AAF_API_KEY", "")
_POLL_INTERVAL_S = 5
_POLL_TIMEOUT_S = 300


class AAFToolAdapter:
    """HTTP adapter that calls AAF intake API and polls for results."""

    def __init__(
        self,
        base_url: str = AAF_BASE_URL,
        api_key: str = AAF_API_KEY,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-API-Key"] = api_key

    async def submit_brd(
        self,
        project_name: str,
        requirements: str,
        language: str = "python",
        iac: str = "bicep",
    ) -> dict[str, Any]:
        """Submit a BRD to AAF and return the created project metadata."""
        payload = {
            "project_name": project_name,
            "requirements": requirements,
            "language": language,
            "iac": iac,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/brd-intake",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def poll_status(self, project_id: str) -> dict[str, Any]:
        """Poll until the project is complete or the timeout is reached."""
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        async with httpx.AsyncClient(timeout=30.0) as client:
            while time.monotonic() < deadline:
                resp = await client.get(
                    f"{self._base_url}/api/projects/{project_id}/status",
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "unknown")
                if status in {"complete", "failed"}:
                    return data
                await asyncio.sleep(_POLL_INTERVAL_S)
        raise TimeoutError(f"AAF project {project_id} did not complete within {_POLL_TIMEOUT_S}s")

    async def generate_architecture(
        self,
        project_name: str,
        requirements: str,
        language: str = "python",
        iac: str = "bicep",
    ) -> dict[str, Any]:
        """End-to-end: submit BRD, poll, return result with artifact paths."""
        submission = await self.submit_brd(project_name, requirements, language, iac)
        project_id = submission.get("project_id") or submission.get("run_id", "")
        if not project_id:
            raise ValueError(f"AAF submission did not return a project_id: {submission}")
        result = await self.poll_status(project_id)
        logger.info(
            "AAF project %s completed — status=%s artifacts=%s",
            project_id,
            result.get("status"),
            result.get("artifacts", []),
        )
        return result


# ---------------------------------------------------------------------------
# MAF tool function wrapper (called by the Architect agent)
# ---------------------------------------------------------------------------


async def aaf_generate_architecture_tool(
    project_name: str,
    requirements: str,
    language: str = "python",
    iac: str = "bicep",
    base_url: Optional[str] = None,
) -> str:
    """MAF tool function: submit to AAF and return a summary string with artifact locations."""
    adapter = AAFToolAdapter(base_url=base_url or AAF_BASE_URL)
    result = await adapter.generate_architecture(project_name, requirements, language, iac)
    artifacts = result.get("artifacts", [])
    summary = (
        f"Architecture generation complete for '{project_name}'. "
        f"Status: {result.get('status')}. "
        f"Artifacts: {', '.join(str(a) for a in artifacts) if artifacts else 'none listed'}."
    )
    return summary
