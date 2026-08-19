import secrets
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, Header, Request, Response, status
from pydantic import SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from twilio.twiml.voice_response import VoiceResponse

from insurance_operations.database.models.telephony import AgencyInboundNumber
from insurance_operations.errors import ApiError
from insurance_operations.telephony.contracts import (
    TelephonyAdapter,
    TelephonyAdapterError,
)
from insurance_operations.telephony.phone_schemas import (
    PhoneConsentInput,
    PhoneConsentResponse,
    PhoneFaqLookupInput,
    PhoneFaqLookupResponse,
    PhoneHandoffInput,
    PhoneHandoffResponse,
    PhoneIntakeConfirmationInput,
    PhoneIntakeConfirmationResponse,
)
from insurance_operations.telephony.phone_service import PhoneReceptionistService
from insurance_operations.telephony.providers.elevenlabs import (
    ElevenLabsPhoneProvider,
    PhoneCallRegistration,
)
from insurance_operations.telephony.providers.twilio import (
    TwilioTelephonyAdapter,
)
from insurance_operations.telephony.schemas import (
    CallAction,
    InboundCallActionResponse,
    InboundCallEventInput,
    InboundCallEventType,
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
        phone_provider: ElevenLabsPhoneProvider | None = None,
        phone_service: PhoneReceptionistService | None = None,
        phone_tool_secret: str | None = None,
        maximum_duration_seconds: int = 180,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._adapter = adapter
        self._telephony_service = telephony_service
        self._phone_provider = phone_provider
        self._phone_service = phone_service
        self._phone_tool_secret = phone_tool_secret
        self._maximum_duration_seconds = maximum_duration_seconds
        self._session_factory = session_factory
        self._registration_twiml: dict[UUID, str] = {}

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

    def receive_twiml(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        correlation_id: UUID,
    ) -> str:
        if self._phone_provider is None:
            raise RuntimeError("phone conversation provider is unavailable")
        action = self.receive(
            headers=headers,
            body=body,
            correlation_id=correlation_id,
        )
        call = action.call
        if action.action not in {CallAction.ANSWER_AI, CallAction.CONTINUE_AI}:
            return safe_twiml("The phone receptionist is currently unavailable.")
        cached_twiml = self._registration_twiml.get(call.id)
        if action.replayed and cached_twiml is not None:
            return cached_twiml
        if call.caller_number_e164 is None:
            self._mark_registration_failed(call.id, correlation_id)
            return safe_twiml("The phone receptionist could not accept this call.")
        try:
            twiml = self._phone_provider.register_inbound_call(
                PhoneCallRegistration(
                    inbound_call_id=str(call.id),
                    from_number=call.caller_number_e164,
                    to_number=self._called_number(call.inbound_number_id),
                    maximum_duration_seconds=self._maximum_duration_seconds,
                )
            )
            self._cache_registration_twiml(call.id, twiml)
            return twiml
        except TelephonyAdapterError:
            self._mark_registration_failed(call.id, correlation_id)
            return safe_twiml("The phone receptionist is temporarily unavailable.")

    def verify_phone_tool(self, authorization: str | None) -> None:
        if self._phone_tool_secret is None or authorization is None:
            raise phone_tool_rejected()
        scheme, separator, supplied = authorization.partition(" ")
        if (
            not separator
            or scheme.casefold() != "bearer"
            or not secrets.compare_digest(supplied, self._phone_tool_secret)
        ):
            raise phone_tool_rejected()

    def accept_phone_consent(
        self,
        *,
        request: PhoneConsentInput,
        correlation_id: UUID,
    ) -> PhoneConsentResponse:
        return self._require_phone_service().accept_consent(
            request=request,
            correlation_id=correlation_id,
        )

    def lookup_phone_faq(
        self,
        *,
        request: PhoneFaqLookupInput,
        correlation_id: UUID,
    ) -> PhoneFaqLookupResponse:
        return self._require_phone_service().lookup_faq(
            request=request,
            correlation_id=correlation_id,
        )

    def confirm_phone_intake(
        self,
        *,
        request: PhoneIntakeConfirmationInput,
        correlation_id: UUID,
    ) -> PhoneIntakeConfirmationResponse:
        return self._require_phone_service().confirm_intake(
            request=request,
            correlation_id=correlation_id,
        )

    def request_phone_handoff(
        self,
        *,
        request: PhoneHandoffInput,
        correlation_id: UUID,
    ) -> PhoneHandoffResponse:
        return self._require_phone_service().request_handoff(
            request=request,
            correlation_id=correlation_id,
        )

    def receive_post_call(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        correlation_id: UUID,
    ) -> None:
        if self._phone_provider is None:
            raise RuntimeError("phone conversation provider is unavailable")
        try:
            payload = self._phone_provider.verify_post_call_webhook(
                headers=headers,
                body=body,
            )
        except TelephonyAdapterError as error:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PHONE_PROVIDER_WEBHOOK_REJECTED",
                message="The phone provider webhook could not be verified",
            ) from error
        self._require_phone_service().finalize_post_call(
            payload=payload,
            correlation_id=correlation_id,
        )

    def receive_transfer_result(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        correlation_id: UUID,
    ) -> PhoneHandoffResponse:
        try:
            result = self._adapter.verify_transfer_callback(
                headers=headers,
                body=body,
            )
        except TelephonyAdapterError as error:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="TELEPHONY_WEBHOOK_REJECTED",
                message="The telephony webhook could not be verified",
            ) from error
        return self._require_phone_service().apply_transfer_result(
            result=result,
            correlation_id=correlation_id,
        )

    def _called_number(self, inbound_number_id: UUID) -> str:
        if self._session_factory is None:
            raise RuntimeError("phone database session is unavailable")
        with self._session_factory() as session:
            number = session.get(AgencyInboundNumber, inbound_number_id)
            if number is None:
                raise RuntimeError("inbound number was not persisted")
            return number.phone_number_e164

    def _mark_registration_failed(
        self,
        call_id: UUID,
        correlation_id: UUID,
    ) -> None:
        self._telephony_service.apply_provider_event(
            call_id=call_id,
            request=InboundCallEventInput(
                event_key="phone-provider-registration-failed",
                event_type=InboundCallEventType.PROVIDER_FAILED,
                occurred_at=datetime.now(UTC),
                failure_code="PHONE_PROVIDER_REGISTRATION_FAILED",
            ),
            correlation_id=correlation_id,
        )

    def _cache_registration_twiml(self, call_id: UUID, twiml: str) -> None:
        self._registration_twiml[call_id] = twiml
        if len(self._registration_twiml) > 100:
            oldest_call_id = next(iter(self._registration_twiml))
            self._registration_twiml.pop(oldest_call_id, None)

    def _require_phone_service(self) -> PhoneReceptionistService:
        if self._phone_service is None:
            raise RuntimeError("phone receptionist service is unavailable")
        return self._phone_service

    def close(self) -> None:
        self._adapter.close()


