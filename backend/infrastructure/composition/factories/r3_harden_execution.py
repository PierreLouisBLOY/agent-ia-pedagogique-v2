"""Explicit one-shot execution boundary; imports and configuration grant no authority."""

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from threading import Lock

from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
from backend.adapters.outbound.openai.contracts import (
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponsesTransportFactory,
)
from backend.infrastructure.composition.factories.r3_harden_profile import validate_harden_profile
from backend.infrastructure.composition.factories.r3_harden_serialization import (
    r3_harden_count_parameters,
    r3_harden_request_parameters,
)
from backend.infrastructure.config.schemas.provider import ModelProfileConfig, ProviderProfileConfig
from backend.infrastructure.config.secrets.provider import ProviderSecretResolver
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping


@dataclass
class HardenExecutionEvidence:
    """Private capture exported before close; raw output never enters business receipts."""

    state: str = "NOT_DISPATCHED"
    response: OpenAIResponsesResponse | None = field(default=None, repr=False)
    parsing: str = "NOT_RUN"
    _reserved: bool = field(default=False, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)


def validate_harden_grant(
    grant: Mapping[str, object],
    *,
    expected_grant_sha256: str,
    model_profile: ModelProfileConfig,
    baseline_commit: str,
    runner_sha256: str,
    pricing_sha256: str,
    now: datetime,
) -> None:
    validate_harden_profile(model_profile)
    required = {
        "purpose",
        "baseline_commit",
        "runner_sha256",
        "pricing_sha256",
        "profile_sha256",
        "request_sha256",
        "count_sha256",
        "projection_sha256",
        "exact_input_tokens",
        "input_microusd_per_million",
        "output_microusd_per_million",
        "ceiling_microusd",
        "issued_at",
        "expires_at",
        "max_calls",
        "retry",
        "fallback",
        "transfer_authorized",
        "execution_authorized",
        "receipt_namespace",
    }
    data = object_data(grant, required)
    cost = model_profile.invocation_limits.max_cost
    if (
        fingerprint(data) != expected_grant_sha256
        or data["purpose"] != "HARDEN_DOSSIER_3_ONCE"
        or data["baseline_commit"] != baseline_commit
        or data["runner_sha256"] != runner_sha256
        or data["pricing_sha256"] != pricing_sha256
        or data["profile_sha256"] != fingerprint(asdict(model_profile))
        or data["execution_authorized"] is not True
        or data["transfer_authorized"] is not True
        or type(data["max_calls"]) is not int
        or data["max_calls"] != 1
        or data["retry"] is not False
        or data["fallback"] is not None
        or cost is None
        or type(data["ceiling_microusd"]) is not int
        or data["ceiling_microusd"] != cost.amount_microunits
    ):
        raise ValueError("R3_HARDEN_NOT_AUTHORIZED")
    import re

    for key in (
        "runner_sha256",
        "pricing_sha256",
        "profile_sha256",
        "request_sha256",
        "count_sha256",
        "projection_sha256",
        "receipt_namespace",
    ):
        value = data[key]
        if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("R3_HARDEN_NOT_AUTHORIZED")
    issued, expiry = (
        datetime.fromisoformat(str(data["issued_at"])),
        datetime.fromisoformat(str(data["expires_at"])),
    )
    if (
        issued.tzinfo is None
        or expiry.tzinfo is None
        or now.tzinfo is None
        or not issued <= now < expiry
        or not 0 < (expiry - issued).total_seconds() <= 7200
    ):
        raise ValueError("R3_HARDEN_NOT_AUTHORIZED")
    for key in ("exact_input_tokens", "input_microusd_per_million", "output_microusd_per_million"):
        number = data[key]
        if type(number) is not int or number <= 0:
            raise ValueError("R3_HARDEN_NOT_AUTHORIZED")
    inputs = int(str(data["exact_input_tokens"]))
    numerator = inputs * int(str(data["input_microusd_per_million"])) + 8192 * int(
        str(data["output_microusd_per_million"])
    )
    if inputs > 32768 or (numerator + 999999) // 1000000 > cost.amount_microunits:
        raise ValueError("R3_HARDEN_BUDGET_REJECTED")


def build_harden_adapter(
    *,
    provider_profile: ProviderProfileConfig,
    model_profile: ModelProfileConfig,
    secret_resolver: ProviderSecretResolver,
    transport_factory: OpenAIResponsesTransportFactory,
    grant: Mapping[str, object],
    expected_grant_sha256: str,
    baseline_commit: str,
    runner_sha256: str,
    pricing_sha256: str,
    clock: Callable[[], datetime],
    evidence: HardenExecutionEvidence,
    reserve_once: Callable[[str], None],
    capture: Callable[[HardenExecutionEvidence], None],
) -> OpenAIGenerationAdapter:
    """Injected reserve_once must durably refuse reuse across processes before dispatch."""
    validate_harden_profile(model_profile, provider_profile)
    sealed = freeze_safe_mapping(grant)

    def check() -> None:
        validate_harden_grant(
            sealed,
            expected_grant_sha256=expected_grant_sha256,
            model_profile=model_profile,
            baseline_commit=baseline_commit,
            runner_sha256=runner_sha256,
            pricing_sha256=pricing_sha256,
            now=clock(),
        )

    check()
    if getattr(transport_factory, "r2_destination", None) is not True:
        raise ValueError("R3_HARDEN_DESTINATION_REJECTED")
    # Explicit factory injection; no concrete SDK client, environment or resolver is created here.
    adapter = OpenAIGenerationAdapter(
        provider_profile=provider_profile,
        model_profile=model_profile,
        secret_resolver=secret_resolver,
        transport_factory=transport_factory,
    )

    def before(request: OpenAIResponsesRequest) -> None:
        import json

        with evidence._lock:
            check()
            body = r3_harden_request_parameters(request, model_profile=model_profile)
            counted = r3_harden_count_parameters(request, model_profile=model_profile)
            projection = json.loads(request.input_json)
            if (
                evidence._reserved
                or fingerprint(body) != sealed["request_sha256"]
                or fingerprint(counted) != sealed["count_sha256"]
                or fingerprint(projection) != sealed["projection_sha256"]
            ):
                raise ValueError("R3_HARDEN_NOT_AUTHORIZED")
            # Consume before a secret or a transport can be resolved. Never undo on error.
            evidence._reserved = True
            reserve_once(str(sealed["receipt_namespace"]))
            evidence.state = "RESERVED"
            capture(evidence)

    def dispatch() -> None:
        check()
        if evidence.state != "RESERVED":
            raise ValueError("R3_HARDEN_NOT_AUTHORIZED")
        evidence.state = "DISPATCH_POSSIBLE"
        capture(evidence)

    def response(value: OpenAIResponsesResponse) -> None:
        evidence.response, evidence.state = value, "RESPONSE_RECEIVED"
        capture(evidence)

    def parsing(value: str) -> None:
        evidence.parsing = value
        capture(evidence)

    adapter.bind_conversation_execution(
        before_request=before, on_dispatch=dispatch, on_response=response, on_parsing=parsing
    )
    return adapter
