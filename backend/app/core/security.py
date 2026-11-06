"""Verification of OpenID Connect access tokens issued by the identity provider."""

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError


class TokenError(Exception):
    """The bearer token is missing, malformed, expired or not trusted."""


@dataclass(frozen=True)
class TokenClaims:
    """The identity claims Resolve relies on."""

    sub: str
    email: str
    name: str | None
    # None means the token carries no role claim at all (e.g. a client with "full
    # scope" disabled), which must not be read as "has no roles".
    roles: frozenset[str] | None
    client_id: str | None = None


class OidcVerifier:
    """Validates signed JWTs against the issuer's JWKS."""

    def __init__(
        self, *, issuer: str, audience: str, jwks_url: str, algorithms: tuple[str, ...]
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._algorithms = list(algorithms)
        self._jwks = PyJWKClient(jwks_url, cache_keys=True)

    def verify(self, token: str) -> TokenClaims:
        """Decodes `token` and returns its claims.

        Raises:
            TokenError: If the signature, issuer, audience or expiry is invalid,
                or required claims are absent.
        """
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub"]},
            )
        except (InvalidTokenError, PyJWKClientError) as exc:
            raise TokenError(str(exc)) from exc

        email = payload.get("email")
        if not isinstance(email, str) or not email:
            raise TokenError("token has no email claim")
        realm_access = payload.get("realm_access")
        roles = (
            frozenset(realm_access.get("roles", []))
            if isinstance(realm_access, dict)
            else None
        )
        return TokenClaims(
            sub=payload["sub"],
            email=email,
            name=payload.get("name"),
            roles=roles,
            client_id=payload.get("azp"),
        )
