"""Optional inbound JWT validation + on-behalf-of (OBO) Graph token acquisition.

By default (``API_REQUIRE_JWT_VALIDATION`` unset/false) these dependencies are inert: no bearer
token is required and SharePoint read calls fall back to the app/managed identity. This keeps the
app importable and runnable without any Azure connectivity.

When ``API_REQUIRE_JWT_VALIDATION`` is true the inbound access token is validated (RS256 against
the tenant JWKS). For *delegated* tokens (carrying an ``scp`` claim) an OBO exchange mints a Graph
token so downstream calls are security-trimmed to the signed-in user. App-only tokens (no ``scp``)
return ``None`` so the app identity is used.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from casewright.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


async def get_optional_bearer_token(
    authorization: str | None = Header(default=None),
) -> str | None:
    """Return the raw inbound bearer token, if any (no validation)."""
    return _extract_bearer(authorization)


@lru_cache(maxsize=4)
def _jwks_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys")


def _validate_access_token(token: str, settings: Settings) -> dict[str, Any]:
    tenant_id = settings.graph_tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GRAPH_TENANT_ID must be configured to validate inbound tokens.",
        )
    audiences = settings.auth_audiences
    if not audiences:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No accepted audiences configured (API_AUTH_AUDIENCE / GRAPH_CLIENT_ID).",
        )
    issuers = [
        f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        f"https://sts.windows.net/{tenant_id}/",
    ]
    try:
        signing_key = _jwks_client(tenant_id).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=list(audiences),
            issuer=issuers,
            options={"require": ["exp", "iss", "aud"], "verify_iss": True},
        )
    except jwt.PyJWTError as exc:
        logger.warning("Inbound token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token."
        ) from exc
    return claims


def _is_delegated_token(claims: dict[str, Any]) -> bool:
    return bool(claims.get("scp"))


async def _exchange_graph_token_obo(user_assertion: str, settings: Settings) -> str:
    if not (settings.graph_tenant_id and settings.graph_client_id and settings.graph_client_secret):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OBO requires GRAPH_TENANT_ID, GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET.",
        )
    # Imported lazily so the module imports without azure-identity present at collection time.
    from azure.identity.aio import OnBehalfOfCredential

    credential = OnBehalfOfCredential(
        tenant_id=settings.graph_tenant_id,
        client_id=settings.graph_client_id,
        client_secret=settings.graph_client_secret,
        user_assertion=user_assertion,
    )
    try:
        token = await credential.get_token(settings.api_obo_graph_scope)
    except Exception as exc:  # pragma: no cover - network/identity failure
        logger.warning("OBO token exchange failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not exchange the access token for a Graph token.",
        ) from exc
    finally:
        await credential.close()
    return token.token


async def get_sync_graph_access_token(
    bearer_token: str | None = Depends(get_optional_bearer_token),
    settings: Settings = Depends(get_settings),
) -> str | None:
    """Resolve a delegated Graph token for the current request, or ``None`` for app identity.

    - Validation disabled: passthrough — return the raw token if present, else ``None``.
    - Validation enabled: validate the token; for delegated tokens perform an OBO exchange (when
      enabled) and return the Graph token; for app-only/no token return ``None``.
    """
    if not settings.api_require_jwt_validation:
        return bearer_token

    if not bearer_token:
        return None

    claims = _validate_access_token(bearer_token, settings)
    if not _is_delegated_token(claims):
        return None
    if not settings.api_obo_enabled:
        return None
    return await _exchange_graph_token_obo(bearer_token, settings)
