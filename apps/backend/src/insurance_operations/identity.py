from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from insurance_operations.database.models.identity import (
    Agency,
    AgencyMembership,
    AppUser,
    AppUserStatus,
    MembershipStatus,
)
from insurance_operations.settings import ApiSettings


class AccessTokenVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: UUID


class AccessTokenVerifier(Protocol):
    def verify(self, access_token: str) -> VerifiedIdentity: ...


class SigningKeyProvider(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> object: ...


class SupabaseAccessTokenVerifier:
    def __init__(
        self,
        settings: ApiSettings,
        *,
        signing_key_provider: SigningKeyProvider | None = None,
    ) -> None:
        self._issuer = str(settings.supabase_auth_issuer).rstrip("/")
        self._audience = settings.supabase_auth_audience
        self._clock_skew_seconds = settings.auth_clock_skew_seconds
        self._signing_key_provider: SigningKeyProvider = (
            signing_key_provider or PyJWKClient(
                str(settings.supabase_auth_jwks_url),
                cache_jwk_set=True,
                lifespan=300,
                timeout=5,
            )
        )

    def verify(self, access_token: str) -> VerifiedIdentity:
        try:
            signing_key = self._signing_key_provider.get_signing_key_from_jwt(
                access_token
            )
            claims = jwt.decode(
                access_token,
                key=getattr(signing_key, "key", signing_key),
                algorithms=["RS256", "ES256"],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._clock_skew_seconds,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
            subject = UUID(str(claims["sub"]))
        except (
            PyJWTError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise AccessTokenVerificationError("access token is invalid") from error

        return VerifiedIdentity(subject=subject)


@dataclass(frozen=True)
class ActorContext:
    app_user_id: UUID
    auth_subject: UUID
    display_name: str
    agency_id: UUID
    agency_name: str
    agency_environment: str


class ActorResolutionError(RuntimeError):
    pass


def resolve_actor(session: Session, identity: VerifiedIdentity) -> ActorContext:
    statement = (
        select(AppUser, AgencyMembership, Agency)
        .join(AgencyMembership, AgencyMembership.app_user_id == AppUser.id)
        .join(Agency, Agency.id == AgencyMembership.agency_id)
        .where(
            AppUser.auth_subject == identity.subject,
            AppUser.status == AppUserStatus.ACTIVE.value,
            AppUser.disabled_at.is_(None),
            AgencyMembership.status == MembershipStatus.ACTIVE.value,
            AgencyMembership.deactivated_at.is_(None),
            Agency.archived_at.is_(None),
        )
    )
    matches = session.execute(statement).all()
    if len(matches) != 1:
        raise ActorResolutionError("active agency membership is required")

    app_user, _membership, agency = matches[0]
    return ActorContext(
        app_user_id=app_user.id,
        auth_subject=app_user.auth_subject,
        display_name=app_user.display_name,
        agency_id=agency.id,
        agency_name=agency.name,
        agency_environment=agency.environment_kind,
    )
