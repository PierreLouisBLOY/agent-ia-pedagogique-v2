"""Provider-generic OpenAI Responses transport shared by outbound adapters."""

from backend.adapters.outbound.openai.contracts import (
    OpenAIIncompleteReason,
    OpenAIReasoningEffort,
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
    "OpenAIIncompleteReason",
    "OpenAIReasoningEffort",
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
