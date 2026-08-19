from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.actors import (
    ActorContext,
    ActorResolutionError,
    resolve_development_actor,
)
from insurance_operations.database.models.telephony import InboundCallStatus
from insurance_operations.demo_security import require_demo_admin_token
from insurance_operations.errors import ApiError
from insurance_operations.settings import ApiSettings, RuntimeEnvironment
from insurance_operations.telephony.schemas import (
    CallPolicyInput,
    CallPolicyResponse,
    InboundCallActionResponse,
    InboundCallEventInput,
    InboundCallLinkLeadInput,
    InboundCallListResponse,
    InboundCallReceiveInput,
    InboundCallResponse,
    InboundNumberCreateInput,
    InboundNumberResponse,
    InboundNumberStatusInput,
)
from insurance_operations.telephony.service import TelephonyService


def create_development_telephony_router(
    *,
    settings: ApiSettings,
    session_factory: sessionmaker[Session],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/development")
    service = TelephonyService(session_factory=session_factory)

    def development_actor(
        demo_admin_token: Annotated[
            str | None,
            Header(alias="X-Demo-Admin-Token"),
        ] = None,
    ) -> ActorContext:
        require_demo_admin_token(settings, demo_admin_token)
        if (
            settings.app_environment is not RuntimeEnvironment.DEVELOPMENT
            or settings.development_actor_user_id is None
        ):
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="DEVELOPMENT_CONTEXT_NOT_FOUND",
                message="The development context is unavailable",
            )

        try:
            with session_factory() as session:
                return resolve_development_actor(
                    session,
                    settings.development_actor_user_id,
                )
        except ActorResolutionError as error:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="DEVELOPMENT_CONTEXT_NOT_FOUND",
                message="The development context is unavailable",
            ) from error

    ActorDependency = Annotated[
        ActorContext,
        Depends(development_actor),
    ]

    @router.get(
        "/call-policy",
        response_model=CallPolicyResponse,
    )
    def get_call_policy(actor: ActorDependency) -> CallPolicyResponse:
        return service.get_policy(actor=actor)

    @router.put(
        "/call-policy",
        response_model=CallPolicyResponse,
    )
    def replace_call_policy(
        request: Request,
        policy_input: CallPolicyInput,
        actor: ActorDependency,
    ) -> CallPolicyResponse:
        return service.replace_policy(
            actor=actor,
            request=policy_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.get(
        "/inbound-numbers",
        response_model=list[InboundNumberResponse],
    )
    def list_inbound_numbers(
        actor: ActorDependency,
    ) -> list[InboundNumberResponse]:
        return service.list_numbers(actor=actor)

    @router.post(
        "/inbound-numbers",
        response_model=InboundNumberResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_inbound_number(
        request: Request,
        number_input: InboundNumberCreateInput,
        actor: ActorDependency,
    ) -> InboundNumberResponse:
        return service.create_number(
            actor=actor,
            request=number_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.patch(
        "/inbound-numbers/{number_id}/status",
        response_model=InboundNumberResponse,
    )
    def set_inbound_number_status(
        number_id: UUID,
        request: Request,
        status_input: InboundNumberStatusInput,
        actor: ActorDependency,
    ) -> InboundNumberResponse:
        return service.set_number_status(
            actor=actor,
            number_id=number_id,
            request=status_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.post(
        "/inbound-calls",
        response_model=InboundCallActionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def receive_inbound_call(
        request: Request,
        call_input: InboundCallReceiveInput,
        actor: ActorDependency,
    ) -> InboundCallActionResponse:
        return service.receive_call(
            actor=actor,
            request=call_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.get(
        "/inbound-calls",
        response_model=InboundCallListResponse,
    )
    def list_inbound_calls(
        actor: ActorDependency,
        call_status: Annotated[
            InboundCallStatus | None,
            Query(alias="status"),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> InboundCallListResponse:
        return service.list_calls(
            actor=actor,
            status=call_status,
            limit=limit,
            offset=offset,
        )

    @router.get(
        "/inbound-calls/{call_id}",
        response_model=InboundCallResponse,
    )
    def get_inbound_call(
        call_id: UUID,
        actor: ActorDependency,
    ) -> InboundCallResponse:
        return service.get_call(
            actor=actor,
            call_id=call_id,
        )

    @router.post(
        "/inbound-calls/{call_id}/events",
        response_model=InboundCallActionResponse,
    )
    def apply_inbound_call_event(
        call_id: UUID,
        request: Request,
        event_input: InboundCallEventInput,
        actor: ActorDependency,
    ) -> InboundCallActionResponse:
        return service.apply_event(
            actor=actor,
            call_id=call_id,
            request=event_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.post(
        "/inbound-calls/{call_id}/lead",
        response_model=InboundCallActionResponse,
    )
    def link_inbound_call_lead(
        call_id: UUID,
        request: Request,
        link_input: InboundCallLinkLeadInput,
        actor: ActorDependency,
    ) -> InboundCallActionResponse:
        return service.link_lead(
            actor=actor,
            call_id=call_id,
            request=link_input,
            correlation_id=UUID(request.state.correlation_id),
        )

    return router
