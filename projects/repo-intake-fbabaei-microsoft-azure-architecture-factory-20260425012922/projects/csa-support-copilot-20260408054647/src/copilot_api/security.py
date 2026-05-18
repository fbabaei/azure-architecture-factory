from secrets import compare_digest

from fastapi import Header, HTTPException, status

from .config import load_settings


def _extract_token(authorization: str | None, x_api_key: str | None) -> str:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def require_api_access(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    settings = load_settings()
    if not settings.require_api_key:
        return

    token = _extract_token(authorization=authorization, x_api_key=x_api_key)
    for configured in settings.api_keys:
        if compare_digest(token, configured):
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API credential.",
    )