from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from insurance_operations.identity import (
    AccessTokenVerificationError,
    SupabaseAccessTokenVerifier,
)
from insurance_operations.settings import (
    ApiSettings,
    DatabaseSslMode,
    RuntimeEnvironment,
)


class StaticSigningKeyProvider:
    def __init__(self, public_key: object) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> object:
        del token
        return self._public_key


def api_settings() -> ApiSettings:
    return ApiSettings(
        app_environment=RuntimeEnvironment.TEST,
        api_host="127.0.0.1",
        api_port=8000,
        database_url="postgresql://user:password@localhost/development",
        test_database_url="postgresql://user:password@localhost/test",
        database_ssl_mode=DatabaseSslMode.DISABLE,
        supabase_auth_issuer="https://example.supabase.co/auth/v1",
        supabase_auth_jwks_url=(
            "https://example.supabase.co/auth/v1/.well-known/jwks.json"
        ),
    )


def signed_token(*, audience: str = "authenticated") -> tuple[str, object, str]:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    now = datetime.now(UTC)
    subject = str(uuid4())
    token = jwt.encode(
        {
            "iss": "https://example.supabase.co/auth/v1",
            "aud": audience,
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    return token, private_key.public_key(), subject


def test_supabase_token_verifier_accepts_approved_claims() -> None:
    token, public_key, subject = signed_token()
    verifier = SupabaseAccessTokenVerifier(
        api_settings(),
        signing_key_provider=StaticSigningKeyProvider(public_key),
    )

    identity = verifier.verify(token)

    assert str(identity.subject) == subject


def test_supabase_token_verifier_rejects_wrong_audience() -> None:
    token, public_key, _subject = signed_token(audience="wrong-audience")
    verifier = SupabaseAccessTokenVerifier(
        api_settings(),
        signing_key_provider=StaticSigningKeyProvider(public_key),
    )

    with pytest.raises(AccessTokenVerificationError):
        verifier.verify(token)
