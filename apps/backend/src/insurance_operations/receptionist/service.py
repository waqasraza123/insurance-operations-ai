from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.actors import ActorContext
from insurance_operations.database.models.operations import AuditActorType, AuditEvent
from insurance_operations.database.models.receptionist import (
    AgencyReceptionistSettings,
)
from insurance_operations.errors import ApiError
from insurance_operations.receptionist.schemas import (
    ReceptionistSettingsInput,
    ReceptionistSettingsResponse,
)


class ReceptionistSettingsService:
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, *, actor: ActorContext) -> ReceptionistSettingsResponse:
        with self._session_factory() as session:
            settings = session.scalar(
                select(AgencyReceptionistSettings).where(
                    AgencyReceptionistSettings.agency_id == actor.agency_id
                )
            )
            if settings is None:
                raise ApiError(
                    status_code=404,
                    code="RECEPTIONIST_SETTINGS_NOT_FOUND",
                    message="Receptionist settings have not been configured",
                )
            return settings_response(settings)

    def replace(
        self,
        *,
        actor: ActorContext,
        request: ReceptionistSettingsInput,
        correlation_id: UUID,
    ) -> ReceptionistSettingsResponse:
        now = datetime.now(UTC)
        with self._session_factory() as session, session.begin():
            settings = session.scalar(
                select(AgencyReceptionistSettings)
                .where(AgencyReceptionistSettings.agency_id == actor.agency_id)
                .with_for_update()
            )
            event_type: str
            changed_fields: list[str]
            if settings is None:
                if request.expected_row_version != 0:
                    raise settings_conflict(current_row_version=0)
                settings = AgencyReceptionistSettings(
                    agency_id=actor.agency_id,
                    created_by=actor.app_user_id,
                    updated_by=actor.app_user_id,
                    **settings_values(request),
                )
                session.add(settings)
                event_type = "AGENCY_RECEPTIONIST_SETTINGS_CREATED"
                changed_fields = sorted(settings_values(request))
            else:
                if settings.row_version != request.expected_row_version:
                    raise settings_conflict(current_row_version=settings.row_version)
                changed_fields = changed_setting_fields(settings, request)
                for field_name, value in settings_values(request).items():
                    setattr(settings, field_name, value)
                settings.updated_by = actor.app_user_id
                event_type = "AGENCY_RECEPTIONIST_SETTINGS_UPDATED"

            session.flush()
            session.refresh(settings)
            session.add(
                AuditEvent(
                    agency_id=actor.agency_id,
                    actor_type=AuditActorType.STAFF.value,
                    actor_user_id=actor.app_user_id,
                    event_type=event_type,
                    occurred_at=now,
                    summary="Agency receptionist settings changed",
                    details={
                        "receptionist_settings_id": str(settings.id),
                        "changed_fields": changed_fields,
                        "row_version": settings.row_version,
                    },
                    correlation_id=correlation_id,
                    event_version=1,
                )
            )
            return settings_response(settings)


def settings_values(request: ReceptionistSettingsInput) -> dict[str, object]:
    return {
        "public_name": request.public_name,
        "greeting": request.greeting,
        "office_hours": request.office_hours,
        "contact_email": (
            str(request.contact_email) if request.contact_email is not None else None
        ),
        "contact_phone": request.contact_phone,
        "supported_insurance_categories": request.supported_insurance_categories,
        "escalation_message": request.escalation_message,
    }


def changed_setting_fields(
    settings: AgencyReceptionistSettings,
    request: ReceptionistSettingsInput,
) -> list[str]:
    return sorted(
        field_name
        for field_name, value in settings_values(request).items()
        if getattr(settings, field_name) != value
    )


def settings_response(
    settings: AgencyReceptionistSettings,
) -> ReceptionistSettingsResponse:
    return ReceptionistSettingsResponse(
        id=settings.id,
        agency_id=settings.agency_id,
        public_name=settings.public_name,
        greeting=settings.greeting,
        office_hours=settings.office_hours,
        contact_email=settings.contact_email,
        contact_phone=settings.contact_phone,
        supported_insurance_categories=settings.supported_insurance_categories,
        escalation_message=settings.escalation_message,
        row_version=settings.row_version,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


def settings_conflict(*, current_row_version: int) -> ApiError:
    return ApiError(
        status_code=409,
        code="RECEPTIONIST_SETTINGS_VERSION_CONFLICT",
        message="Receptionist settings were changed by another request",
        details={"current_row_version": current_row_version},
    )
