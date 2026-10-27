"""Component-only synthetic identities/sources; not a startup/coverage substitute."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_codesign_contract import build_request
from backend.adapters.outbound.generation.openai.p0_finite_chain import FiniteChainBroker
from backend.adapters.outbound.generation.openai.p0_finite_policy import ROLES
from backend.adapters.outbound.generation.openai.p0_finite_ports import (
    FiniteGenerationPort,
    FinitePreLaunchGuard,
    FiniteReviewPort,
    FiniteTransportFactory,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    P1_HASHES,
    validate_permission,
)
from backend.adapters.outbound.generation.p0_codesign_agents import CoDesignGenerator
from backend.adapters.outbound.openai.contracts import OpenAIReasoningEffort
from backend.adapters.outbound.review.openai.adapter import OpenAIReviewAdapter
from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.agents.generation import GenerationCoordinator
from backend.agent_runtime.contracts import BudgetSpec
from backend.infrastructure.composition.factories.p0_codesign import P0CoDesignBinding
from backend.infrastructure.config.schemas.provider import (
    ModelProfileId,
    ProviderCode,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretValue,
)
from backend.infrastructure.filesystem import capture_secure_path
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity
from tests.finite_chain_325_fixture import Control, f
from tests.test_codesign_global_324 import Search, composition, simple
from tests.test_codesign_openai_contract_324 import model


def component(root, *, correction=False, scenario="complete"):
    root.mkdir()
    pin = P0NormalReceipt(root, "3" * 64)
    now = datetime.now(UTC)
    tariff = {
        "schema": "P0-NORMAL-TARIFF-1.0",
        "provider": "OPENAI",
        "model": "gpt-5.6-terra",
        "tier": "default",
        "input_usd_per_million": "2",
        "input_multiplier": "1.25",
        "output_usd_per_million": "12",
        "evidence_sha256": "e" * 64,
        "owner_admission_sha256": "f" * 64,
        "retrieved_at_utc": (now - timedelta(days=1)).isoformat(),
    }
    permission = {key: "a" * 64 for key in P1_HASHES}
    permission.update(
        schema="P0-PRODUCT-CREATE-PERMISSION-1.0",
        baseline_commit="1" * 40,
        receipt_root_sha256=pin.root_sha256,
        permission_namespace_sha256="3" * 64,
        tariff_sha256=sha(canonical(tariff)),
        issued_at_utc=(now - timedelta(minutes=1)).isoformat(),
        expires_at_utc=(now + timedelta(days=1)).isoformat(),
        allowed_families=["EXERCISE"],
        allowed_levels=["FIRST_STMG"],
        selected_admitted_sources_only=True,
        excluded_oracles_and_private_evidence=True,
        require_exact_local_consent=True,
        local_operator_delegation_accepted=True,
        provider="OPENAI",
        model="gpt-5.6-terra",
        endpoint="https://api.openai.com/v1/responses",
        reasoning="low",
        tier="default",
        max_output_tokens=4096,
        max_calls=1,
        count_calls=0,
        review_calls=0,
        modify_calls=0,
        retry=0,
        fallback="NONE",
        parallelism=1,
        per_call_ceiling_usd="0.14",
        cumulative_ceiling_usd="0.14",
        live_authorized=True,
        transfer_authorized=True,
    )
    validate_permission(
        permission,
        identities={k: permission[k] for k in P1_HASHES | {"baseline_commit"}},
        now=now,
        family="EXERCISE",
        level="FIRST_STMG",
    )
    ledger = P0ProductLedger(root=root, permission=permission)
    with ledger.locked():
        assert ledger.slots() == []
    lock = root / (ledger.prefix + "LOCK")
    native = capture_secure_path(lock, allowed_root=root)
    policy = {
        key: permission[key]
        for key in (
            "receipt_root_sha256",
            "package_sha256",
            "runtime_sha256",
            "source_tree_sha256",
            "institutional_catalog_sha256",
            "tariff_sha256",
            "tokenizer_manifest_sha256",
            "allowed_families",
            "allowed_levels",
            "issued_at_utc",
            "expires_at_utc",
        )
    }
    policy.update(
        schema="P0-FINITE-CHAIN-POLICY-2.0",
        normal_permission_sha256=sha(canonical(permission)),
        normal_envelope_sha256="b" * 64,
        campaign_namespace_sha256=permission["permission_namespace_sha256"],
        root_lock_sha256=sha(lock.read_bytes()),
        root_lock_identity_sha256=sha(canonical({"device": native.device, "inode": native.inode})),
        price_evidence_sha256="e" * 64,
        max_chains=1,
        maximum_effects=4,
        roles=list(ROLES),
        per_effect_ceiling_usd="0.14",
        cumulative_ceiling_usd="1.96",
        max_campaign_effects=14,
        retained_origins=[],
        max_output_tokens=4096,
        input_upper_tokens=36000,
        preview_minutes=15,
        authority_minutes=60,
        retry=0,
        fallback="NONE",
    )
    decision = {
        "schema": "P0-FINITE-CHAIN-ADOPTION-2.0",
        "status": "ADOPTED",
        "policy_sha256": sha(canonical(policy)),
        "normal_envelope_sha256": "b" * 64,
        "price_evidence_sha256": "e" * 64,
        "financial_evidence_admitted": True,
        "additional_finite_right_accepted": True,
        "historical_uncertainty_preserved": True,
    }
    dispatch, content = simple()
    service, _, _ = composition(dispatch, content)
    parent = service.records[dispatch["version_ref"]]
    control = Control(correction=correction, scenario=scenario)
    state = SimpleNamespace(
        clock=now,
        prepared=False,
        secret_reads=0,
        token_delta=0,
        fail_count_at=None,
        counts=0,
        on_count=lambda count: None,
    )

    def tokenizer(body):
        state.counts += 1
        state.on_count(state.counts)
        if state.fail_count_at == state.counts:
            raise ValueError("P0_CHAIN_SYNTHETIC_TOKENIZER_REFUSED")
        return {
            "schema": "P0-NORMAL-TOKENIZER-PROOF-1.0",
            "model": "gpt-5.6-terra",
            "recognition": "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER",
            "encoding": "o200k_base",
            "manifest_sha256": policy["tokenizer_manifest_sha256"],
            "request_sha256": sha(body),
            "model_mapping_sha256": "1" * 64,
            "encoding_sha256": "2" * 64,
            "all_string_values_and_keys_tokens": 1000 + state.token_delta,
            "serialized_json_tokens": 1100 + state.token_delta,
            "network_forbidden_during_count": True,
            "provider_calls": 0,
        }

    def prepare_secret():
        assert ledger._held_thread is None
        state.prepared = True
        state.secret_reads += 1

    class Resolver:
        def resolve(self, ref):
            assert state.prepared
            return ProviderSecretValue(f.FAKE_KEY)

    class NoExecution:
        def generate(self, *, request):
            raise AssertionError("PREPARATION_ONLY")

    m = model()

    def initial(request):
        prep = CoDesignGenerator.initial_preparation(
            parent=P0Production(object_data(request["production"])),
            evidence=object_data(request["evidence"]),
            objective=str(request["objective"]),
            direction=str(request["direction"]),
            identity=OperationIdentity("run:" + "0" * 32, "step:" + "0" * 32, None, "0" * 32),
        )
        return build_request(
            GenerationCoordinator(NoExecution()).prepare(request=prep).port_request, m
        )

    args = {
        "ledger": ledger,
        "policy": policy,
        "decision": decision,
        "enabled": True,
        "revalidate": lambda: None,
        "revalidate_authority": lambda: None,
        "source_reader": lambda r: [{"boundary": "DECLARED_SYNTHETIC_SOURCE_PORT"}],
        "initial_wire": initial,
        "tokenizer": tokenizer,
        "tariff": tariff,
        "prepare_credential": prepare_secret,
        "clock": lambda: state.clock,
    }
    broker = FiniteChainBroker(**args)
    control.binding = SimpleNamespace(broker=broker)
    transport = FiniteTransportFactory(broker, control)
    provider = ProviderProfileConfig(
        ProviderProfileId("openai.synthetic"),
        ProviderCode("openai"),
        ProviderCredentialRef("OPENAI_API_KEY"),
    )
    generation = FiniteGenerationPort(
        broker,
        OpenAIGenerationAdapter(
            provider_profile=provider,
            model_profile=m,
            secret_resolver=Resolver(),
            transport_factory=transport,
        ),
    )
    review = FiniteReviewPort(
        broker,
        OpenAIReviewAdapter(
            provider_profile=provider,
            model_profile=replace(
                m,
                model_profile_id=ModelProfileId("openai.synthetic.review"),
                supported_workloads=(ProviderWorkloadKind.REVIEW,),
            ),
            secret_resolver=Resolver(),
            transport_factory=transport,
            reasoning_effort=OpenAIReasoningEffort.LOW,
            service_tier="default",
        ),
    )
    service.codesign = P0CoDesignBinding(
        search=Search(),
        generation=generation,
        review=P0ReviewAdapter(review, authorize=lambda _: broker.active is not None),
        guard=FinitePreLaunchGuard(broker),
        envelope=BudgetSpec(max_retries=0, max_cost=Decimal(".56")),
        permission_scope_ref="scope:finite:" + broker.policy_sha,
        authorize=broker.authorize_chain,
    )
    service.finite_consent = broker
    service.fresh_codesign_evidence = lambda p: dispatch["evidence"]
    core = {
        "command_id": "b" * 32,
        "production_ref": parent.production_ref,
        "version_ref": parent.version_ref,
        "bundle_sha256": parent.sha256,
        "direction": "V2_TO_AI",
        "objective": "Clarifier le titre",
        "evidence_query": None,
    }
    request = service._finite_request(core)
    shown = broker.preview(request)
    command = {
        **core,
        "evidence_query": shown["evidence_query"],
        "preview_sha256": shown["preview_sha256"],
        "transfer_accepted": True,
        "cost_bound_accepted": True,
    }
    return SimpleNamespace(
        service=service,
        broker=broker,
        ledger=ledger,
        permission=permission,
        policy=policy,
        decision=decision,
        control=control,
        state=state,
        command=command,
        shown=shown,
        request=request,
        args=args,
        parent=parent,
    )
