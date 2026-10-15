"""Explicit profile4 or readonly inspection plan, never implicit live authority."""

from __future__ import annotations

import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from backend.adapters.inbound.application.p1_campaign_inspection import P1CampaignInspectionInbound
from backend.adapters.outbound.generation.openai.p0_content import build_p0_content_request
from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    P0NormalReceipt,
    decode,
    pinned_receipt_root,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import (
    EVENT_FIELDS,
    NODE_FIELDS,
    BoundChain,
    OriginProof,
    allow_own_transition,
    bind_chain,
    mapping,
    reject_orphan_namespaces,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_ledger import NORMAL_EVENTS
from backend.adapters.outbound.generation.openai.p0_product_policy import (
    P1_HASHES,
    validate_permission,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected import (
    P0RejectedProductGenerationAdapter,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
    bind_chain_v2,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    target as selected_attempt,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_ledger import (
    P0RejectedContinuityLedger,
)
from backend.core_contracts.outcome import ApplicationFailureKind
from backend.infrastructure.composition.factories.p0_normal_profile import (
    LocalTokenizerHelper,
    MaskedLocalSecretResolver,
    read_descriptor,
    strict_document,
    verify_source_package,
    windows_operator,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import (
    absolute,
    descriptor,
)
from backend.infrastructure.composition.factories.p0_rejected_profile_contract import (
    validate_external_adoption,
)
from backend.infrastructure.composition.factories.p0_rejected_readset import (
    NativeP0RejectedReadPhases,
)
from backend.infrastructure.filesystem import capture_secure_path, read_file_nofollow
from backend.modules.pedagogical_design.ports.outbound.p0_generation import P0GenerationPort
from backend.modules.work_orchestration.application.queries.inspect_p1_campaign import (
    InspectP1Campaign,
)
from backend.modules.work_orchestration.application.queries.p0_local_reference_context import (
    ReadP0LocalReferenceContext,
)
from backend.modules.work_orchestration.application.queries.p0_source_admission import (
    ReadP0SourceAdmission,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionPortError,
    P1CampaignInspectionRequest,
)
from backend.shared_kernel.correlation import CorrelationId

if TYPE_CHECKING:
    from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
    from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
    from backend.modules.work_orchestration.application.services.p0_creation import (
        P0CreationService,
    )

_ROOT = Path(__file__).resolve().parents[4]
PLAN_FIELDS = {
    "schema",
    "operation",
    "source_manifest",
    "package",
    "baseline_commit",
    "source_tree",
    "origin_tip_permission_sha256",
    "ancestors",
    "original_anchor",
    "proposal",
    "owner_orientation_adoption",
    "owner_diagnostic",
    "expected_operator_delegation",
    "saved_root_native_identity",
    "receipt_root_native_identity",
    "target_runtime",
    "target_attempt",
    "issued_at_utc",
    "expires_at_utc",
    "ledger_writes_allowed",
    "provider_calls_allowed",
}


@dataclass(frozen=True)
class ValidatedInspectionPlan:
    plan: Mapping[str, object]
    sha256: str
    chain: BoundChain


def _document(path: Path) -> tuple[dict[str, object], str]:
    absolute(str(path))
    with pinned_receipt_root(path.parent):
        raw = read_file_nofollow(path, allowed_root=path.parent, maximum_bytes=256_000)
    return strict_document(raw), sha(raw)


def _native(path: Path) -> dict[str, object]:
    identity = capture_secure_path(path, allowed_root=path)
    if not identity.is_directory:
        raise ValueError("P0_REJECTED_EXISTING_NATIVE_STORE_REQUIRED")
    return {"path": str(path), "device": identity.device, "inode": identity.inode}


def _proof(envelope: Mapping[str, object], *, saved_root: Path) -> OriginProof:
    profile = mapping(envelope["profile"], "P0_REJECTED_PROFILE")
    permission = cast(dict[str, object], read_descriptor(envelope["permission"]))
    decision = cast(dict[str, object], read_descriptor(envelope["decision"]))
    if (
        permission["baseline_commit"] != profile["baseline_commit"]
        or permission["source_tree_sha256"] != descriptor(profile["source_manifest"])["sha256"]
        or permission["package_sha256"] != descriptor(profile["package"])["sha256"]
    ):
        raise ValueError("P0_REJECTED_SOURCE_PERMISSION_BINDING")
    delegation = cast(dict[str, object], read_descriptor(profile["operator_delegation"]))
    for key in ("source_manifest", "source_admission_manifest", "tokenizer_manifest", "tariff"):
        read_descriptor(profile[key], canonical_required=key != "source_admission_manifest")
    for key in ("package", "tariff_evidence"):
        read_descriptor(profile[key], json_document=False)
    tariff = cast(Mapping[str, object], read_descriptor(profile["tariff"]))
    if tariff["evidence_sha256"] != descriptor(profile["tariff_evidence"])["sha256"]:
        raise ValueError("P0_REJECTED_TARIFF_EVIDENCE_BINDING")
    if profile["schema"] != "P0-NORMAL-PROFILE-1.0":
        read_descriptor(profile["local_reference_context_manifest"])
    return OriginProof(
        permission,
        envelope,
        decision,
        delegation,
        windows_operator(),
        sha(canonical(_native(saved_root))),
    )


def _ancestors(
    nodes: object, saved_root: Path
) -> tuple[list[OriginProof], dict[str, Mapping[str, object]]]:
    if not isinstance(nodes, list) or not nodes or len(nodes) > 14:
        raise ValueError("P0_REJECTED_EXACT_ANCESTORS_REQUIRED")
    proofs: list[OriginProof] = []
    manifests: dict[str, Mapping[str, object]] = {}
    for value in nodes:
        node = mapping(value, "P0_REJECTED_NODE")
        closed(node, NODE_FIELDS, "P0_REJECTED_NODE_FIELDS")
        envelope = cast(dict[str, object], read_descriptor(node["profile_envelope"]))
        proof = _proof(envelope, saved_root=saved_root)
        if (
            node["permission_sha256"] != proof.permission_sha256
            or canonical(node["permission"]) != canonical(envelope["permission"])
            or canonical(node["owner_decision"]) != canonical(envelope["decision"])
        ):
            raise ValueError("P0_REJECTED_ANCESTOR_DESCRIPTOR_BINDING")
        profile = mapping(envelope["profile"], "P0_REJECTED_PROFILE")
        if profile["schema"] in {"P0-NORMAL-PROFILE-3.0", "P0-NORMAL-PROFILE-4.0"}:
            manifests[proof.permission_sha256] = cast(
                dict[str, object], read_descriptor(profile["continuity_manifest"])
            )
            read_descriptor(profile["continuity_anchor"])
            read_descriptor(profile["source_admission_owner_decision"])
        proofs.append(proof)
    return proofs, manifests


def _anchor(value: object) -> dict[str, object]:
    anchor = cast(dict[str, object], read_descriptor(value))
    read_descriptor(anchor["implementation_decision"], canonical_required=False)
    read_descriptor(anchor["conditions"], json_document=False)
    for witness in cast(list[Mapping[str, object]], anchor["required_historical_reservations"]):
        read_descriptor(witness["metadata_evidence"], canonical_required=False)
    return anchor


def _external(
    path: Path, *, components: Mapping[str, object], operation: str
) -> Mapping[str, object]:
    control, _ = _document(path)
    book = cast(dict[str, object], read_descriptor(control["book"]))
    owner = cast(
        dict[str, object], read_descriptor(control["owner_evidence"], canonical_required=False)
    )
    # Protected trusted control, outside HTTP and all adopted components. The
    # expected raw human capture SHA is separate from that capture's contents.
    expected = str(control["expected_owner_evidence_sha256"])
    validate_external_adoption(
        control,
        book=book,
        owner_evidence=owner,
        owner_raw_sha256=str(descriptor(control["owner_evidence"])["sha256"]),
        expected_owner_raw_sha256=expected,
        components=components,
        operation=operation,
    )
    return control


def _orientation(plan: Mapping[str, object], selected: Mapping[str, object]) -> None:
    owner = cast(
        Mapping[str, object],
        read_descriptor(plan["owner_orientation_adoption"], canonical_required=False),
    )
    p1 = mapping(owner.get("p1"), "P0_REJECTED_OWNER_ORIENTATION_REQUIRED")
    if (
        owner.get("schema") != "LU-OWNER-P1-FAILED-DISPOSITION-M02-EXTENSION-ADOPTIONS-1.0"
        or owner.get("source") != "DIRECT_HUMAN_ASYNC_QUESTION_REPLY"
        or not isinstance(owner.get("question_call_id"), str)
        or not owner["question_call_id"]
        or owner.get("human_cryptographic_signature_claimed") is not False
        or p1.get("answer_exact") != "Adopter cette disposition bornée"
        or p1.get("state") != "ADOPTED_LIMITED"
        or p1.get("failed_request_sha256") != selected["request_sha256"]
        or p1.get("retained_reserved_usd") != selected["reserved_usd"]
        or any(
            p1.get(key) is not False
            for key in (
                "real_ledger_mutation",
                "activation",
                "new_provider_call",
                "grant_transfer",
                "quota_reset",
            )
        )
    ):
        raise ValueError("P0_REJECTED_PRIOR_ORIENTATION_BINDING")
    if "proposal" in plan:
        read_descriptor(plan["proposal"], json_document=False)
        if p1.get("proposal_sha256") != descriptor(plan["proposal"])["sha256"]:
            raise ValueError("P0_REJECTED_PRIOR_PROPOSAL_BINDING")
    diagnostic = cast(
        Mapping[str, object], read_descriptor(plan["owner_diagnostic"], canonical_required=False)
    )
    stages = diagnostic.get("stages")
    if (
        diagnostic.get("schema") != "LU-P1-OWNER-PURE-REJECTION-RULE-1.0"
        or any(
            diagnostic.get(source) != selected[key]
            for source, key in (
                ("request_sha256", "request_sha256"),
                ("request_bytes", "request_bytes"),
                ("permission_sha256", "permission_sha256"),
                ("slot_namespace_sha256", "namespace_sha256"),
                ("output_text_sha256", "output_text_sha256"),
            )
        )
        or diagnostic.get("diagnosis") != "PURE_LOCAL_REJECTION_REPRODUCED"
        or diagnostic.get("raw_output_text_disclosed") is not False
        or not isinstance(stages, list)
        or len(
            [
                stage
                for stage in stages
                if isinstance(stage, Mapping)
                and stage.get("stage") == "BIND_AND_VALIDATE_COURSE"
                and stage.get("status") == "REJECTED"
                and stage.get("code") == "P0_RICH_COURSE_NOTION_UNKNOWN"
            ]
        )
        != 1
    ):
        raise ValueError("P0_REJECTED_PRIOR_DIAGNOSTIC_BINDING")


class _InspectionReader:
    def __init__(self, loader: object, *, identity: str, bootstrap: bool) -> None:
        self.loader, self.identity, self.bootstrap_mode = loader, identity, bootstrap

    def inspect(
        self, *, inspection_ref: str, expected_plan_or_profile_sha256: str
    ) -> Mapping[str, object]:
        if (
            inspection_ref != "p1-inspection:" + self.identity
            or expected_plan_or_profile_sha256 != self.identity
        ):
            raise P1CampaignInspectionPortError(ApplicationFailureKind.AF_MAPPING_CORRUPTION)
        try:
            ledger = self.loader()  # type: ignore[operator]
            return cast(
                Mapping[str, object],
                ledger.bootstrap() if self.bootstrap_mode else ledger.snapshot(),
            )
        except ValueError as error:
            kind = ApplicationFailureKind.AF_MAPPING_CORRUPTION
            if str(error) == "P0_PRODUCT_CONCURRENT_DISPATCH":
                kind = ApplicationFailureKind.AF_CONCURRENCY
            elif "OUTCOME_RECONCILIATION_REQUIRED" in str(
                error
            ) or "EXACT_EVENT_SET_REQUIRED" in str(error):
                kind = ApplicationFailureKind.AF_COMMIT_OUTCOME_UNKNOWN
            raise P1CampaignInspectionPortError(kind) from None
        except OSError:
            raise P1CampaignInspectionPortError(
                ApplicationFailureKind.AF_PORT_UNAVAILABLE
            ) from None


class _ReadOnlyBinding:
    generation: P0GenerationPort | None = None

    def _bind_inspection(self, endpoint: P0CreationEndpoint, reader: _InspectionReader) -> None:
        logical = "p1-inspection:" + reader.identity
        inbound = P1CampaignInspectionInbound(
            InspectP1Campaign(
                reader, inspection_ref=logical, expected_plan_or_profile_sha256=reader.identity
            )
        )
        request = P1CampaignInspectionRequest(logical, reader.identity)

        def snapshot() -> dict[str, object]:
            outcome = inbound.inspect(
                request=request, correlation_id=CorrelationId("P1_INSPECTION_LOCAL")
            )
            if not outcome.success or outcome.data is None:
                raise ValueError("P0_REJECTED_APPLICATION_INSPECTION_REFUSED")
            return outcome.data.as_dict()

        endpoint.campaign_snapshot = snapshot

    def close(self) -> None:
        pass


class P0RejectedInspectionComposition(_ReadOnlyBinding):
    def __init__(
        self,
        *,
        plan_path: Path,
        adoption_path: Path,
        target: Read15RuntimeTarget,
        saved_root: Path,
        application_root: Path = _ROOT,
    ) -> None:
        self.path, self.adoption_path, self.target = plan_path, adoption_path, target
        self.saved_root, self.application_root = saved_root, application_root
        self.plan, self.plan_sha256 = _document(plan_path)
        validated = self._validate()
        profile = mapping(validated.chain.current.envelope["profile"], "P0_REJECTED_ORIGIN_PROFILE")
        self._bound_ledger = P0RejectedContinuityLedger(
            root=Path(str(profile["receipt_root"])),
            permission=validated.chain.current.permission,
            chain_loader=lambda: self._validate().chain,
            broker_identity=self,
            clock=lambda: datetime.now(UTC),
            selected=selected_attempt(validated.plan["target_attempt"]),
            tariff=cast(Mapping[str, object], read_descriptor(profile["tariff"])),
            orientation=descriptor(validated.plan["owner_orientation_adoption"]),
            diagnostic=descriptor(validated.plan["owner_diagnostic"]),
            plan_sha256=validated.sha256,
        )

    def _validate(self) -> ValidatedInspectionPlan:
        plan, pin = _document(self.path)
        if pin != self.plan_sha256:
            raise ValueError("P0_REJECTED_PLAN_CHANGED")
        closed(plan, PLAN_FIELDS, "P0_REJECTED_PLAN_FIELDS")
        selected = selected_attempt(plan["target_attempt"])
        if (
            plan["schema"] != "P0-KNOWN-REJECTED-INSPECTION-PLAN-1.0"
            or plan["operation"] != "INSPECT_KNOWN_REJECTION_AND_CAMPAIGN_READ_ONLY"
            or plan["ledger_writes_allowed"] is not False
            or type(plan["provider_calls_allowed"]) is not int
            or plan["provider_calls_allowed"] != 0
            or not digest(plan["origin_tip_permission_sha256"])
            or any(
                not isinstance(plan[key], str)
                or re.fullmatch(r"[0-9a-f]{40}", str(plan[key])) is None
                for key in ("baseline_commit", "source_tree")
            )
            or not utc(plan["issued_at_utc"]) <= datetime.now(UTC) < utc(plan["expires_at_utc"])
        ):
            raise ValueError("P0_REJECTED_PLAN_POLICY")
        _external(
            self.adoption_path,
            components={
                "inspection_plan_sha256": pin,
                "source_manifest_sha256": descriptor(plan["source_manifest"])["sha256"],
                "package_sha256": descriptor(plan["package"])["sha256"],
            },
            operation="INSPECTION_ONLY",
        )
        verify_source_package(plan, application_root=self.application_root)
        source = cast(Mapping[str, object], read_descriptor(plan["source_manifest"]))
        if (
            source["source_commit"] != plan["baseline_commit"]
            or source["source_tree"] != plan["source_tree"]
        ):
            raise ValueError("P0_REJECTED_PLAN_SOURCE_BINDING")
        proofs, manifests = _ancestors(plan["ancestors"], self.saved_root)
        tip = proofs[-1]
        if (
            tip.permission_sha256 != plan["origin_tip_permission_sha256"]
            or selected["permission_sha256"] != tip.permission_sha256
        ):
            raise ValueError("P0_REJECTED_PLAN_TIP_BINDING")
        prior = manifests.get(tip.permission_sha256)
        if prior is None:
            raise ValueError("P0_REJECTED_PLAN_VERSIONED_ORIGIN_REQUIRED")
        original = _anchor(plan["original_anchor"])
        chain = bind_chain(prior, proofs[:-1], tip, ancestor_manifests=manifests, anchor=original)
        profile = mapping(tip.envelope["profile"], "P0_REJECTED_PLAN_PROFILE")
        runtime = mapping(plan["target_runtime"], "P0_REJECTED_PLAN_RUNTIME")
        if (
            canonical(runtime) != canonical(profile["runtime"])
            or Path(str(runtime["path"])) != self.target.runtime_path
            or Path(str(runtime["data_root"])) != self.target.data_root
            or runtime["sha256"] != self.target.expected_sha256
            or Path(str(profile["saved_root"])) != self.saved_root
            or canonical(plan["expected_operator_delegation"])
            != canonical(profile["operator_delegation"])
            or canonical(plan["saved_root_native_identity"]) != canonical(_native(self.saved_root))
            or canonical(plan["receipt_root_native_identity"])
            != canonical(_native(Path(str(profile["receipt_root"]))))
            or not utc(chain.root.permission["issued_at_utc"])
            <= utc(plan["issued_at_utc"])
            < utc(plan["expires_at_utc"])
            <= utc(chain.root.permission["expires_at_utc"])
        ):
            raise ValueError("P0_REJECTED_PLAN_NATIVE_BINDING")
        self.target.validate()
        _orientation(plan, selected)
        return ValidatedInspectionPlan(plan, pin, chain)

    def _ledger(self) -> P0RejectedContinuityLedger:
        # Keep the native store identity bound to this composition. Each read
        # still invokes the fresh chain_loader inside the original LOCK.
        return self._bound_ledger

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        service.generation, endpoint.generation_bound, endpoint.consent_execute = None, False, None
        self._bind_inspection(
            endpoint, _InspectionReader(self._ledger, identity=self.plan_sha256, bootstrap=True)
        )


class P0RejectedProductComposition(_ReadOnlyBinding):
    read_phases: NativeP0RejectedReadPhases | None = None

    def __init__(
        self,
        *,
        path: Path,
        adoption_path: Path,
        target: Read15RuntimeTarget,
        saved_root: Path,
        mode: str = "off",
        application_root: Path = _ROOT,
    ) -> None:
        if mode not in {"off", "on"}:
            raise ValueError("P0_REJECTED_EXPLICIT_MODE_REQUIRED")
        self.path, self.adoption_path, self.target = path, adoption_path, target
        self.saved_root, self.application_root, self.mode = saved_root, application_root, mode
        self.envelope, self.envelope_sha256 = _document(path)
        self.profile = dict(mapping(self.envelope["profile"], "P0_REJECTED_PROFILE"))
        if self.profile.get("continuity_enabled") is not (mode == "on"):
            raise ValueError("P0_REJECTED_ADOPTED_MODE_MISMATCH")
        self.profile_sha256 = sha(canonical(self.profile))
        self.root = Path(absolute(self.profile["receipt_root"]))
        self.chain = self._chain()
        self.permission, self.decision = (
            dict(self.chain.current.permission),
            dict(self.chain.current.decision),
        )
        self.tariff = cast(Mapping[str, object], read_descriptor(self.profile["tariff"]))
        self._bound_ledger = P0RejectedContinuityLedger(
            root=self.root,
            permission=self.chain.current.permission,
            chain_loader=self._chain,
            broker_identity=self,
            clock=lambda: datetime.now(UTC),
            selected=selected_attempt(self.chain.disposition["target_attempt"]),
            tariff=self.tariff,
            orientation=descriptor(self.chain.evidence["owner_orientation_adoption"]),
            diagnostic=descriptor(self.chain.evidence["owner_diagnostic"]),
            plan_sha256=str(self.chain.evidence["inspection_plan_sha256"]),
        )
        self.resolver: MaskedLocalSecretResolver | None = None
        self.local_context: ReadP0LocalReferenceContext | None = None
        self.admission: ReadP0SourceAdmission | None = None
        self.read_phases = NativeP0RejectedReadPhases(
            lock_scope=self._read_scope,
            collect=self._read_files,
            full_chain=self._chain_uncached,
            fresh=self._read_fresh,
            mutable_directories=(self.root, self.saved_root, self.target.data_root),
        )
        if mode == "on":
            try:
                self._on()
            except Exception:
                self.close()
                raise

    def _chain(self) -> BoundChainV2:
        phases = self.read_phases
        if phases is not None:
            if phases.poisoned:
                raise ValueError("P0_READSET_ASYNC_TERMINATION_UNCONFIRMED")
            if phases.has_proof:
                return phases.require_proof()
        return self._chain_uncached()

    def _read_scope(self) -> object:
        broker = self.generation
        if not isinstance(broker, P0RejectedProductGenerationAdapter):
            raise ValueError("P0_READSET_EXACT_BROKER_REQUIRED")
        ledger = broker.ledger
        if (
            not isinstance(ledger, P0RejectedContinuityLedger)
            or ledger.broker_identity is not broker
        ):
            raise ValueError("P0_READSET_EXACT_LEDGER_REQUIRED")
        if ledger._held_thread != threading.get_ident():
            raise ValueError("P0_READSET_NATIVE_LOCK_REQUIRED")
        chain = ledger.chain()
        return (
            id(self),
            id(broker),
            id(ledger),
            id(chain),
            ledger._held_thread,
            chain.current.permission_sha256,
            chain.manifest["campaign_namespace_sha256"],
        )

    def _read_files(self) -> Mapping[Path, tuple[Path, str]]:
        files: dict[Path, tuple[Path, str]] = {}
        seen: set[Path] = set()

        def add(path: Path, root: Path, pin: str) -> None:
            if path in files and files[path][1] != pin:
                raise ValueError("P0_READSET_AMBIGUOUS_PIN")
            files[path] = (root, pin)

        def walk(value: object) -> None:
            if isinstance(value, Mapping):
                if set(value) == {"path", "sha256"}:
                    desc = descriptor(value)
                    path, pin = Path(str(desc["path"])), str(desc["sha256"])
                    add(path, path.parent, pin)
                    if path not in seen:
                        seen.add(path)
                        with pinned_receipt_root(path.parent):
                            raw = read_file_nofollow(
                                path, allowed_root=path.parent, maximum_bytes=128_000_000
                            )
                        if sha(raw) != pin:
                            raise ValueError("P0_READSET_DESCRIPTOR_CHANGED")
                        if path.suffix.casefold() == ".json":
                            document = strict_document(raw, canonical_required=False)
                            if document.get("schema") == "P0-NORMAL-SOURCE-MANIFEST-2.0":
                                if canonical(document) == canonical(
                                    read_descriptor(self.profile["source_manifest"])
                                ):
                                    source_files = mapping(
                                        document["files"], "P0_READSET_SOURCE_FILES"
                                    )
                                    for name, source_pin in source_files.items():
                                        add(
                                            self.application_root / str(name),
                                            self.application_root,
                                            str(source_pin),
                                        )
                            walk(document)
                else:
                    for child in value.values():
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        envelope, pin = _document(self.path)
        add(self.path, self.path.parent, pin)
        control, control_pin = _document(self.adoption_path)
        add(self.adoption_path, self.adoption_path.parent, control_pin)
        walk(envelope)
        walk(control)
        # Historical receipts remain read-only, while the exact new namespace
        # follows its existing append/create-only Normal protocol.
        ledger = cast(
            P0RejectedContinuityLedger,
            cast(P0RejectedProductGenerationAdapter, self.generation).ledger,
        )
        pending = ledger._pending
        records = ledger.slots()
        namespaces = {str(record["namespace_sha256"]) for record in records}
        for path in self.root.iterdir():
            if path.is_file() and path.suffix.casefold() == ".json":
                if not (
                    path.name.startswith(ledger.prefix) or path.name.split(".")[0] in namespaces
                ):
                    continue
                if pending is not None and path.name.startswith(pending.namespace_sha256 + "."):
                    continue
                with pinned_receipt_root(self.root):
                    raw = read_file_nofollow(
                        path, allowed_root=self.root, maximum_bytes=128_000_000
                    )
                add(path, self.root, sha(raw))
        return files

    def _read_fresh(self, chain: BoundChainV2) -> None:
        if (self.application_root / ".git").exists():
            raise ValueError("P0_READSET_EXACT_DISTRIBUTION_REQUIRED")
        self.target.validate()
        if windows_operator() != chain.current.operator:
            raise ValueError("P0_READSET_OPERATOR_CHANGED")
        profile = mapping(chain.current.envelope["profile"], "P0_READSET_PROFILE")
        if sha(canonical(_native(self.saved_root))) != chain.current.saved_root_native_sha256:
            raise ValueError("P0_READSET_SAVED_ROOT_CHANGED")
        source = cast(Mapping[str, object], read_descriptor(profile["source_manifest"]))
        expected = mapping(source["files"], "P0_READSET_SOURCE_FILES")
        actual = {
            path.relative_to(self.application_root).as_posix()
            for name in ("backend", "frontend", "tools", "config")
            for path in (self.application_root / name).rglob("*")
            if path.is_file()
            and path.suffix.casefold() in {".py", ".js", ".css", ".html", ".ps1", ".json"}
            and "__pycache__" not in path.parts
        }
        if actual != set(expected):
            raise ValueError("P0_READSET_SOURCE_COVERAGE_CHANGED")
        cast(P0RejectedProductGenerationAdapter, self.generation).ledger.pin._root_unchanged()
        # The read-set never freezes unrelated campaigns. Detect additional
        # current-campaign slots, or forbidden own outcomes, freshly.
        phases = cast(NativeP0RejectedReadPhases, self.read_phases)
        ledger = cast(
            P0RejectedContinuityLedger,
            cast(P0RejectedProductGenerationAdapter, self.generation).ledger,
        )
        protected = {path.name for path in phases.protected_paths if path.parent == self.root}
        actual_slots = {path.name for path in self.root.glob(ledger.prefix + "*.json")}
        if actual_slots - protected:
            raise ValueError("P0_READSET_CURRENT_SLOTS_CHANGED")
        records = [
            decode(read_file_nofollow(self.root / name, allowed_root=self.root, maximum_bytes=32_000))
            for name in sorted(actual_slots)
        ]
        # Inventory is fresh even though the retained bytes are immutable.
        # Classify new namespaces through their exact origin, never by directory.
        reject_orphan_namespaces(chain, records, normal_namespaces=ledger._normal_namespaces())
        pending = ledger._pending
        if pending is not None:
            own = [record for record in records if record["namespace_sha256"] == pending.namespace_sha256]
            if len(own) != 1:
                raise ValueError("P0_READSET_OWN_PENDING_BINDING")
            receipt = P0NormalReceipt(self.root, pending.namespace_sha256)
            existing = {state for state in NORMAL_EVENTS if receipt.exists(state)}
            if not existing:
                if not allow_own_transition(
                    chain,
                    own[0],
                    pending,
                    broker_identity=ledger.broker_identity,
                    dispatch_sha256=str(ledger._pending_dispatch_sha256),
                    now=ledger.clock(),
                    existing_p0_events=tuple(existing),
                ):
                    raise ValueError("P0_READSET_OWN_PENDING_BINDING")
            elif existing == {"RESERVED", "DISPATCH"}:
                self._read_reserved_pending(chain, own[0], receipt, ledger)
            else:
                raise ValueError("P0_READSET_OWN_PENDING_STAGE")
        namespaces = {str(record["namespace_sha256"]) for record in records}
        for path in self.root.iterdir():
            if path.suffix.casefold() != ".json" or path.name.split(".")[0] not in namespaces:
                continue
            if path.name in protected:
                continue
            if pending is None or not path.name.startswith(pending.namespace_sha256 + "."):
                raise ValueError("P0_READSET_HISTORICAL_EVENTS_CHANGED")
        if pending is not None and any(
            (self.root / (pending.namespace_sha256 + "." + state + ".json")).exists()
            for state in ("UNKNOWN", "PARSING_REJECTED")
        ):
            raise ValueError("P0_CONTINUITY_OUTCOME_RECONCILIATION_REQUIRED")

    def _read_reserved_pending(
        self,
        chain: BoundChainV2,
        record: Mapping[str, object],
        receipt: P0NormalReceipt,
        ledger: P0RejectedContinuityLedger,
    ) -> None:
        """Only the exact preprovider RESERVED+DISPATCH transition is admissible."""
        pending = ledger._pending
        grant = mapping(record["grant"], "P0_READSET_OWN_PENDING_GRANT")
        now = ledger.clock()
        exact = {
            "permission_sha256": chain.current.permission_sha256,
            "command_id": record["command_id"],
            "grant_sha256": record["grant_sha256"],
            "namespace_sha256": record["namespace_sha256"],
            "request_sha256": record["request_sha256"],
            "preflight_sha256": record["preflight_sha256"],
            "dispatch_sha256": str(ledger._pending_dispatch_sha256),
        }
        if (
            pending is None
            or pending.broker_identity is not ledger.broker_identity
            or record["permission_sha256"] != chain.current.permission_sha256
            or any(getattr(pending, key) != value for key, value in exact.items())
            or not utc(grant["issued_at_utc"]) <= now < utc(grant["expires_at_utc"])
            or not now < utc(pending.expires_at_utc)
        ):
            raise ValueError("P0_READSET_OWN_PENDING_BINDING")
        capture = receipt.read("DISPATCH")
        closed(capture, {"schema", "grant_sha256", "dispatch_sha256", "request_sha256",
                         "preflight_sha256", "namespace_sha256", "grant", "dispatch",
                         "body", "preflight"}, "P0_READSET_OWN_CAPTURE_FIELDS")
        dispatch = mapping(capture["dispatch"], "P0_READSET_OWN_CAPTURE_TYPES")
        proof = mapping(capture["preflight"], "P0_READSET_OWN_CAPTURE_TYPES")
        body = capture["body"]
        if (
            capture["schema"] != "P0-NORMAL-DISPATCH-CAPTURE-1.0"
            or canonical(capture["grant"]) != canonical(grant)
            or sha(canonical(capture["grant"])) != pending.grant_sha256
            or any(capture[key] != record[key] for key in (
                "grant_sha256", "request_sha256", "preflight_sha256", "namespace_sha256"))
            or capture["dispatch_sha256"] != pending.dispatch_sha256
            or sha(canonical(dispatch)) != pending.dispatch_sha256
            or not isinstance(body, str)
            or sha(body.encode()) != pending.request_sha256
            or len(body.encode()) != grant["request_bytes"]
            or sha(canonical(proof)) != pending.preflight_sha256
        ):
            raise ValueError("P0_READSET_OWN_CAPTURE_BINDING")
        reserved = receipt.read("RESERVED")
        closed(reserved, EVENT_FIELDS, "P0_READSET_OWN_RESERVED_FIELDS")
        expected = receipt.event("RESERVED", grant, proof)
        if (
            any(reserved[key] != value for key, value in expected.items() if key != "timestamp_utc")
            or type(reserved["provider_attempts"]) is not int
            or not utc(grant["issued_at_utc"]) <= utc(reserved["timestamp_utc"]) <= now
            or not utc(reserved["timestamp_utc"]) < utc(grant["expires_at_utc"])
        ):
            raise ValueError("P0_READSET_OWN_RESERVED_BINDING")

    def _chain_uncached(self) -> BoundChainV2:
        envelope, pin = _document(self.path)
        if pin != self.envelope_sha256:
            raise ValueError("P0_REJECTED_PROFILE_CHANGED")
        current = _proof(envelope, saved_root=self.saved_root)
        profile = mapping(envelope["profile"], "P0_REJECTED_PROFILE")
        manifest = cast(Mapping[str, object], read_descriptor(profile["continuity_manifest"]))
        anchor = _anchor(profile["continuity_anchor"])
        original = _anchor(anchor["original_anchor"])
        disposition = cast(Mapping[str, object], read_descriptor(profile["rejected_disposition"]))
        evidence = cast(Mapping[str, object], read_descriptor(disposition["observed_evidence"]))
        _orientation(disposition, selected_attempt(disposition["target_attempt"]))
        proofs, manifests = _ancestors(manifest["ancestors"], self.saved_root)
        # Both immutable envelopes are supplied by the external adoption, not
        # referenced by the components. ON includes its exact OFF predecessor.
        control, _ = _document(self.adoption_path)
        pair = mapping(control.get("profile_envelopes"), "P0_REJECTED_EXTERNAL_ENVELOPES_REQUIRED")
        closed(pair, {"off", "on"}, "P0_REJECTED_EXTERNAL_ENVELOPES_REQUIRED")
        loaded: dict[str, Mapping[str, object]] = {
            key: cast(Mapping[str, object], read_descriptor(value)) for key, value in pair.items()
        }
        profiles = {
            key: mapping(value["profile"], "P0_REJECTED_EXTERNAL_PROFILE")
            for key, value in loaded.items()
        }
        if (
            profiles["off"]["continuity_enabled"] is not False
            or profiles["on"]["continuity_enabled"] is not True
            or canonical(loaded[self.mode]) != canonical(envelope)
            or descriptor(pair[self.mode])["sha256"] != pin
            or any(
                canonical(profiles[key][name]) != canonical(profile[name])
                for key in profiles
                for name in (
                    "source_manifest",
                    "package",
                    "continuity_anchor",
                    "rejected_disposition",
                )
            )
        ):
            raise ValueError("P0_REJECTED_EXTERNAL_MODE_BINDING")
        _external(
            self.adoption_path,
            components={
                "observed_evidence_sha256": sha(canonical(evidence)),
                "disposition_sha256": sha(canonical(disposition)),
                "anchor2_sha256": sha(canonical(anchor)),
                "manifest2_sha256": {
                    key: descriptor(value["continuity_manifest"])["sha256"]
                    for key, value in profiles.items()
                },
                "profile4_OFF_sha256": sha(canonical(profiles["off"])),
                "profile4_ON_sha256": sha(canonical(profiles["on"])),
                "source_manifest_sha256": descriptor(profile["source_manifest"])["sha256"],
                "package_sha256": descriptor(profile["package"])["sha256"],
            },
            operation="OFF_ON_COMPONENT_REBIND",
        )
        if any(
            mapping(proof.envelope["profile"], "P0_REJECTED_ANCESTOR")["schema"]
            == "P0-NORMAL-PROFILE-4.0"
            and canonical(proof.envelope) != canonical(loaded["off"])
            for proof in proofs
        ):
            raise ValueError("P0_REJECTED_UNADOPTED_PROFILE4_ANCESTOR")
        runtime = mapping(profile["runtime"], "P0_REJECTED_RUNTIME")
        if (
            Path(str(runtime["path"])) != self.target.runtime_path
            or Path(str(runtime["data_root"])) != self.target.data_root
            or runtime["sha256"] != self.target.expected_sha256
            or Path(str(profile["saved_root"])) != self.saved_root
        ):
            raise ValueError("P0_REJECTED_TARGET_BINDING")
        self.target.validate()
        verify_source_package(profile, application_root=self.application_root)
        return bind_chain_v2(
            manifest,
            proofs,
            current,
            anchor=anchor,
            original_anchor=original,
            ancestor_manifests=manifests,
            disposition=disposition,
            evidence=evidence,
        )

    def _ledger(self) -> P0RejectedContinuityLedger:
        # Returning an object is not a validation cache: locked() reloads all
        # current descriptors/source/identities before every snapshot.
        return self._bound_ledger

    def identities(self) -> Mapping[str, object]:
        chain = self._chain()
        identities = {key: chain.current.permission[key] for key in P1_HASHES | {"baseline_commit"}}
        actual = {
            "source_tree_sha256": descriptor(self.profile["source_manifest"])["sha256"],
            "package_sha256": descriptor(self.profile["package"])["sha256"],
            "profile_sha256": self.profile_sha256,
            "receipt_root_sha256": P0NormalReceipt(
                self.root, str(chain.manifest["campaign_namespace_sha256"])
            ).root_sha256,
        }
        if any(identities[key] != value for key, value in actual.items()):
            raise ValueError("P0_REJECTED_CURRENT_IDENTITIES_CHANGED")
        return identities

    def grant_identities(self, request: Mapping[str, object], body: bytes) -> Mapping[str, object]:
        current = self.identities()
        fields = {
            key: value
            for key, value in current.items()
            if key
            in {
                "owner_decision_sha256",
                "baseline_commit",
                "source_tree_sha256",
                "package_sha256",
                "runtime_sha256",
                "profile_sha256",
                "output_schema_sha256",
                "tokenizer_manifest_sha256",
                "tariff_sha256",
                "receipt_root_sha256",
            }
        }
        return {
            **fields,
            "preparation_sha256": sha(canonical(request)),
            "context_sha256": request["context_sha256"],
            "reference_set_sha256": sha(canonical(request["references"])),
            "request_sha256": sha(body),
            "request_bytes": len(body),
            "output_schema_sha256": sha(canonical(build_p0_content_request(request).output_schema)),
            "namespace_sha256": self.permission["permission_namespace_sha256"],
        }

    def _on(self) -> None:
        validate_permission(
            self.permission,
            identities=self.identities(),
            now=datetime.now(UTC),
            family="COURSE",
            level=str(cast(list[str], self.permission["allowed_levels"])[0]),
        )
        self._ledger().snapshot()
        from backend.adapters.outbound.openai import OpenAISDKResponsesTransportFactory
        from backend.infrastructure.config.secrets.provider import ProviderCredentialRef

        owner = descriptor(self.profile["source_admission_owner_decision"])["sha256"]
        source = cast(
            Mapping[str, object],
            read_descriptor(self.profile["source_admission_manifest"], canonical_required=False),
        )
        self.admission = ReadP0SourceAdmission(
            source,
            manifest_sha256=str(descriptor(self.profile["source_admission_manifest"])["sha256"]),
            adopted_manifest_sha256=str(self.decision["source_admission_manifest_sha256"]),
            owner_admission_sha256=str(owner),
        )
        local = cast(
            Mapping[str, object], read_descriptor(self.profile["local_reference_context_manifest"])
        )
        self.local_context = ReadP0LocalReferenceContext(
            local,
            manifest_sha256=str(
                descriptor(self.profile["local_reference_context_manifest"])["sha256"]
            ),
            adopted_manifest_sha256=str(self.decision["local_reference_context_manifest_sha256"]),
            owner_admission_sha256=str(owner),
            sources=self.admission,
            runtime_sha256=self.target.expected_sha256,
            institutional_catalogue_sha256=str(self.profile["institutional_catalog_sha256"]),
        )
        adoption = {
            "profile_schema": self.profile["schema"],
            "owner_decision_schema": self.decision["schema"],
            "profile_sha256": self.permission["profile_sha256"],
            "owner_decision_sha256": self.permission["owner_decision_sha256"],
            "local_reference_context_manifest_sha256": self.local_context.manifest_sha256,
            "source_admission_owner_decision_sha256": owner,
            "continuity_manifest_sha256": descriptor(self.profile["continuity_manifest"])["sha256"],
            "continuity_anchor_sha256": descriptor(self.profile["continuity_anchor"])["sha256"],
            "rejected_disposition_sha256": descriptor(self.profile["rejected_disposition"])[
                "sha256"
            ],
        }
        tokenizer_manifest = cast(
            Mapping[str, object], read_descriptor(self.profile["tokenizer_manifest"])
        )
        tokenizer = LocalTokenizerHelper(
            tokenizer_manifest,
            str(self.permission["tokenizer_manifest_sha256"]),
            application_root=self.application_root,
        )
        tokenizer(
            canonical({"model": "gpt-5.6-terra", "input": "P0 LOCAL TOKENIZER READINESS PROBE"})
        )
        self.resolver = MaskedLocalSecretResolver(
            ProviderCredentialRef(str(self.profile["credential_ref"]))
        )
        self.generation = P0RejectedProductGenerationAdapter(
            read_phase=cast(NativeP0RejectedReadPhases, self.read_phases),
            rejected_chain=self._chain,
            permission=self.permission,
            permission_identities=self.identities,
            identity_source=self.grant_identities,
            tariff=self.tariff,
            tokenizer=tokenizer,
            receipt_root=self.root,
            resolver=self.resolver,
            credential_ref=self.resolver.ref,
            transport=OpenAISDKResponsesTransportFactory(r2_destination=True),
            local_context_adoption=adoption,
        )
        # No preview/consent/grant is created by construction. Current metadata
        # must pass before the normal generation binder becomes available.

    def bind(self, service: P0CreationService, endpoint: P0CreationEndpoint) -> None:
        self._bind_inspection(
            endpoint, _InspectionReader(self._ledger, identity=self.profile_sha256, bootstrap=False)
        )
        if self.mode == "off":
            service.generation, endpoint.generation_bound, endpoint.consent_execute = (
                None,
                False,
                None,
            )
            return
        from backend.infrastructure.composition.factories.p0_local_reference_context import (
            build_local_reference_resolver,
        )
        from backend.infrastructure.composition.factories.p0_product_consent import (
            bind_product_consent,
        )

        assert self.local_context is not None and isinstance(
            self.generation, P0RejectedProductGenerationAdapter
        )
        resolver = build_local_reference_resolver(
            self.target, self.local_context, revalidate=self.identities
        )
        service.institutional_resolver = resolver
        endpoint.local_reference_contexts = self.local_context.metadata
        bind_product_consent(
            service,
            endpoint,
            target=self.target,
            generation=self.generation,
            admission=self.local_context,
            institutional_resolver=resolver,
        )

    def close(self) -> None:
        phases = getattr(self, "read_phases", None)
        if phases is not None:
            phases.close()
        if self.resolver is not None:
            self.resolver.close()
