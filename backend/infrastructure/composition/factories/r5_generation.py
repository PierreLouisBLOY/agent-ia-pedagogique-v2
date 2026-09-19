"""Explicit R5 selection, preparation and one-shot supervised composition.

No ambient data discovery, generic retrieval, live grant creation or count call.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import BinaryIO, cast
from uuid import uuid4

from backend.adapters.outbound.generation.conversation import (
    ConversationGenerationAdapter,
    NoGenerationDispatch,
)
from backend.adapters.outbound.generation.openai.mapping import build_openai_request
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesTransportFactory,
)
from backend.adapters.outbound.system.conversation_job import (
    ConversationProcessJob,
    OneShotReceipt,
    decode_frame,
    encode_frame,
)
from backend.agent_runtime.agents.generation import GenerationOperation, GenerationPortRequest
from backend.infrastructure.composition.factories.conversation import (
    R2ExecutionEvidence,
    build_conversation_generation_adapter,
    conversation_provider_configuration,
    r2_count_handoff,
    r2_digest,
    r2_environment_identity,
    r2_request_parameters,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.local_reference import selected_local_evidence
from backend.infrastructure.config.secrets.provider import EnvironmentProviderSecretResolver
from backend.infrastructure.filesystem import read_file_nofollow
from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.application.commands.create_conversation_draft import (
    CreateConversationDraft,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    LOCAL_REFERENCE_LABEL,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.modules.work_orchestration.ports.outbound.generation_job import (
    GenerationJobResult,
    GenerationUsage,
)
from backend.shared_kernel.time import Instant

SCOPE_SCHEMA = "R5-EXACT-SELECTION-SCOPE-1.0"
GRANT_SCHEMA = "R5-GENERATION-GRANT-1.0"
PACKET_SCHEMA = "R5-PRIVATE-WORKER-1.0"
# Proposed technical rates inherited from the inspected configuration, not live approval.
PRICING = {"currency": "USD", "input_bound_per_million": "2.5", "output_per_million": "12"}
SCOPE_FIELDS = {"schema", "baseline_commit", "runtime_sha256", "selection", "provenance_label",
    "brief", "context", "neutral_sha256", "generation_sha256", "count_sha256", "profile_sha256",
    "pricing_sha256", "output_schema_sha256"}
GRANT_FIELDS = {"schema", "baseline_commit", "scope_sha256", "live_authorized", "transfer_authorized",
    "model_profile_approved", "pricing_approved", "provider", "max_calls", "retry", "fallback",
    "issued_at", "expires_at", "ceiling_usd", "token_count_receipt", "count_receipt_sha256",
    "receipt_root_sha256", "environment"}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _sha(value: object, size: int = 64) -> None:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{" + str(size) + "}", value) is None:
        raise ValueError("R5_IDENTITY_REJECTED")


def validate_selection(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 3:
        raise ValueError("R5_SELECTION_REJECTED")
    result = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {
                "object_ref", "object_kind", "passage_ref", "version_or_checksum", "text_sha256"}:
            raise ValueError("R5_SELECTION_REJECTED")
        if any(not isinstance(v, str) or re.fullmatch(r"[A-Za-z0-9:._-]{1,240}", v) is None
               for v in item.values()):
            raise ValueError("R5_SELECTION_REJECTED")
        _sha(item["text_sha256"])
        if item["object_kind"] not in {"RESOURCE", "NOTION", "PEDAGOGICAL_CONTENT", "OFFICIAL_OCCURRENCE"}:
            raise ValueError("R5_SELECTION_REJECTED")
        result.append(dict(item))
    if len({item["passage_ref"] for item in result}) != len(result):
        raise ValueError("R5_SELECTION_REJECTED")
    return tuple(result)


def profile_identity() -> str:
    # asdict contains the logical credential reference, never a resolved credential.
    configuration = conversation_provider_configuration()
    value = asdict(configuration)
    value["provider_profiles"][0]["credential_ref"] = configuration.provider_profiles[0].credential_ref.value
    return r2_digest(value)


def _port_request(projection: Mapping[str, object]) -> GenerationPortRequest:
    return GenerationPortRequest(operation=GenerationOperation(str(projection["operation"])),
        source_step_id=str(projection["source_step_id"]), production_kind=str(projection["production_kind"]),
        objective=str(projection["objective"]), output_format=str(projection["output_format"]),
        pedagogical_context=cast(Mapping[str, object], projection["pedagogical_context"]),
        resolved_inputs=cast(Mapping[str, object], projection["resolved_inputs"]),
        constraints=cast(Mapping[str, object], projection["constraints"]),
        evidence_refs=tuple(cast(Sequence[str], projection["evidence_refs"])),
        expected_sections=tuple(cast(Sequence[str], projection["expected_sections"])),
        output_contract=cast(Mapping[str, object], projection["output_contract"]))


def prepare_exact_selection(target: Read15RuntimeTarget, *, request: ConversationDraftRequest,
                            selection: object) -> dict[str, object]:
    selected = validate_selection(selection)
    bridge = ConversationGenerationAdapter(evidence=lambda: selected_local_evidence(target, selected),
        generation=NoGenerationDispatch(), clock=lambda: Instant(datetime.now(UTC)),
        new_id=lambda prefix: prefix + ":" + uuid4().hex, reserved_cost=Decimal("0"),
        provenance_label=LOCAL_REFERENCE_LABEL)
    prepared = dict(CreateConversationDraft(bridge).prepare(request=request))
    projection = cast(Mapping[str, object], prepared["projection"])
    inputs = cast(Mapping[str, object], projection["resolved_inputs"])
    evidence = cast(Sequence[Mapping[str, object]], inputs["evidence"])
    expected = {item["passage_ref"]: item for item in selected}
    if len(evidence) != len(selected):
        raise ValueError("R5_MATERIALIZATION_REJECTED")
    for item in evidence:
        selected_item = expected.get(item["locator"])
        if (selected_item is None or item["source_ref"] != selected_item["object_ref"]
                or item["version_or_checksum"] != selected_item["version_or_checksum"]
                or item["provenance_label"] != LOCAL_REFERENCE_LABEL
                or not isinstance(item["text"], str) or not 1 <= len(item["text"]) <= 1000
                or hashlib.sha256(item["text"].encode("utf-8")).hexdigest() != selected_item["text_sha256"]):
            raise ValueError("R5_MATERIALIZATION_REJECTED")
    wire = build_openai_request(request=_port_request(projection),
                               model_profile=conversation_provider_configuration().model_profiles[0])
    generation = r2_request_parameters(wire)
    count = cast(dict[str, object], r2_count_handoff(generation)["parameters"])
    return {**prepared, "generation": generation, "count": count,
            "generation_sha256": r2_digest(generation), "count_sha256": r2_digest(count)}


def scope_from_preparation(prepared: Mapping[str, object], *, request: ConversationDraftRequest,
                          target: Read15RuntimeTarget, selection: object, baseline: str) -> dict[str, object]:
    _sha(baseline, 40)
    generation = cast(Mapping[str, object], prepared["generation"])
    text = cast(Mapping[str, object], generation["text"])
    format_value = cast(Mapping[str, object], text["format"])
    return {"schema": SCOPE_SCHEMA, "baseline_commit": baseline, "runtime_sha256": target.expected_sha256,
        "selection": list(validate_selection(selection)), "provenance_label": LOCAL_REFERENCE_LABEL,
        "brief": request.brief, "context": request.context.as_dict(),
        "neutral_sha256": r2_digest(prepared["projection"]),
        "generation_sha256": r2_digest(generation), "count_sha256": r2_digest(prepared["count"]),
        "profile_sha256": profile_identity(), "pricing_sha256": r2_digest(PRICING),
        "output_schema_sha256": r2_digest(format_value["schema"])}


def validate_scope(scope: Mapping[str, object], *, baseline: str) -> None:
    if (set(scope) != SCOPE_FIELDS or scope["schema"] != SCOPE_SCHEMA
            or scope["baseline_commit"] != baseline or scope["provenance_label"] != LOCAL_REFERENCE_LABEL
            or scope["profile_sha256"] != profile_identity() or scope["pricing_sha256"] != r2_digest(PRICING)):
        raise ValueError("R5_SCOPE_REJECTED")
    _sha(baseline, 40)
    for key in SCOPE_FIELDS:
        if key.endswith("sha256"):
            _sha(scope[key])
    validate_selection(scope["selection"])
    if not isinstance(scope["context"], Mapping):
        raise ValueError("R5_CONTEXT_REJECTED")
    ConfirmedConversationContext(scope["context"])
    if not isinstance(scope["brief"], str) or not 1 <= len(scope["brief"]) <= 4000:
        raise ValueError("R5_BRIEF_REJECTED")


def validate_grant(grant: Mapping[str, object], *, scope: Mapping[str, object], baseline: str,
                   now: datetime) -> Decimal:
    validate_scope(scope, baseline=baseline)
    if (set(grant) != GRANT_FIELDS or grant["schema"] != GRANT_SCHEMA
            or grant["baseline_commit"] != baseline or grant["scope_sha256"] != r2_digest(dict(scope))
            or any(grant[key] is not True for key in (
                "live_authorized", "transfer_authorized", "model_profile_approved", "pricing_approved"))
            or grant["provider"] != "OPENAI_ONLY" or type(grant["max_calls"]) is not int
            or grant["max_calls"] != 1 or type(grant["retry"]) is not int or grant["retry"] != 0
            or grant["fallback"] != "NONE"):
        raise ValueError("R5_GRANT_REJECTED")
    issued = datetime.fromisoformat(str(grant["issued_at"]))
    expiry = datetime.fromisoformat(str(grant["expires_at"]))
    if (now.tzinfo is None or issued.tzinfo is None or expiry.tzinfo is None
            or not issued <= now < expiry or expiry - issued > timedelta(minutes=30)):
        raise ValueError("R5_GRANT_EXPIRED")
    _sha(grant["receipt_root_sha256"])
    proof = grant["token_count_receipt"]
    if (not isinstance(proof, dict) or set(proof) != {"schema", "status", "scope_sha256",
            "generation_sha256", "count_sha256", "input_tokens", "count_authorization_sha256",
            "cost_status", "unknown_cost_explicitly_accepted"}
            or proof["schema"] != "R5-COUNT-RECEIPT-1.0" or proof["status"] != "CONFIRMED"
            or proof["scope_sha256"] != grant["scope_sha256"]
            or proof["generation_sha256"] != scope["generation_sha256"]
            or proof["count_sha256"] != scope["count_sha256"]
            or type(proof["input_tokens"]) is not int or not 1 <= proof["input_tokens"] <= 32768
            or type(proof["unknown_cost_explicitly_accepted"]) is not bool
            or proof["cost_status"] not in {"KNOWN", "UNKNOWN"}
            or (proof["cost_status"] == "UNKNOWN" and proof["unknown_cost_explicitly_accepted"] is not True)
            or r2_digest(proof) != grant["count_receipt_sha256"]):
        raise ValueError("R5_COUNT_REQUIRED")
    _sha(proof["count_authorization_sha256"])
    if not isinstance(grant["ceiling_usd"], str):
        raise ValueError("R5_BUDGET_REJECTED")
    ceiling = Decimal(grant["ceiling_usd"])
    required = (Decimal(proof["input_tokens"]) * Decimal("2.5") + Decimal(4096) * Decimal("12")) / 1_000_000
    if not ceiling.is_finite() or not required <= ceiling <= Decimal("0.140000"):
        raise ValueError("R5_BUDGET_REJECTED")
    if grant["environment"] != r2_environment_identity():
        raise ValueError("R5_ENVIRONMENT_REJECTED")
    return ceiling


def check_material(scope: Mapping[str, object], *, request: ConversationDraftRequest,
                   target: Read15RuntimeTarget) -> dict[str, object]:
    if (request.brief != scope["brief"] or request.context.as_dict() != scope["context"]
            or target.expected_sha256 != scope["runtime_sha256"]):
        raise ValueError("R5_REQUEST_REJECTED")
    prepared = prepare_exact_selection(target, request=request, selection=scope["selection"])
    actual = scope_from_preparation(prepared, request=request, target=target,
                                   selection=scope["selection"], baseline=str(scope["baseline_commit"]))
    if actual != scope:
        raise ValueError("R5_REQUEST_IDENTITY_REJECTED")
    return prepared


def current_baseline() -> str:
    root = Path(__file__).resolve().parents[4]
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH") if k in os.environ}
    args = ["git", "-c", "safe.directory=" + root.as_posix()]
    def git(*values: str) -> bytes:
        return subprocess.run([*args, *values], cwd=root, env=env, capture_output=True,
            check=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    baseline = git("rev-parse", "HEAD").decode("ascii").strip()
    git("diff", "--exit-code", baseline, "--", "backend", "pyproject.toml", "requirements")
    if git("ls-files", "--others", "--exclude-standard", "--", "backend"):
        raise ValueError("R5_UNCOMMITTED_SOURCE_REJECTED")
    if git("rev-parse", "HEAD").decode("ascii").strip() != baseline:
        raise ValueError("R5_BASELINE_CHANGED")
    return baseline


def load_document(path: Path) -> dict[str, object]:
    if not path.is_absolute():
        raise ValueError("R5_EXPLICIT_DOCUMENT_REQUIRED")
    raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=12000)
    import struct
    return decode_frame(struct.pack("!I", len(raw)) + raw)


def build_r5_process_job(*, grant: Mapping[str, object], scope: Mapping[str, object], baseline: str,
    target: Read15RuntimeTarget, receipt_root: Path, private_temp: Path,
    credential_input: Callable[[], str]) -> ConversationProcessJob:
    # Snapshot caller-owned mappings: later mutation cannot silently rebind authority.
    grant = json.loads(canonical_bytes(dict(grant)))
    scope = json.loads(canonical_bytes(dict(scope)))
    ceiling = validate_grant(grant, scope=scope, baseline=baseline, now=datetime.now(UTC))
    if grant["receipt_root_sha256"] != r2_digest(str(receipt_root.absolute()).casefold()):
        raise ValueError("R5_RECEIPT_NAMESPACE_REJECTED")
    if target.expected_sha256 != scope["runtime_sha256"]:
        raise ValueError("R5_TARGET_REJECTED")
    validated: list[ConversationDraftRequest] = []
    def authorize(request: ConversationDraftRequest) -> None:
        validate_grant(grant, scope=scope, baseline=baseline, now=datetime.now(UTC))
        check_material(scope, request=request, target=target)
        validated[:] = [request]
    def technical() -> Mapping[str, object]:
        validate_grant(grant, scope=scope, baseline=baseline, now=datetime.now(UTC))
        if not validated:
            raise ValueError("R5_REQUEST_NOT_VALIDATED")
        check_material(scope, request=validated[0], target=target)
        packet = {"schema": PACKET_SCHEMA, "scope": dict(scope), "grant": dict(grant),
            "runtime_path": str(target.runtime_path), "data_root": str(target.data_root), "secret": ""}
        # Reserve worst-case credential size before asking for masked input.
        if len(encode_frame({**packet, "secret": "x" * 4096})) > 16384:
            raise ValueError("R5_PRIVATE_CHANNEL_BOUND")
        secret = credential_input()
        if not isinstance(secret, str) or not secret.strip() or len(secret) > 4096:
            raise ValueError("R5_MASKED_INPUT_REQUIRED")
        packet["secret"] = secret
        return packet
    root = Path(__file__).resolve().parents[4]
    environment = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH") if k in os.environ}
    environment.update({"TEMP": str(private_temp), "TMP": str(private_temp), "PYTHONPATH": str(root),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    receipt = OneShotReceipt(receipt_root, r2_digest(dict(grant)), ceiling)
    receipt.require_unused()
    return ConversationProcessJob(executable=Path(sys.executable), working_directory=root,
        environment=environment, authorize=authorize, receipt=receipt, technical=technical)


def run_r5_worker(packet: dict[str, object], *, request: ConversationDraftRequest, sink: BinaryIO,
    transport_factory: OpenAIResponsesTransportFactory | None = None,
    baseline: str | None = None) -> GenerationJobResult:
    if set(packet) != {"schema", "scope", "grant", "runtime_path", "data_root", "secret"} or packet["schema"] != PACKET_SCHEMA:
        raise ValueError("R5_PACKET_REJECTED")
    scope, grant = packet["scope"], packet["grant"]
    if not isinstance(scope, dict) or not isinstance(grant, dict):
        raise ValueError("R5_PACKET_REJECTED")
    # Only explicit test transport injection can bind an artificial Git identity.
    identity = baseline if baseline is not None and transport_factory is not None else current_baseline()
    ceiling = validate_grant(grant, scope=scope, baseline=identity, now=datetime.now(UTC))
    target = Read15RuntimeTarget(Path(str(packet["runtime_path"])), Path(str(packet["data_root"])),
                                str(scope["runtime_sha256"]))
    check_material(scope, request=request, target=target)
    def publish(usage: GenerationUsage) -> None:
        frame = encode_frame(asdict(usage))
        sent = 0
        while sent < len(frame):
            amount = sink.write(frame[sent:])
            if not amount:
                raise ValueError("R5_USAGE_CHANNEL_FAILED")
            sent += amount
        sink.flush()
    evidence = R2ExecutionEvidence(request_sha256=str(scope["generation_sha256"]), publish=publish)
    secret = packet.pop("secret")
    if not isinstance(secret, str) or not secret.strip() or len(secret) > 4096:
        raise ValueError("R5_MASKED_INPUT_REQUIRED")
    if transport_factory is None:
        from backend.adapters.outbound.openai.transport import OpenAISDKResponsesTransportFactory
        transport_factory = OpenAISDKResponsesTransportFactory(r2_destination=True)
    adapter = build_conversation_generation_adapter(
        secret_resolver=EnvironmentProviderSecretResolver({"openai.r2.generation": secret}),
        transport_factory=transport_factory)
    del secret
    def before(provider_request: OpenAIResponsesRequest) -> None:
        validate_grant(grant, scope=scope, baseline=identity, now=datetime.now(UTC))
        evidence.before_request(provider_request)
    adapter.bind_conversation_execution(before_request=before, on_dispatch=evidence.on_dispatch,
        on_response=evidence.on_response, on_parsing=evidence.on_parsing)
    selected = validate_selection(scope["selection"])
    bridge = ConversationGenerationAdapter(evidence=lambda: selected_local_evidence(target, selected),
        generation=adapter, clock=lambda: Instant(datetime.now(UTC)),
        new_id=lambda prefix: prefix + ":" + uuid4().hex, reserved_cost=ceiling,
        provenance_label=LOCAL_REFERENCE_LABEL)
    try:
        draft = CreateConversationDraft(bridge).create(request=request)
        # R5 never presents a provider-incomplete answer as a completed candidate.
        if evidence.usage.parsing != "SUCCEEDED":
            raise ConversationRejected("GENERATION_OUTPUT_INVALID")
        result = GenerationJobResult(request.generation_id, "CANDIDATE_READY", draft=draft)
    except ConversationRejected:
        result = GenerationJobResult(request.generation_id,
            ("FAILED_OUTPUT" if evidence.usage.response_received else "UNKNOWN")
            if evidence.usage.provider_attempted else "FAILED_NO_EFFECT",
            error_code="GENERATION_OUTPUT_INVALID")
    except Exception:
        result = GenerationJobResult(request.generation_id, "UNKNOWN" if evidence.usage.provider_attempted
            else "FAILED_NO_EFFECT", error_code="GENERATION_OUTCOME_UNKNOWN")
    return replace(result, usage=evidence.usage)
