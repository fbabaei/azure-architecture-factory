import os
from dataclasses import dataclass


def _parse_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_version: str
    require_api_key: bool
    api_keys: list[str]
    allow_origins: list[str]
    rate_limit_per_minute: int


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "CSA Support Copilot API"),
        app_env=os.getenv("APP_ENV", "dev"),
        app_version=os.getenv("APP_VERSION", "1.0.0"),
        require_api_key=_parse_bool("REQUIRE_API_KEY", True),
        api_keys=_parse_list("CSA_API_KEYS", []),
        allow_origins=_parse_list(
            "ALLOWED_ORIGINS",
            ["http://localhost:5501", "http://127.0.0.1:5501"],
        ),
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "30")),
    )