import httpx
import pytest

from insurance_operations.conversations.contracts import ConversationProviderError
from insurance_operations.conversations.providers.elevenlabs import (
    ELEVENLABS_API_BASE_URL,
    ElevenLabsConversationProvider,
)


def test_provider_mints_webrtc_token_without_exposing_api_key() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={"token": "short-lived-token", "conversation_id": "conv_test"},
        )

    client = httpx.Client(
        base_url=ELEVENLABS_API_BASE_URL,
        transport=httpx.MockTransport(handler),
    )
    provider = ElevenLabsConversationProvider(
        api_key="server-only-secret",
        agent_id="agent_test",
        client=client,
    )

    grant = provider.authorize_session()

    assert grant.transport == "webrtc"
    assert grant.credential == "short-lived-token"
    assert grant.metadata.external_session_reference == "conv_test"
    assert captured_request is not None
    assert captured_request.url.path == "/v1/convai/conversation/token"
    assert captured_request.url.params["agent_id"] == "agent_test"
    assert captured_request.headers["xi-api-key"] == "server-only-secret"


def test_provider_returns_sanitized_error_for_invalid_response() -> None:
    client = httpx.Client(
        base_url=ELEVENLABS_API_BASE_URL,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                502,
                text="upstream detail containing server-only-secret",
            )
        ),
    )
    provider = ElevenLabsConversationProvider(
        api_key="server-only-secret",
        agent_id="agent_test",
        client=client,
    )

    with pytest.raises(ConversationProviderError) as error:
        provider.authorize_session()

    assert str(error.value) == "conversation provider authorization failed"
    assert "server-only-secret" not in str(error.value)

