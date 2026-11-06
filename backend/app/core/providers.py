"""Process-wide singletons for external services (storage, model gateway).

Kept outside `app.api` so background workers can use them too. Tests replace
them through FastAPI dependency overrides or by monkeypatching these getters.
"""

from functools import lru_cache

from openai import OpenAI, Timeout

from app.core.config import settings
from app.core.security import OidcVerifier
from app.llm.base import ChatModel, Embedder
from app.llm.cache import CachingEmbedder
from app.llm.gateway import GatewayChat, GatewayEmbedder
from app.storage.base import Storage
from app.storage.local import LocalStorage


@lru_cache
def get_verifier() -> OidcVerifier:
    return OidcVerifier(
        issuer=settings.OIDC_ISSUER,
        audience=settings.OIDC_AUDIENCE,
        jwks_url=settings.oidc_jwks_url,
        algorithms=("RS256",),
    )


@lru_cache
def get_storage() -> Storage:
    return LocalStorage(settings.STORAGE_ROOT)


@lru_cache
def _gateway_client() -> OpenAI:
    return OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        max_retries=settings.LLM_MAX_RETRIES,
        timeout=Timeout(settings.LLM_TIMEOUT_SECONDS, connect=10.0),
    )


@lru_cache
def get_embedder() -> Embedder:
    return CachingEmbedder(
        GatewayEmbedder(_gateway_client(), settings.EMBED_MODEL),
        maxsize=settings.EMBED_CACHE_SIZE,
    )


@lru_cache
def get_chat_model() -> ChatModel:
    return GatewayChat(_gateway_client(), settings.CHAT_MODEL)
