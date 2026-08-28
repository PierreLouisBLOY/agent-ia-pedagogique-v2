"""OpenAI Responses implementation of the provider-neutral GenerationPort."""

from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
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
    "OpenAIGenerationAdapter",
    "OpenAIResponsesRequest",
    "OpenAIResponsesResponse",
    "OpenAIResponsesTransport",
    "OpenAIResponsesTransportFactory",
    "OpenAIResponseStatus",
    "OpenAIResponseUsage",
    "OpenAISDKResponsesTransport",
    "OpenAISDKResponsesTransportFactory",
    "OpenAITransportError",
    "OpenAITransportErrorCode",
]
