"""Finite ON chain composed by the ordinary P0 launcher and existing owners."""

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.adapters.inbound.api.p0_pilot_command_followup import P0PilotCommandFollowup
from backend.adapters.outbound.generation.openai.adapter import OpenAIGenerationAdapter
from backend.adapters.outbound.generation.openai.p0_codesign_contract import build_request
from backend.adapters.outbound.generation.openai.p0_finite_chain import FiniteChainBroker
from backend.adapters.outbound.generation.openai.p0_finite_policy import validate_policy
from backend.adapters.outbound.generation.openai.p0_finite_ports import (
    FiniteGenerationPort,
    FinitePreLaunchGuard,
    FiniteReviewPort,
    FiniteTransportFactory,
)
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, closed, sha
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import (
    P0ContinuityProductLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.generation.openai.p0_product_policy import validate_source_receipts
from backend.adapters.outbound.generation.p0_codesign_agents import CoDesignGenerator
from backend.adapters.outbound.openai import OpenAISDKResponsesTransportFactory
from backend.adapters.outbound.openai.contracts import OpenAIReasoningEffort, OpenAIResponsesRequest
from backend.adapters.outbound.review.openai.adapter import OpenAIReviewAdapter
from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.agents.generation import GenerationCoordinator, GenerationPort
from backend.agent_runtime.contracts import BudgetSpec
from backend.infrastructure.composition.factories.p0_codesign import P0CoDesignBinding
from backend.infrastructure.composition.factories.p0_normal_profile import (
    _ROOT,
    LocalTokenizerHelper,
    OpenAIEnvironmentSecretResolver,
    P0NormalProductComposition,
    build_p0_secret_resolver,
    read_descriptor,
    verify_source_package,
)
from backend.infrastructure.composition.factories.p0_product_consent import product_source_reader
from backend.infrastructure.config.schemas.provider import (
    ModelCode,
    ModelContextLimits,
    ModelProfileConfig,
    ModelProfileId,
    ProviderCode,
    ProviderInvocationLimits,
    ProviderProfileConfig,
    ProviderProfileId,
    ProviderWorkloadKind,
)
from backend.infrastructure.config.secrets.provider import (
    ProviderCredentialRef,
    ProviderSecretError,
    ProviderSecretValue,
)
from backend.infrastructure.filesystem import (
    capture_secure_path,
    hash_file_nofollow,
    read_file_nofollow,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from backend.modules.work_orchestration.contracts.dto.operation_identity import OperationIdentity


class FiniteChainComposition:
    def __init__(
        self, *, normal: P0NormalProductComposition, path: Path, expected_sha256: str, mode: str
    ) -> None:
        if mode not in {"enabled", "disabled"} or normal.mode != "evidence-only":
            raise ValueError("P0_CHAIN_STARTUP_MODE")
        self.normal, self.path, self.expected_sha256, self.mode = (
            normal,
            path,
            expected_sha256,
            mode,
        )
        self.broker: FiniteChainBroker | None = None
        self.document = cast(
            dict[str, object], read_descriptor({"path": str(path), "sha256": expected_sha256})
        )
        closed(
            self.document,
            {
                "schema",
                "normal_envelope_sha256",
                "policy",
                "decision",
                "current_source_profile",
                "historical_application_root",
            },
            "P0_CHAIN_STARTUP_FIELDS",
        )
        if (
            self.document["schema"] != "P0-FINITE-CHAIN-STARTUP-2.0"
            or self.document["normal_envelope_sha256"] != normal.envelope_sha256
            or Path(str(self.document["historical_application_root"])) != normal.application_root
        ):
            raise ValueError("P0_CHAIN_STARTUP_BINDING")
        self.policy = cast(dict[str, object], read_descriptor(self.document["policy"]))
        self.decision = cast(dict[str, object], read_descriptor(self.document["decision"]))
        self.source_profile = cast(
            dict[str, object], read_descriptor(self.document["current_source_profile"])
        )
        closed(
            self.source_profile,
            {"schema", "baseline_commit", "package", "source_manifest"},
            "P0_CHAIN_CURRENT_SOURCE_FIELDS",
        )
        if self.source_profile["schema"] != "P0-FINITE-CURRENT-SOURCE-1.0":
            raise ValueError("P0_CHAIN_CURRENT_SOURCE_FIELDS")
        self._tokenizer = LocalTokenizerHelper(
            normal.tokenizer_manifest,
            str(normal.permission["tokenizer_manifest_sha256"]),
            application_root=_ROOT,
        )
        self._resolver: OpenAIEnvironmentSecretResolver | None = None
        self.credential_ref = ProviderCredentialRef(str(normal.profile["credential_ref"]))
        if mode == "enabled" and self.decision.get("status") != "ADOPTED":
            raise ValueError("P0_CHAIN_ADOPTION_REQUIRED")
        self._helper = _ROOT / "tools/p0-tokenize-local.py"
        source_manifest = cast(
            Mapping[str, object], read_descriptor(self.source_profile["source_manifest"])
        )
        self._helper_sha256 = str(
            cast(Mapping[str, object], source_manifest["files"])["tools/p0-tokenize-local.py"]
        )
        self._helper_identity = capture_secure_path(self._helper, allowed_root=_ROOT)

    def authority_identities(self) -> None:
        normal = self.normal
        if (
            sha(read_file_nofollow(self.path, allowed_root=self.path.parent, maximum_bytes=32000))
            != self.expected_sha256
        ):
            raise ValueError("P0_CHAIN_STARTUP_CHANGED")
        if canonical(read_descriptor(self.document["policy"])) != canonical(
            self.policy
        ) or canonical(read_descriptor(self.document["decision"])) != canonical(self.decision):
            raise ValueError("P0_CHAIN_ADOPTED_OBJECT_CHANGED")
        read_descriptor({"path": str(normal.path), "sha256": normal.envelope_sha256})
        for key in ("permission", "decision"):
            read_descriptor(normal.envelope[key])
        for key in (
            "operator_delegation",
            "source_admission_manifest",
            "tokenizer_manifest",
            "tariff",
        ):
            read_descriptor(
                normal.profile[key], canonical_required=key != "source_admission_manifest"
            )
        if canonical(read_descriptor(self.document["current_source_profile"])) != canonical(
            self.source_profile
        ):
            raise ValueError("P0_CHAIN_CURRENT_SOURCE_CHANGED")
        if (
            cast(Mapping[str, object], self.source_profile["package"])["sha256"]
            != self.policy["package_sha256"]
            or cast(Mapping[str, object], self.source_profile["source_manifest"])["sha256"]
            != self.policy["source_tree_sha256"]
        ):
            raise ValueError("P0_CHAIN_CURRENT_SOURCE_BINDING")
        if self.policy["normal_envelope_sha256"] != normal.envelope_sha256:
            raise ValueError("P0_CHAIN_NORMAL_BINDING")
        price = cast(bytes, read_descriptor(normal.profile["tariff_evidence"], json_document=False))
        if sha(price) != self.policy["price_evidence_sha256"] or normal.tariff[
            "evidence_sha256"
        ] != sha(price):
            raise ValueError("P0_CHAIN_TARIFF_EVIDENCE_CHANGED")

    def revalidate(self) -> None:
        self.authority_identities()
        self.normal.identities()
        # Identical root AND exact descriptors share the already executed guard.
        if not (
            self.normal.application_root == _ROOT
            and all(
                canonical(self.normal.profile[key]) == canonical(self.source_profile[key])
                for key in ("package", "source_manifest")
            )
        ):
            verify_source_package(self.source_profile, application_root=_ROOT)

    def tokenizer(self, body: bytes) -> Mapping[str, object]:
        if (
            not self._helper_identity.same_identity(
                capture_secure_path(self._helper, allowed_root=_ROOT)
            )
            or hash_file_nofollow(self._helper, allowed_root=_ROOT) != self._helper_sha256
        ):
            raise ValueError("P0_CHAIN_TOKENIZER_HELPER_CHANGED")
        read_descriptor(self.normal.profile["tokenizer_manifest"])
        result = self._tokenizer(body)
        if (
            not self._helper_identity.same_identity(
                capture_secure_path(self._helper, allowed_root=_ROOT)
            )
            or hash_file_nofollow(self._helper, allowed_root=_ROOT) != self._helper_sha256
        ):
            raise ValueError("P0_CHAIN_TOKENIZER_HELPER_CHANGED")
        return result

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        normal = self.normal
        # A single ledger object owns CREATE and finite roles in the same campaign.
        ledger = (
            P0ContinuityProductLedger(
                root=normal.root,
                permission=normal.permission,
                chain_loader=normal._continuity_chain,
                broker_identity=self,
                clock=lambda: datetime.now(UTC),
            )
            if normal.continuity
            else P0ProductLedger(root=normal.root, permission=normal.permission)
        )
        validate_policy(
            self.policy,
            self.decision,
            normal.permission,
            now=datetime.now(UTC),
            proposed=self.decision["status"] == "PROPOSED",
        )
        source_reader = (
            None
            if self.mode == "disabled"
            else product_source_reader(
                target=normal.target,
                admission=normal.local_context or normal.admission,
                institutional_resolver=service.institutional_resolver
                if normal.local_context is not None
                else None,
            )
        )

        def fresh(parent: P0Production) -> Mapping[str, str]:
            from backend.infrastructure.composition.factories.r6_all_notions import (
                exact_notion_evidence,
            )

            found: dict[str, str] = {}
            selection = object_data(parent.context.data.get("institutional", {}))
            notions = selection.get("notion_refs", ())
            if not isinstance(notions, (tuple, list)):
                raise ValueError("P0_CHAIN_NOTION_SELECTION_REQUIRED")
            with exact_notion_evidence(normal.target) as inbound:
                passages = [
                    p
                    for notion in notions
                    for p in items(inbound.inspect(str(notion))["items"], 256)
                ]
            for ref in items(parent.data["references"], 8):
                matched = [
                    p
                    for p in passages
                    if p["object_ref"] == ref["source_ref"]
                    and p["passage_ref"] == ref["locator"]
                    and p["version_or_checksum"] == ref["checksum_or_version"]
                    and p["excerpt_truncated"] is False
                ]
                if len(matched) != 1 or not isinstance(matched[0]["excerpt"], str):
                    raise ValueError("P0_CHAIN_FRESH_EVIDENCE_REQUIRED")
                found[str(ref["evidence_id"])] = str(matched[0]["excerpt"])
            return found

        def sources(request: Mapping[str, object]) -> list[dict[str, object]]:
            if source_reader is None:
                raise ValueError("P0_CHAIN_SOURCE_ADOPTION_REQUIRED")
            parent = object_data(request["production"])
            receipts = source_reader(
                {
                    "context": parent["context"],
                    "references": parent["references"],
                    "evidence": request["evidence"],
                }
            )
            validate_source_receipts(
                normal.permission, receipts, local_context_adoption=normal.local_context_adoption
            )
            return receipts

        provider = (
            ProviderProfileConfig(
                ProviderProfileId("openai.p0.finite"),
                ProviderCode("openai"),
                # Same logical credential as the adopted normal profile.
                self.credential_ref,
            )
            if self.mode == "enabled"
            else None
        )
        model = ModelProfileConfig(
            ModelProfileId("openai.p0.finite.generation"),
            ProviderProfileId("openai.p0.finite"),
            ModelCode("gpt-5.6-terra"),
            ModelContextLimits(128000, 100000, 4096),
            ProviderInvocationLimits(
                max_attempts=1, call_timeout_milliseconds=120000, max_output_tokens=4096
            ),
            (ProviderWorkloadKind.GENERATION, ProviderWorkloadKind.CORRECTION),
            structured_output_required=True,
        )

        # Preparing the exact first body uses the same coordinator/mapping as AG-03.
        # This boundary must never be invoked during pure preparation.
        class NoExecution:
            def generate(self, *, request: object) -> object:
                raise ValueError("P0_CHAIN_PREPARATION_IS_NOT_EXECUTION")

        def initial(request: Mapping[str, object]) -> OpenAIResponsesRequest:
            parent = P0Production(object_data(request["production"]))
            family = parent.context.question_mode or parent.context.resource_type
            if family not in cast(
                list[str], self.policy["allowed_families"]
            ) or parent.context.data["level"] not in cast(list[str], self.policy["allowed_levels"]):
                raise ValueError("P0_CHAIN_CONTEXT_SCOPE")
            prep = CoDesignGenerator.initial_preparation(
                parent=parent,
                evidence=object_data(request["evidence"]),
                objective=str(request["objective"]),
                direction=str(request["direction"]),
                identity=OperationIdentity("run:" + "0" * 32, "step:" + "0" * 32, None, "0" * 32),
            )
            prepared = GenerationCoordinator(cast(GenerationPort, NoExecution())).prepare(
                request=prep
            )
            return build_request(prepared.port_request, model)

        def credential() -> None:
            if self.mode != "enabled":
                raise ValueError("P0_CHAIN_ENVIRONMENT_CREDENTIAL_REQUIRED")
            if self._resolver is None:
                selected = build_p0_secret_resolver(
                    self.credential_ref, credential_source="OPENAI_API_KEY"
                )
                if not isinstance(selected, OpenAIEnvironmentSecretResolver):
                    raise ValueError("P0_CHAIN_ENVIRONMENT_CREDENTIAL_REQUIRED")
                self._resolver = selected
            try:
                self._resolver.resolve(self.credential_ref)
            except ProviderSecretError:
                raise ValueError("P0_CHAIN_OPENAI_API_KEY_MISSING_OR_INVALID") from None

        broker = FiniteChainBroker(
            ledger=ledger,
            policy=self.policy,
            decision=self.decision,
            enabled=self.mode == "enabled",
            revalidate=self.revalidate,
            revalidate_authority=self.authority_identities,
            source_reader=sources,
            initial_wire=initial,
            tokenizer=self.tokenizer,
            tariff=normal.tariff,
            prepare_credential=credential,
        )
        self.broker = broker
        # Complete source guards precede this pinned helper probe.
        self.tokenizer(
            canonical({"model": "gpt-5.6-terra", "input": "FINITE LOCAL READINESS PROBE"})
        )
        service.finite_consent, service.fresh_codesign_evidence = broker, fresh
        endpoint.codesign_command_read = broker.observe
        endpoint.normal_mode = "FINITE_CHAIN_ONLY"
        endpoint.consent_execute = None
        endpoint.generation_bound = endpoint.review_bound = False
        endpoint.codesign_binding = (
            "FINITE_CHAIN_ENABLED" if self.mode == "enabled" else "FINITE_CHAIN_DISARMED"
        )
        endpoint.codesign_profile = {
            "startup_sha256": self.expected_sha256,
            "policy_sha256": broker.policy_sha,
            "decision_sha256": broker.decision_sha,
            "mode": self.mode,
            "adoption_status": self.decision["status"],
            **{
                key: self.policy[key]
                for key in (
                    "package_sha256",
                    "source_tree_sha256",
                    "runtime_sha256",
                    "institutional_catalog_sha256",
                    "tariff_sha256",
                    "tokenizer_manifest_sha256",
                    "root_lock_sha256",
                    "root_lock_identity_sha256",
                )
            },
            "historical_create_binding": "NONE",
            "startup_started_authority": False,
        }
        if self.mode == "disabled":
            return
        assert provider is not None
        transport = FiniteTransportFactory(
            broker,
            OpenAISDKResponsesTransportFactory(r2_destination=True, environment_key_allowed=True),
        )
        owner = self

        class PreparedFiniteCredential:
            def resolve(self, credential_ref: ProviderCredentialRef) -> ProviderSecretValue:
                if owner._resolver is None:
                    raise ValueError("P0_CHAIN_CREDENTIAL_NOT_PREPARED")
                return owner._resolver.resolve_prepared(credential_ref)

        resolver = PreparedFiniteCredential()
        generation = FiniteGenerationPort(
            broker,
            OpenAIGenerationAdapter(
                provider_profile=provider,
                model_profile=model,
                secret_resolver=resolver,
                transport_factory=transport,
            ),
        )
        review_model = ModelProfileConfig(
            ModelProfileId("openai.p0.finite.review"),
            provider.profile_id,
            model.model_code,
            model.context_limits,
            model.invocation_limits,
            (ProviderWorkloadKind.REVIEW,),
            structured_output_required=True,
        )
        review = FiniteReviewPort(
            broker,
            OpenAIReviewAdapter(
                provider_profile=provider,
                model_profile=review_model,
                secret_resolver=resolver,
                transport_factory=transport,
                reasoning_effort=OpenAIReasoningEffort.LOW,
                service_tier="default",
            ),
        )
        from backend.infrastructure.composition.factories.p0_local_search import (
            ScopedApplicationSearch,
        )

        binding = P0CoDesignBinding(
            search=ScopedApplicationSearch(normal.target),
            generation=generation,
            review=P0ReviewAdapter(review, authorize=lambda _: broker.active is not None),
            guard=FinitePreLaunchGuard(broker),
            envelope=BudgetSpec(
                max_retries=0, max_cost=Decimal(str(self.policy["per_effect_ceiling_usd"])) * 4
            ),
            permission_scope_ref="scope:finite:" + broker.policy_sha,
            authorize=broker.authorize_chain,
        )
        service.codesign = binding
        endpoint.codesign_command_followup = P0PilotCommandFollowup(
            service.execute,
            finite=True,
            retained_reader=lambda command: dict(
                broker.observe(command)
                or {"state": "LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE", "command_id": command}
            ),
        )

    @property
    def generation(self) -> P0GenerationPort | None:
        return None  # The historical CREATE permission is evidence, never rebound.

    def close(self) -> None:
        if self._resolver is not None:
            self._resolver.close()
        self.normal.close()
