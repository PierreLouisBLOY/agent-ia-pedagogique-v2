"""Explicit R2 composition; no ambient configuration or credential inspection."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib.metadata import distribution, version
from pathlib import Path
from secrets import token_urlsafe
from typing import TYPE_CHECKING, NoReturn, cast
from uuid import uuid4

from backend.adapters.inbound.api.conversation import ConversationEndpoint
from backend.adapters.inbound.api.production import ProductionEndpoint
from backend.adapters.inbound.application.conversation import (
    ConversationApplicationInbound,
    ConversationInputError,
)
from backend.adapters.inbound.application.production import ProductionUseCaseInbound
from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.sqlite import (
    SQLiteEvidenceDocumentContentAdapter,
    SQLiteEvidenceSearchAdapter,
)
from backend.adapters.outbound.generation.openai import OpenAIGenerationAdapter
from backend.adapters.outbound.openai import OpenAIResponsesTransportFactory
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
)
from backend.adapters.outbound.openai.transport import openai_sdk_import_path
from backend.adapters.outbound.persistence.conversation_memory import ConversationMemoryStore
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
from backend.adapters.outbound.search.sqlite import BusinessSearchAdapter
from backend.adapters.outbound.system.conversation_job import (
    ConversationProcessJob,
    OneShotReceipt,
    decode_frame,
    encode_frame,
    usage_cost_evidence,
)
from backend.agent_runtime.agents.evidence import (
    EvidenceAgent,
    EvidenceMaterializationPolicy,
    RetrievalChannel,
    RetrievalCoordinationPolicy,
    RetrievalCoordinator,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    UseCaseRequest,
    UseCaseResult,
)
from backend.agent_runtime.orchestration import (
    WorkflowRequirements,
    WorkflowSelectionStatus,
    WorkflowSelector,
)
from backend.agent_runtime.orchestration.workflows import WorkflowKind
from backend.core_contracts.invocation import UseCaseContext
from backend.infrastructure.composition.factories.openai import build_openai_generation_adapter
from backend.infrastructure.config.effective_config.provider import EffectiveProviderConfiguration
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderConfigurationVersion,
    ProviderCostLimit,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderRouteConfig,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretResolver,
)
from backend.infrastructure.filesystem import read_file_nofollow
from backend.modules.pedagogical_context.application.services.conversation_context import (
    ConversationContextService,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.application.queries.read_production import (
    ReadProductionQuery,
)
from backend.modules.work_orchestration.application.services.conversation import (
    ConversationService,
    initial_conversation,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationRejected
from backend.modules.work_orchestration.ports.outbound.generation_job import (
    GenerationJobPort,
    GenerationJobResult,
    GenerationUsage,
)
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

if TYPE_CHECKING:
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget


@dataclass(frozen=True, slots=True)
class ConversationEvidenceClock:
    def now(self) -> Instant:
        return Instant(datetime.now(UTC))


@contextmanager
def conversation_evidence(target: Read15RuntimeTarget) -> Iterator[EvidenceAgent]:
    """Only the explicitly supplied synthetic target; hash verified before SQLite open."""
    target.validate()
    connection = connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)
    try:
        search = SQLiteEvidenceSearchAdapter(BusinessSearchAdapter(connection))
        coordinator = RetrievalCoordinator(
            search_port=search, admissibility_port=search,
            policy=RetrievalCoordinationPolicy(
                (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL),
                (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL), 10, 3, 60,
            ),
        )
        content = SQLiteEvidenceDocumentContentAdapter(DocumentContentAccessAdapter(connection),
                                                        ConversationEvidenceClock())
        with SQLiteLocalSearchAdapter(connection).read_snapshot():
            yield EvidenceAgent(coordinator, content, EvidenceMaterializationPolicy(1000))
    finally:
        connection.close()


class UnapprovedGenerationJob:
    """Real product refusal: no live authority may be inferred from implementation approval."""
    def authorize(self, request: ConversationDraftRequest) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def start(self, request: ConversationDraftRequest) -> NoReturn:
        raise ConversationRejected("GENERATION_NOT_AUTHORIZED")

    def poll(self) -> GenerationJobResult | None:
        return None

    def close(self) -> None:
        return None


def conversation_provider_configuration() -> EffectiveProviderConfiguration:
    """Pure proposed profile. Neither configuration nor a cost ceiling grants live authority.

    The 32768 input allowance remains unproved: default product dispatch stays disabled.
    This function never reads environment, a secret, a configuration file or a runtime.
    """
    provider_id = ProviderProfileId("openai.r2")
    model_id = ModelProfileId("openai.gpt-5.6-terra.generation")
    return EffectiveProviderConfiguration(
        ProviderConfigurationVersion(1, 0),
        (ProviderProfileConfig(provider_id, ProviderCode("openai"),
                               ProviderCredentialRef("openai.r2.generation")),),
        (ModelProfileConfig(model_id, provider_id, ModelCode("gpt-5.6-terra"),
            ModelContextLimits(1_050_000, 32768, 4096),
            ProviderInvocationLimits(1, 90000, 32768, 4096, 36864,
                                     ProviderCostLimit(140000, "USD")),
            (ProviderWorkloadKind.GENERATION,), structured_output_required=True),),
        (ProviderRouteConfig(ProviderWorkloadKind.GENERATION, model_id),),
    )


def build_conversation_generation_adapter(*, secret_resolver: ProviderSecretResolver,
    transport_factory: OpenAIResponsesTransportFactory) -> OpenAIGenerationAdapter:
    """Explicit existing-factory binding, inert until invoked by an authorized caller.

    No default resolver/transport acquisition: synthetic validation injects test-only doubles.
    Product CLI does not bind this function before a separately approved live handoff.
    """
    return build_openai_generation_adapter(configuration=conversation_provider_configuration(),
        workload_kind=ProviderWorkloadKind.GENERATION, secret_resolver=secret_resolver,
        transport_factory=transport_factory)


def proposed_conversation_cost() -> Decimal:
    """Conservative documented proposal, not a verified input bound or owner approval."""
    return (Decimal(32768) * Decimal("2") * Decimal("1.25") +
            Decimal(4096) * Decimal("12")) / Decimal(1_000_000)


def r2_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def r2_request_parameters(request: OpenAIResponsesRequest) -> dict[str, object]:
    """Exact semantic create request; no conversational history or hidden additions."""
    if (request.model != "gpt-5.6-terra" or request.max_output_tokens != 4096
            or request.service_tier != "default" or request.reasoning_effort is None
            or request.reasoning_effort.value != "low"):
        raise ValueError("R2_REQUEST_REJECTED")
    return {"background": False, "model": request.model, "instructions": request.instructions,
        "input": request.input_json, "max_output_tokens": 4096, "service_tier": "default",
        "store": False, "stream": False, "reasoning": {"effort": "low"},
        "tools": [], "tool_choice": "none", "text": {"format": {
            "type": "json_schema", "name": request.schema_name,
            "schema": request.output_schema, "strict": True}}}


def r2_count_handoff(projection: Mapping[str, object]) -> dict[str, object]:
    """Pure count projection; no credential, SDK client or operation performed.

    input_tokens.count accepts these seven fields. Output reservation, tier,
    background/store/stream are create-only, bound by the complete request hash.
    """
    expected = {"model", "instructions", "input", "text", "reasoning", "tools", "tool_choice",
                "background", "store", "stream", "service_tier", "max_output_tokens"}
    if set(projection) != expected:
        raise ValueError("R2_COUNT_FIELDS_REJECTED")
    fields = ("model", "instructions", "input", "text", "reasoning", "tools", "tool_choice")
    parameters = {key: projection[key] for key in fields}
    return {"generation_request_sha256": r2_digest(dict(projection)),
            "count_request_sha256": r2_digest(parameters), "parameters": parameters,
            "status": "PENDING_AUTHORIZED_COUNT", "cost_status": "NOT_ESTABLISHED"}


def r2_environment_identity() -> dict[str, str]:
    """Package metadata only; no client construction or environment/secret inspection."""
    if sys.version_info[:2] != (3, 12) or sys.platform != "win32" or version("openai") != "3.8.0":
        raise ValueError("R2_LOCKED_ENVIRONMENT_REQUIRED")
    package = Path(str(distribution("openai").locate_file("openai"))).resolve()
    if (not package.is_relative_to(Path(sys.prefix).resolve())
            or openai_sdk_import_path() != package / "__init__.py"):
        raise ValueError("R2_LOCKED_SDK_PATH_REQUIRED")
    return {"python": ".".join(str(n) for n in sys.version_info[:3]),
            "platform": sys.platform, "openai": version("openai")}


_R2_UNKNOWN_COUNT_RECEIPT_SHA256 = "b31b77e43e949831b7c06b7ed30418f01edbd4c7b529b32fade95ec597bae936"
_R2_UNKNOWN_COUNT_AUTHORIZATION_SHA256 = "5e62ec067cd99af49e5d378d29b473c3a3d7ba263ee43aa164944dae25c09c46"


def count_receipt_financially_admissible_for_generation(
    proof: Mapping[str, object], *, scope_sha256: str,
) -> bool:
    """Pure closed exception for one owner-accepted receipt, never a live grant.

    Legacy known-cost proofs retain their six-field shape. UNKNOWN additionally
    carries the original UTF-8 receipt/approval text (not paths) so their raw
    SHA-256 identities can be verified without reading files or resolving keys.
    Historical receipt flags are preserved; this is a new admissibility decision.
    """
    core = {"kind", "generation_request_sha256", "count_request_sha256", "input_tokens",
            "count_authorization_sha256", "count_cost_status"}
    count = proof.get("input_tokens")
    authorization_sha = proof.get("count_authorization_sha256")
    if (proof.get("kind") != "AUTHORIZED_PROVIDER_COUNT" or type(count) is not int
            or not 0 < count <= 32768 or not isinstance(authorization_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", authorization_sha) is None):
        return False
    cost = proof.get("count_cost_status")
    if cost in ("APPROVED_BOUND", "MEASURED"):
        # This specific approval accepts UNKNOWN, not a fabricated known/zero cost.
        return set(proof) == core and authorization_sha != _R2_UNKNOWN_COUNT_AUTHORIZATION_SHA256
    if (cost != "UNKNOWN" or set(proof) != core | {
            "count_receipt_raw", "count_receipt_sha256", "count_authorization_raw"}
            or authorization_sha != _R2_UNKNOWN_COUNT_AUTHORIZATION_SHA256
            or proof["count_receipt_sha256"] != _R2_UNKNOWN_COUNT_RECEIPT_SHA256
            or count != 1100
            or scope_sha256 != "89572eeb3204c895c22b559058229be6cd678d5e2562f40965d46f97f10b7502"):
        return False
    receipt_raw, authorization_raw = proof["count_receipt_raw"], proof["count_authorization_raw"]
    if not isinstance(receipt_raw, str) or not isinstance(authorization_raw, str):
        return False
    try:
        receipt_bytes, authorization_bytes = receipt_raw.encode("utf-8"), authorization_raw.encode("utf-8")
        if (len(receipt_bytes) > 4096 or len(authorization_bytes) > 4096
                or hashlib.sha256(receipt_bytes).hexdigest() != _R2_UNKNOWN_COUNT_RECEIPT_SHA256
                or hashlib.sha256(authorization_bytes).hexdigest() != authorization_sha):
            return False
        receipt = json.loads(receipt_raw)
    except (UnicodeError, ValueError):
        return False
    if not isinstance(receipt, dict) or not {
        "OWNER_R2_COUNT = APPROVED",
        "COUNT_COST_STATUS = UNKNOWN_ACCEPTED_FOR_THIS_SINGLE_COUNT",
        "COUNT_CALLS_MAX = 1", "COUNT_RETRY = FORBIDDEN",
        "P_LIVE_GENERATION = NOT_AUTHORIZED", "OWNER_ATTESTATION = APPROVED",
    }.issubset(authorization_raw.splitlines()):
        return False
    bindings = {
        "baseline_commit": "dee62951e34a46af942aefdfcd9abfc3a2d0c7bb",
        "scope_canonical_sha256": scope_sha256,
        "count_authorization_sha256": authorization_sha,
        "count_request_sha256": "b284e5da6b8c341acac469cecec641b6185c22ebd92e5b8812a2c1835d628bb7",
        "generation_request_sha256": "576e7008056bd74038e1b74be94e3278e67b29fa5591f6699a34d964f15002a7",
        "count_status": "PASS", "count_cost_status": "UNKNOWN", "replay": "FORBIDDEN",
        "live_authorization": "CONSUMED", "P_LIVE_GENERATION": "NOT_AUTHORIZED",
    }
    return (all(receipt.get(key) == value for key, value in bindings.items())
            and proof["count_request_sha256"] == bindings["count_request_sha256"]
            and proof["generation_request_sha256"] == bindings["generation_request_sha256"]
            and type(receipt.get("input_tokens")) is int and receipt["input_tokens"] == 1100
            and type(receipt.get("COUNT_API_CALLS")) is int and receipt["COUNT_API_CALLS"] == 1
            and type(receipt.get("GENERATION_CALLS")) is int and receipt["GENERATION_CALLS"] == 0
            and receipt.get("provider_attempted") is True and receipt.get("response_received") is True)


def validate_r2_grant(grant: Mapping[str, object], *, scope: Mapping[str, object],
                      baseline: str, now: datetime) -> Decimal:
    """No I/O: explicit owner grant, count receipt binding and reserve before secret."""
    keys = {"schema", "operation", "baseline_commit", "scope_sha256", "projection_sha256",
        "profile_sha256", "pricing_sha256", "output_schema_sha256", "usage_contract_sha256", "provider", "max_calls",
        "ceiling_usd", "live_authorized", "transfer_authorized", "credential_source", "expires_at",
        "token_count_receipt", "token_count_receipt_sha256", "runtime_sha256", "environment",
        "receipt_root_sha256"}
    if (set(grant) != keys or grant["schema"] != "R2-GENERATION-GRANT-1.0"
            or grant["operation"] != "GENERATION" or grant["live_authorized"] is not True
            or grant["transfer_authorized"] is not True or grant["provider"] != "OPENAI_ONLY"
            or type(grant["max_calls"]) is not int or grant["max_calls"] != 1
            or grant["credential_source"] != "MASKED_LOCAL_PRIVATE_CHANNEL"
            or re.fullmatch(r"[0-9a-f]{40}", baseline) is None or grant["baseline_commit"] != baseline
            or grant["scope_sha256"] != r2_digest(dict(scope))):
        raise ValueError("R2_GRANT_REJECTED")
    for key in ("projection_sha256", "profile_sha256", "pricing_sha256", "output_schema_sha256", "usage_contract_sha256"):
        if not isinstance(scope.get(key), str) or grant[key] != scope[key]:
            raise ValueError("R2_GRANT_IDENTITY_REJECTED")
    for key in ("runtime_sha256", "receipt_root_sha256"):
        value = grant[key]
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("R2_GRANT_REJECTED")
    expiry = datetime.fromisoformat(cast(str, grant["expires_at"]))
    if expiry.tzinfo is None or now.tzinfo is None or expiry <= now:
        raise ValueError("R2_GRANT_EXPIRED")
    ceiling = Decimal(cast(str, grant["ceiling_usd"]))
    if not ceiling.is_finite() or not proposed_conversation_cost() <= ceiling <= Decimal("0.140000"):
        raise ValueError("R2_BUDGET_REJECTED")
    projection = cast(dict[str, object], scope["projection"])
    if r2_digest(projection) != grant["projection_sha256"]:
        raise ValueError("R2_SCOPE_REJECTED")
    handoff = r2_count_handoff(projection)
    proof = grant["token_count_receipt"]
    if (not isinstance(proof, dict)
            or not count_receipt_financially_admissible_for_generation(proof, scope_sha256=r2_digest(dict(scope)))
            or proof["generation_request_sha256"] != handoff["generation_request_sha256"]
            or proof["count_request_sha256"] != handoff["count_request_sha256"]
            or grant["token_count_receipt_sha256"] != r2_digest(proof)):
        raise ValueError("R2_AUTHORIZED_COUNT_REQUIRED")
    return ceiling


class R2ExecutionEvidence:
    """Technical pre-parsing capture; sink is private and injected by composition."""
    def __init__(self, *, request_sha256: str, publish: Callable[[GenerationUsage], None]) -> None:
        self.request_sha256, self.publish = request_sha256, publish
        self.usage = GenerationUsage()
        self.used = False

    def before_request(self, request: OpenAIResponsesRequest) -> None:
        if self.used or r2_digest(r2_request_parameters(request)) != self.request_sha256:
            raise ValueError("R2_REQUEST_OR_REPLAY_REJECTED")
        self.used = True

    def on_dispatch(self) -> None:
        self.usage = replace(self.usage, provider_attempted=True)
        self.publish(self.usage)  # A failure here prevents provider dispatch.

    def on_response(self, response: OpenAIResponsesResponse) -> None:
        usage = response.usage
        try:
            self.usage = GenerationUsage(provider_attempted=True, response_received=True,
                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens, cached_input_tokens=usage.cached_input_tokens,
                cache_write_input_tokens=usage.cache_write_input_tokens,
                reasoning_tokens=usage.reasoning_tokens, service_tier=response.service_tier or "UNKNOWN")
        except ValueError:
            self.usage = GenerationUsage(provider_attempted=True, response_received=True)
        self.publish(self.usage)

    def on_parsing(self, status: str) -> None:
        self.usage = replace(self.usage, parsing=status)
        self.publish(self.usage)


def r2_cost_evidence(usage: GenerationUsage) -> dict[str, object]:
    """No cache assumptions and no double billing of reasoning tokens."""
    return usage_cost_evidence(usage)


def r2_source_material() -> tuple[str, dict[str, object]]:
    """Authenticate committed source only; no business target or credential discovery."""
    root = Path(__file__).resolve().parents[4]
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH") if key in os.environ}
    args = ["git", "-c", "safe.directory=" + root.as_posix()]
    result = subprocess.run([*args, "rev-parse", "HEAD"], cwd=root, env=env,
        capture_output=True, check=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    baseline = result.stdout.decode("ascii").strip()
    folder = root / "docs/development/phase_12_18_h2_r2_generation"
    manifest = read_file_nofollow(folder / "MANIFEST_SHA256.txt", allowed_root=root, maximum_bytes=32768)
    committed = subprocess.run([*args, "show", baseline + ":docs/development/phase_12_18_h2_r2_generation/MANIFEST_SHA256.txt"],
        cwd=root, env=env, capture_output=True, check=True, timeout=5,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    if manifest != committed:
        raise ValueError("R2_UNCOMMITTED_MANIFEST_REJECTED")
    paths = ["docs/development/phase_12_18_h2_r2_generation/MANIFEST_SHA256.txt"]
    for line in manifest.decode("utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        # Active manifest uses repo-relative traversals from its fixed folder.
        path = Path(os.path.abspath(folder / relative))  # Normalize without following source symlinks.
        if not path.is_relative_to(root) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("R2_SOURCE_MANIFEST_REJECTED")
        raw = read_file_nofollow(path, allowed_root=root, maximum_bytes=2_000_000)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("R2_SOURCE_IDENTITY_REJECTED")
        paths.append(path.relative_to(root).as_posix())
    subprocess.run([*args, "diff", "--exit-code", baseline, "--", *paths], cwd=root, env=env,
        capture_output=True, check=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    final_head = subprocess.run([*args, "rev-parse", "HEAD"], cwd=root, env=env,
        capture_output=True, check=True, timeout=5,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.decode("ascii").strip()
    if final_head != baseline:
        raise ValueError("R2_BASELINE_CHANGED")
    scope = json.loads(read_file_nofollow(folder / "LIVE_GENERATION_SCOPE.json",
        allowed_root=root, maximum_bytes=65536))
    if not isinstance(scope, dict):
        raise ValueError("R2_SCOPE_REJECTED")
    return baseline, scope


def build_r2_process_job(*, grant: Mapping[str, object], scope: Mapping[str, object], baseline: str,
    target: Read15RuntimeTarget, receipt_root: Path, private_temp: Path,
    credential_input: Callable[[], str]) -> ConversationProcessJob:
    environment_identity = r2_environment_identity()
    ceiling = validate_r2_grant(grant, scope=scope, baseline=baseline, now=datetime.now(UTC))
    if grant["environment"] != environment_identity or grant["runtime_sha256"] != target.expected_sha256:
        raise ValueError("R2_ENVIRONMENT_OR_TARGET_REJECTED")
    if grant["receipt_root_sha256"] != r2_digest(str(receipt_root.absolute()).casefold()):
        raise ValueError("R2_RECEIPT_NAMESPACE_REJECTED")
    projection = cast(dict[str, object], scope["projection"])
    pedagogical = json.loads(cast(str, projection["input"]))
    def authorize(request: ConversationDraftRequest) -> None:
        validate_r2_grant(grant, scope=scope, baseline=baseline, now=datetime.now(UTC))
        if (request.brief != pedagogical["objective"]
                or request.context.as_dict() != pedagogical["pedagogical_context"]):
            raise ConversationRejected("GENERATION_NOT_AUTHORIZED")
    def technical() -> Mapping[str, object]:
        # Runs once after reservation, never on read/poll and never for an invalid grant.
        validate_r2_grant(grant, scope=scope, baseline=baseline, now=datetime.now(UTC))
        secret = credential_input()
        if not isinstance(secret, str) or not secret.strip() or len(secret) > 4096:
            raise ValueError("R2_MASKED_INPUT_REQUIRED")
        return {"grant": dict(grant), "runtime_path": str(target.runtime_path),
                "data_root": str(target.data_root), "secret": secret}
    root = Path(__file__).resolve().parents[4]
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH") if key in os.environ}
    environment.update({"TEMP": str(private_temp), "TMP": str(private_temp), "PYTHONPATH": str(root),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    receipt = OneShotReceipt(receipt_root, r2_digest(dict(grant)), ceiling)
    receipt.require_unused()
    return ConversationProcessJob(executable=Path(sys.executable), working_directory=root,
        environment=environment, authorize=authorize,
        receipt=receipt, technical=technical)


def load_r2_grant(path: Path) -> dict[str, object]:
    if not path.is_absolute():
        raise ValueError("R2_EXPLICIT_GRANT_REQUIRED")
    raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=16384)
    # Reuse the closed JSON decoder (duplicate keys, constants and oversized frames).
    return decode_frame(encode_frame(json.loads(raw, object_pairs_hook=_r2_unique_pairs)))


def _r2_unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("R2_DUPLICATE_GRANT_KEY")
        result[key] = value
    return result


def observe_conversation_ambiguity() -> None:
    decision = WorkflowSelector().select(WorkflowRequirements(
        blocking_ambiguity=True, human_gate_required=True,
        external_evidence_required=True, production_required=True))
    if (decision.status is not WorkflowSelectionStatus.WAITING_HUMAN
            or decision.stages or decision.overlays != (WorkflowKind.WF_10,)):
        raise ConversationRejected("APPLICATION_FAILURE")
    # WF-10 is observed, never compiled, dispatched or granted an application action.


@dataclass(frozen=True, slots=True)
class ConversationComposition:
    service: ConversationService
    endpoint: ConversationEndpoint
    production: ProductionEndpoint
    store: ConversationMemoryStore


def build_conversation(*, jobs: GenerationJobPort | None = None) -> ConversationComposition:
    def clock() -> datetime:
        return datetime.now(UTC)
    def new_id(prefix: str) -> str:
        return prefix + ":" + uuid4().hex
    identifier = new_id("conv")
    expires = clock() + timedelta(hours=2)
    store = ConversationMemoryStore(initial_conversation(identifier, expires))
    service = ConversationService(conversation_id=identifier, store=store,
        jobs=jobs if jobs is not None else UnapprovedGenerationJob(), contexts=ConversationContextService(),
        new_id=new_id, clock=clock, expires_at=expires, ambiguity_observer=observe_conversation_ambiguity)
    inbound = ProductionUseCaseInbound(ReadProductionQuery(store), conversation_id=identifier)

    def read(production: str, version: str, correlation: str) -> UseCaseResult[object, object]:
        try:
            service.snapshot()  # Expiration/access gate; no polling, provider, credential or SQLite.
        except ConversationRejected as error:
            raise ConversationInputError(error.code) from None
        corr = CorrelationId(correlation)
        request = UseCaseRequest(meta=ContractMeta(
            AGENT_CONTRACT_SCHEMA_V1_0, "r2-read", "r2-read-production", None, corr, Instant(clock()),
            ActorRef(ActorKind.APPLICATION, "r2-read"), InvocationStatus.PLANNED),
            use_case_id="application.read_production", payload={"production_ref": production, "version_ref": version},
            actor_context=UseCaseContext(corr))
        return inbound.invoke(request=request)
    return ConversationComposition(service, ConversationEndpoint(ConversationApplicationInbound(service),
                                    token_urlsafe(32)), ProductionEndpoint(read), store)
