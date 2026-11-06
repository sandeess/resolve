import os

# Settings are read at import time, so set safe defaults before importing `app`.
os.environ.setdefault("OIDC_ISSUER", "http://idp.test/realms/resolve")
os.environ.setdefault("OIDC_AUDIENCE", "resolve-api")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:dev-only-password@localhost:55432/app"
)
