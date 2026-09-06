"""One invocation, no server or ambient credential/configuration discovery."""
from __future__ import annotations

import argparse
import os
import struct
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, cast
from uuid import uuid4

from backend.adapters.outbound.generation.conversation import ConversationGenerationAdapter
from backend.adapters.outbound.openai.contracts import OpenAIResponsesTransportFactory
from backend.adapters.outbound.system.conversation_job import (
    FRAME_LIMIT,
    decode_frame,
    decode_request,
    encode_frame,
    result_payload,
)
from backend.agent_runtime.agents.generation import GenerationPort
from backend.infrastructure.config.secrets.provider import EnvironmentProviderSecretResolver
from backend.modules.pedagogical_design.application.commands.create_conversation_draft import (
    CreateConversationDraft,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.modules.work_orchestration.ports.outbound.generation_job import (
    GenerationJobResult,
    GenerationUsage,
)
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-read", type=int)
    parser.add_argument("--private-write", type=int)
    args = parser.parse_args()
    try:
        if args.private_read is not None and args.private_write is not None:
            with private_pipe(args.private_read, "rb") as source, private_pipe(args.private_write, "wb") as sink:
                packet = read_private_packet(source)
                request = read_request(sys.stdin.buffer)
                result = run_authorized_generation(packet, request=request, sink=sink)
                sys.stdout.buffer.write(encode_frame(result_payload(result)))
                sys.stdout.buffer.flush()
                return 0
        request = read_request(sys.stdin.buffer)
        result = GenerationJobResult(request.generation_id, "FAILED_NO_EFFECT",
                                      error_code="GENERATION_NOT_AUTHORIZED")
        sys.stdout.buffer.write(encode_frame(result_payload(result)))
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 1


def private_pipe(handle: int, mode: str) -> BinaryIO:
    if os.name == "nt":
        import msvcrt
        fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDONLY if mode == "rb" else os.O_WRONLY))
    else:
        fd = handle
    return cast(BinaryIO, os.fdopen(fd, mode, buffering=0))


def read_private_packet(source: BinaryIO) -> dict[str, object]:
    header = source.read(4)
    if len(header) != 4 or not 1 <= struct.unpack("!I", header)[0] <= 16380:
        raise ValueError("PRIVATE_CHANNEL_REJECTED")
    size = struct.unpack("!I", header)[0]
    chunks = bytearray()
    while len(chunks) < size:
        chunk = source.read(size - len(chunks))
        if not chunk:
            raise ValueError("PRIVATE_CHANNEL_REJECTED")
        chunks.extend(chunk)
    packet = decode_frame(header + chunks)
    chunks[:] = b"\x00" * len(chunks)
    if set(packet) != {"grant", "runtime_path", "data_root", "secret"}:
        raise ValueError("PRIVATE_CHANNEL_REJECTED")
    return packet


def run_authorized_generation(packet: dict[str, object], *, request: ConversationDraftRequest,
    sink: BinaryIO, material: tuple[str, dict[str, object]] | None = None,
    transport_factory: OpenAIResponsesTransportFactory | None = None) -> GenerationJobResult:
    from backend.adapters.outbound.openai.transport import OpenAISDKResponsesTransportFactory
    from backend.infrastructure.composition.factories.conversation import (
        R2ExecutionEvidence,
        build_conversation_generation_adapter,
        r2_environment_identity,
        r2_source_material,
        validate_r2_grant,
    )
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
    baseline, scope = material if material is not None else r2_source_material()
    grant = packet["grant"]
    if not isinstance(grant, dict):
        raise ValueError("R2_GRANT_REJECTED")
    ceiling = validate_r2_grant(grant, scope=scope, baseline=baseline, now=datetime.now(UTC))
    if grant["environment"] != r2_environment_identity():
        raise ValueError("R2_ENVIRONMENT_REJECTED")
    target = Read15RuntimeTarget(Path(cast(str, packet["runtime_path"])),
        Path(cast(str, packet["data_root"])), cast(str, grant["runtime_sha256"]))
    target.validate()
    def publish(usage: GenerationUsage) -> None:
        frame = encode_frame(asdict(usage))
        sent = 0
        while sent < len(frame):
            amount = sink.write(frame[sent:])
            if not amount:
                raise ValueError("PRIVATE_USAGE_CHANNEL_FAILED")
            sent += amount
        sink.flush()
    evidence = R2ExecutionEvidence(request_sha256=cast(str, grant["projection_sha256"]), publish=publish)
    secret = packet.pop("secret")
    if not isinstance(secret, str) or not secret.strip() or len(secret) > 4096:
        raise ValueError("R2_MASKED_INPUT_REQUIRED")
    adapter = build_conversation_generation_adapter(
        secret_resolver=EnvironmentProviderSecretResolver({"openai.r2.generation": secret}),
        transport_factory=transport_factory or OpenAISDKResponsesTransportFactory(r2_destination=True))
    del secret
    adapter.bind_conversation_execution(before_request=evidence.before_request,
        on_dispatch=evidence.on_dispatch, on_response=evidence.on_response, on_parsing=evidence.on_parsing)
    result = run_generation(request, target=target, generation=adapter, reserved_cost=ceiling)
    return replace(result, usage=evidence.usage)


if __name__ == "__main__":
    raise SystemExit(main())
