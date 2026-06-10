import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent.parent


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list_env(name: str, default: str = "*") -> List[str]:
    value = os.environ.get(name, default)
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or ["*"]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.environ.get("WISE_APP_NAME", "Wise MLOps Agent")
    app_version: str = os.environ.get("WISE_APP_VERSION", "1.0")
    environment: str = os.environ.get("WISE_ENV", "local")
    db_path: Path = Path(os.environ.get("WISE_AGENT_DB_PATH", BASE_DIR / "data" / "agent.db"))
    db_backend: str = os.environ.get("WISE_DB_BACKEND", "sqlite").strip().lower()
    cf_api_base: str = os.environ.get("CLOUDFLARE_API_BASE", "https://api.cloudflare.com/client/v4")
    cf_account_id: str = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    cf_d1_database_id: str = os.environ.get("CLOUDFLARE_D1_DATABASE_ID", "")
    cf_api_token: str = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    auth_enabled: bool = _bool_env("WISE_AUTH_ENABLED", False)
    auth_secret: str = os.environ.get("WISE_AUTH_SECRET", "local-dev-secret")
    admin_username: str = os.environ.get("WISE_ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("WISE_ADMIN_PASSWORD", "change-me")
    session_ttl_seconds: int = int(os.environ.get("WISE_SESSION_TTL_SECONDS", "86400"))
    cors_origins: List[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cors_origins", _list_env("WISE_CORS_ORIGINS", "*"))


settings = Settings()