def create_twilio_ingress_router(
    ingress_service: TelephonyIngressService,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/providers/twilio/inbound",
        status_code=status.HTTP_200_OK,
        include_in_schema=False,
    )
    async def receive_twilio_inbound_call(request: Request) -> Response:
        body = await request.body()

        try:
            twiml = ingress_service.receive_twiml(
                headers=request.headers,
                body=body,
                correlation_id=UUID(request.state.correlation_id),
            )
        except ApiError as error:
            if error.status_code == status.HTTP_403_FORBIDDEN:
                raise
            twiml = safe_twiml("The phone receptionist is currently unavailable.")
        return Response(content=twiml, media_type="application/xml")

    @router.post(
        "/api/v1/providers/twilio/transfer-result",
        include_in_schema=False,
    )
    async def receive_twilio_transfer_result(request: Request) -> Response:
        body = await request.body()
        result = ingress_service.receive_transfer_result(
            headers=request.headers,
            body=body,
            correlation_id=UUID(request.state.correlation_id),
        )
        if result.action is CallAction.COLLECT_CALLBACK:
            return Response(
                content=safe_twiml(
                    result.message or "The agency will follow up with you."
                ),
                media_type="application/xml",
            )
        return Response(content=str(VoiceResponse()), media_type="application/xml")

    @router.post(
        "/api/v1/providers/elevenlabs/tools/phone-consent",
        response_model=PhoneConsentResponse,
        include_in_schema=False,
    )
    def accept_phone_consent(
        request: Request,
        input_data: PhoneConsentInput,
        authorization: Annotated[str | None, Header()] = None,
    ) -> PhoneConsentResponse:
        ingress_service.verify_phone_tool(authorization)
        return ingress_service.accept_phone_consent(
            request=input_data,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.post(
        "/api/v1/providers/elevenlabs/tools/approved-faq",
        response_model=PhoneFaqLookupResponse,
        include_in_schema=False,
    )
    def lookup_phone_faq(
        request: Request,
        input_data: PhoneFaqLookupInput,
        authorization: Annotated[str | None, Header()] = None,
    ) -> PhoneFaqLookupResponse:
        ingress_service.verify_phone_tool(authorization)
        return ingress_service.lookup_phone_faq(
            request=input_data,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.post(
        "/api/v1/providers/elevenlabs/tools/confirm-intake",
        response_model=PhoneIntakeConfirmationResponse,
        include_in_schema=False,
    )
    def confirm_phone_intake(
        request: Request,
        input_data: PhoneIntakeConfirmationInput,
        authorization: Annotated[str | None, Header()] = None,
    ) -> PhoneIntakeConfirmationResponse:
        ingress_service.verify_phone_tool(authorization)
        return ingress_service.confirm_phone_intake(
            request=input_data,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.post(
        "/api/v1/providers/elevenlabs/tools/request-handoff",
        response_model=PhoneHandoffResponse,
        include_in_schema=False,
    )
    def request_phone_handoff(
        request: Request,
        input_data: PhoneHandoffInput,
        authorization: Annotated[str | None, Header()] = None,
    ) -> PhoneHandoffResponse:
        ingress_service.verify_phone_tool(authorization)
        return ingress_service.request_phone_handoff(
            request=input_data,
            correlation_id=UUID(request.state.correlation_id),
        )

    @router.post(
        "/api/v1/providers/elevenlabs/post-call",
        status_code=status.HTTP_200_OK,
        include_in_schema=False,
    )
    async def receive_elevenlabs_post_call(request: Request) -> Response:
        body = await request.body()
        ingress_service.receive_post_call(
            headers=request.headers,
            body=body,
            correlation_id=UUID(request.state.correlation_id),
        )
        return Response(status_code=status.HTTP_200_OK)

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
    transfer_callback_url = required_setting(
        settings.twilio_transfer_callback_url,
        "TWILIO_TRANSFER_CALLBACK_URL",
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
        transfer_callback_url=transfer_callback_url,
    )

    telephony_service = TelephonyService(session_factory=session_factory)
    phone_provider = ElevenLabsPhoneProvider(
        api_key=required_secret(settings.elevenlabs_api_key, "ELEVENLABS_API_KEY"),
        agent_id=required_setting(
            settings.elevenlabs_phone_agent_id,
            "ELEVENLABS_PHONE_AGENT_ID",
        ),
        post_call_webhook_secret=required_secret(
            settings.elevenlabs_post_call_webhook_secret,
            "ELEVENLABS_POST_CALL_WEBHOOK_SECRET",
        ),
    )
    if settings.development_actor_user_id is None:
        raise RuntimeError("DEVELOPMENT_ACTOR_USER_ID is unavailable")
    phone_service = PhoneReceptionistService(
        session_factory=session_factory,
        telephony_service=telephony_service,
        telephony_adapter=adapter,
        development_actor_user_id=settings.development_actor_user_id,
        maximum_duration_seconds=settings.phone_max_duration_seconds,
        confirmation_window_minutes=settings.phone_confirmation_window_minutes,
    )

    ingress_service = TelephonyIngressService(
        adapter=adapter,
        telephony_service=telephony_service,
        phone_provider=phone_provider,
        phone_service=phone_service,
        phone_tool_secret=required_secret(
            settings.elevenlabs_phone_tool_secret,
            "ELEVENLABS_PHONE_TOOL_SECRET",
        ),
        maximum_duration_seconds=settings.phone_max_duration_seconds,
        session_factory=session_factory,
    )

    application.include_router(create_twilio_ingress_router(ingress_service))
    application.state.telephony_ingress_service = ingress_service

    return ingress_service


def required_setting(value: str | None, name: str) -> str:
    if value is None:
        raise RuntimeError(f"{name} is unavailable")
    return value


def required_secret(value: SecretStr | None, name: str) -> str:
    if value is None or not value.get_secret_value():
        raise RuntimeError(f"{name} is unavailable")
    return value.get_secret_value()


def safe_twiml(message: str) -> str:
    response = VoiceResponse()
    response.say(message)
    response.hangup()
    return str(response)


def phone_tool_rejected() -> ApiError:
    return ApiError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="PHONE_TOOL_REJECTED",
        message="The phone tool request could not be authenticated",
    )
