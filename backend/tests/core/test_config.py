from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(
        DATABASE_URL="postgresql://u:p@localhost/db",  # type: ignore[arg-type]  # validated from str
        OIDC_ISSUER="http://idp.test/realms/resolve",
        OIDC_AUDIENCE="resolve-api",
        **overrides,  # type: ignore[arg-type]
    )


def test_development_allows_every_local_address_the_app_can_be_opened_at() -> None:
    origins = _settings(FASTAPI_ENV="development").cors_origins
    for host in ("localhost", "127.0.0.1"):
        assert f"http://{host}:5173" in origins  # the Vite dev server
        assert f"http://{host}:8000" in origins  # the build served by the API
    assert len(origins) == len(set(origins))


def test_outside_development_only_the_configured_frontend_is_allowed() -> None:
    settings = _settings(FRONTEND_HOST="https://resolve.example.com", FASTAPI_ENV=None)
    assert settings.cors_origins == ["https://resolve.example.com"]
