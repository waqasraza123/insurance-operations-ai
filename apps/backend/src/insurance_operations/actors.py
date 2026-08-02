from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from insurance_operations.database.models.identity import (
    Agency,
    AgencyEnvironment,
    AgencyMembership,
    AppUser,
    AppUserStatus,
    MembershipStatus,
)


@dataclass(frozen=True)
class ActorContext:
    app_user_id: UUID
    display_name: str
    agency_id: UUID
    agency_name: str
    agency_environment: str


class ActorResolutionError(RuntimeError):
    pass


def resolve_development_actor(
    session: Session,
    app_user_id: UUID,
) -> ActorContext:
    statement = (
        select(AppUser, AgencyMembership, Agency)
        .join(AgencyMembership, AgencyMembership.app_user_id == AppUser.id)
        .join(Agency, Agency.id == AgencyMembership.agency_id)
        .where(
            AppUser.id == app_user_id,
            AppUser.status == AppUserStatus.ACTIVE.value,
            AppUser.disabled_at.is_(None),
            AgencyMembership.status == MembershipStatus.ACTIVE.value,
            AgencyMembership.deactivated_at.is_(None),
            Agency.environment_kind == AgencyEnvironment.DEVELOPMENT.value,
            Agency.archived_at.is_(None),
        )
    )
    matches = session.execute(statement).all()
    if len(matches) != 1:
        raise ActorResolutionError("active development membership is required")

    app_user, _membership, agency = matches[0]
    return ActorContext(
        app_user_id=app_user.id,
        display_name=app_user.display_name,
        agency_id=agency.id,
        agency_name=agency.name,
        agency_environment=agency.environment_kind,
    )
