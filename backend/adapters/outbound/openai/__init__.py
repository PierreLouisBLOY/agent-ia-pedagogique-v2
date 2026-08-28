"""Provider-generic OpenAI Responses transport shared by outbound adapters."""

from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponsesTransport,
    OpenAIResponsesTransportFactory,
    OpenAIResponseUsage,
    OpenAITransportError,
    OpenAITransportErrorCode,
)
from backend.adapters.outbound.openai.transport import (
    OpenAISDKResponsesTransport,
    OpenAISDKResponsesTransportFactory,
)

__all__ = [
    "OpenAIResponsesRequest",
    "OpenAIResponsesResponse",
    "OpenAIResponseStatus",
    "OpenAIResponsesTransport",
    "OpenAIResponsesTransportFactory",
    "OpenAIResponseUsage",
    "OpenAISDKResponsesTransport",
    "OpenAISDKResponsesTransportFactory",
    "OpenAITransportError",
    "OpenAITransportErrorCode",
]
