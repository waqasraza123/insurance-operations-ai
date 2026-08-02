import httpx
from pydantic import BaseModel, Field, ValidationError

from insurance_operations.conversations.contracts import (
    ConnectionGrant,
    ConversationProviderError,
    ProviderSessionMetadata,
)

ELEVENLABS_API_BASE_URL = "https://api.elevenlabs.io"
ELEVENLABS_ADAPTER_VERSION = "1"


class ConversationTokenResponse(BaseModel):
    token: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1, max_length=200)


class ElevenLabsConversationProvider:
    def __init__(
        self,
        *,
        api_key: str,
        agent_id: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._agent_id = agent_id
        self._client = client or httpx.Client(
            base_url=ELEVENLABS_API_BASE_URL,
            timeout=httpx.Timeout(10),
        )
        self._owns_client = client is None

    def authorize_session(self) -> ConnectionGrant:
        try:
            response = self._client.get(
                "/v1/convai/conversation/token",
                params={"agent_id": self._agent_id},
                headers={"xi-api-key": self._api_key},
            )
            response.raise_for_status()
            token_response = ConversationTokenResponse.model_validate(
                response.json()
            )
        except (httpx.HTTPError, ValidationError, ValueError) as error:
            raise ConversationProviderError(
                "conversation provider authorization failed"
            ) from error

        return ConnectionGrant(
            transport="webrtc",
            credential=token_response.token,
            metadata=ProviderSessionMetadata(
                adapter="elevenlabs_agents",
                adapter_version=ELEVENLABS_ADAPTER_VERSION,
                external_session_reference=token_response.conversation_id,
            ),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
