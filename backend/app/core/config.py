from pathlib import Path
from typing import Literal

from pydantic import HttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from the environment and the top-level `.env`."""

    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    PROJECT_NAME: str = "Resolve"
    API_V1_STR: str = "/api/v1"
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None
    SENTRY_DSN: HttpUrl | None = None

    DATABASE_URL: PostgresDsn

    # OpenID Connect (Keycloak). Tokens are verified against the issuer's JWKS.
    OIDC_ISSUER: str
    OIDC_AUDIENCE: str
    OIDC_JWKS_URL: str | None = None
    OIDC_ADMIN_ROLE: str = "resolve-admin"

    # Public URL of the MCP server, advertised to clients in OAuth discovery metadata.
    MCP_PUBLIC_URL: str = "http://localhost:8010"

    # LLM gateway (LiteLLM proxy, OpenAI-compatible). Models are proxy aliases.
    LLM_BASE_URL: str = "http://localhost:4000/v1"
    LLM_API_KEY: str = "sk-resolve-dev"
    EMBED_MODEL: str = "embed"
    CHAT_MODEL: str = "chat-fast"
    # Fail fast instead of hanging on a slow link; one retry at most.
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 1

    # Per-process caches: Ask answers (entries, seconds) and query embeddings (entries).
    ASK_CACHE_SIZE: int = 256
    ASK_CACHE_TTL_SECONDS: float = 3600.0
    EMBED_CACHE_SIZE: int = 1024

    # File storage (local volume backend).
    STORAGE_ROOT: Path = Path("./data/files")
    MAX_UPLOAD_MB: int = 50

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str | PostgresDsn) -> str:
        database_url = str(value)
        for scheme in ("postgres://", "postgresql://"):
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    @property
    def cors_origins(self) -> list[str]:
        """Browser origins allowed to call the API.

        In development the same page may be opened as `localhost` or `127.0.0.1`,
        and as the Vite server (5173) or the API-served build (8000).
        """
        origins = [self.FRONTEND_HOST]
        if self.FASTAPI_ENV == "development":
            for host in ("localhost", "127.0.0.1"):
                origins += [f"http://{host}:5173", f"http://{host}:8000"]
        return list(dict.fromkeys(origins))

    @property
    def queue_dsn(self) -> str:
        """Plain libpq DSN for the Procrastinate job queue."""
        return str(self.DATABASE_URL).replace(
            "postgresql+psycopg://", "postgresql://", 1
        )

    @property
    def oidc_jwks_url(self) -> str:
        """JWKS endpoint, defaulting to the standard Keycloak location."""
        return (
            self.OIDC_JWKS_URL
            or f"{self.OIDC_ISSUER.rstrip('/')}/protocol/openid-connect/certs"
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


settings = Settings()  # type: ignore # ty: ignore[unused-ignore-comment]
