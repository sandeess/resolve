import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.security import OidcVerifier, TokenError

ISSUER = "http://idp.test/realms/resolve"
AUDIENCE = "resolve-api"


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def verifier(private_key: rsa.RSAPrivateKey) -> OidcVerifier:
    verifier = OidcVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url="http://idp.test/certs",
        algorithms=("RS256",),
    )
    signing_key = MagicMock()
    signing_key.key = private_key.public_key()
    verifier._jwks = MagicMock()
    verifier._jwks.get_signing_key_from_jwt.return_value = signing_key
    return verifier


def _token(key: rsa.RSAPrivateKey, **overrides: object) -> str:
    claims: dict[str, object] = {
        "sub": "user-1",
        "email": "lead@example.com",
        "name": "Lee Lead",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 300,
        "realm_access": {"roles": ["resolve-admin"]},
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def test_valid_token(verifier: OidcVerifier, private_key: rsa.RSAPrivateKey) -> None:
    claims = verifier.verify(_token(private_key))
    assert claims.sub == "user-1"
    assert claims.email == "lead@example.com"
    assert claims.roles == frozenset({"resolve-admin"})


@pytest.mark.parametrize(
    "override",
    [
        {"exp": int(time.time()) - 10},
        {"aud": "someone-else"},
        {"iss": "http://evil.test"},
        {"email": None},
    ],
)
def test_rejects_bad_tokens(
    verifier: OidcVerifier, private_key: rsa.RSAPrivateKey, override: dict[str, object]
) -> None:
    with pytest.raises(TokenError):
        verifier.verify(_token(private_key, **override))


def test_rejects_wrong_signing_key(verifier: OidcVerifier) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(TokenError):
        verifier.verify(_token(other))


def test_token_without_realm_access_has_unknown_roles_not_empty_roles(
    verifier: OidcVerifier, private_key: rsa.RSAPrivateKey
) -> None:
    claims = verifier.verify(_token(private_key, realm_access=None))
    assert claims.roles is None
    assert (
        verifier.verify(_token(private_key, realm_access={"roles": []})).roles
        == frozenset()
    )
