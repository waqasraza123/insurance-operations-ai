from collections.abc import Mapping
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request, Response, status
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from insurance_operations.errors import ApiError
from insurance_operations.telephony.contracts import (
    TelephonyAdapter,
    TelephonyAdapterError,
)
from insurance_operations.telephony.providers.twilio import (
    TwilioTelephonyAdapter,
)
from insurance_operations.telephony.schemas import (
    InboundCallActionResponse,
    InboundCallReceiveInput,
)
from insurance_operations.telephony.service import TelephonyService
from insurance_operations.telephony.settings import TelephonyProviderSettings


class TelephonyIngressService:
    def __init__(
        self,
        *,
        adapter: TelephonyAdapter,
        telephony_service: TelephonyService,
    ) -> None:
        self._adapter = adapter
        self._telephony_service = telephony_service

    def receive(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        correlation_id: UUID,
    ) -> InboundCallActionResponse:
        try:
            verified_call = self._adapter.verify_inbound_webhook(
                headers=headers,
                body=body,
            )
        except TelephonyAdapterError as error:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="TELEPHONY_WEBHOOK_REJECTED",
                message="The telephony webhook could not be verified",
            ) from error

        normalized_request = InboundCallReceiveInput(
            adapter_name=verified_call.adapter_name,
            adapter_version=verified_call.adapter_version,
            source_call_reference=verified_call.source_call_reference,
            called_number_e164=verified_call.called_number_e164,
            caller_number_e164=verified_call.caller_number_e164,
            occurred_at=verified_call.occurred_at,
        )

        return self._telephony_service.receive_provider_call(
            request=normalized_request,
            correlation_id=correlation_id,
        )

    def close(self) -> None:
        self._adapter.close()


def create_twilio_ingress_router(
    ingress_service: TelephonyIngressService,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/providers/twilio/inbound",
        status_code=status.HTTP_204_NO_CONTENT,
        include_in_schema=False,
    )
    async def receive_twilio_inbound_call(request: Request) -> Response:
        body = await request.body()

        ingress_service.receive(
            headers=request.headers,
            body=body,
            correlation_id=UUID(request.state.correlation_id),
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def configure_twilio_ingress(
    application: FastAPI,
    settings: TelephonyProviderSettings,
    database_engine: Engine,
) -> TelephonyIngressService | None:
    if not settings.telephony_provider_enabled:
        return None

    account_sid = required_setting(
        settings.twilio_account_sid,
        "TWILIO_ACCOUNT_SID",
    )
    webhook_url = required_setting(
        settings.twilio_inbound_webhook_url,
        "TWILIO_INBOUND_WEBHOOK_URL",
    )

    if settings.twilio_auth_token is None:
        raise RuntimeError("TWILIO_AUTH_TOKEN is unavailable")

    session_factory = sessionmaker(
        bind=database_engine,
        class_=Session,
        expire_on_commit=False,
    )

    adapter = TwilioTelephonyAdapter(
        account_sid=account_sid,
        auth_token=settings.twilio_auth_token.get_secret_value(),
        inbound_webhook_url=webhook_url,
    )

    ingress_service = TelephonyIngressService(
        adapter=adapter,
        telephony_service=TelephonyService(
            session_factory=session_factory,
        ),
    )

    application.include_router(create_twilio_ingress_router(ingress_service))
    application.state.telephony_ingress_service = ingress_service

    return ingress_service


def required_setting(value: str | None, name: str) -> str:
    if value is None:
        raise RuntimeError(f"{name} is unavailable")
    return value
