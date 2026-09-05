"""One invocation, no server or ambient credential/configuration discovery."""
from __future__ import annotations

import struct
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, BinaryIO
from uuid import uuid4

from backend.adapters.outbound.generation.conversation import ConversationGenerationAdapter
from backend.adapters.outbound.system.conversation_job import (
    FRAME_LIMIT,
    decode_frame,
    decode_request,
    encode_frame,
    result_payload,
)
from backend.agent_runtime.agents.generation import GenerationPort
from backend.modules.pedagogical_design.application.commands.create_conversation_draft import (
    CreateConversationDraft,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.modules.work_orchestration.ports.outbound.generation_job import GenerationJobResult
from backend.shared_kernel.time import Instant

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget


def run_generation(request: ConversationDraftRequest, *, target: Read15RuntimeTarget,
                   generation: GenerationPort, reserved_cost: Decimal) -> GenerationJobResult:
    from backend.infrastructure.composition.factories.conversation import conversation_evidence
    bridge = ConversationGenerationAdapter(evidence=lambda: conversation_evidence(target),
        generation=generation, clock=lambda: Instant(datetime.now(UTC)),
        new_id=lambda prefix: prefix + ":" + uuid4().hex, reserved_cost=reserved_cost)
    try:
        draft = CreateConversationDraft(bridge).create(request=request)
        return GenerationJobResult(request.generation_id, "CANDIDATE_READY", draft=draft)
    except ConversationRejected as error:
        if error.code == "INSUFFICIENT_EVIDENCE":
            return GenerationJobResult(request.generation_id, "FAILED_NO_EFFECT", error_code=error.code)
        return GenerationJobResult(request.generation_id, "FAILED_OUTPUT", error_code="GENERATION_OUTPUT_INVALID")
    except Exception:
        return GenerationJobResult(request.generation_id, "UNKNOWN", error_code="GENERATION_OUTCOME_UNKNOWN")


def read_request(source: BinaryIO) -> ConversationDraftRequest:
    header = source.read(4)
    if len(header) != 4:
        raise ValueError("IPC_FRAME_REJECTED")
    size = struct.unpack("!I", header)[0]
    if not 1 <= size <= FRAME_LIMIT:
        raise ValueError("IPC_FRAME_REJECTED")
    raw = source.read(size + 1)
    return decode_request(decode_frame(header + raw))


def main() -> int:
    # No live authorization, selected credential source or proved input-token bound in this baseline.
    # This entrypoint must not acquire them from a request, environment, or historical approval.
    try:
        request = read_request(sys.stdin.buffer)
        result = GenerationJobResult(request.generation_id, "FAILED_NO_EFFECT",
                                      error_code="GENERATION_NOT_AUTHORIZED")
        sys.stdout.buffer.write(encode_frame(result_payload(result)))
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
