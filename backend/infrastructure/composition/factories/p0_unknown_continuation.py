"""Explicit one-operation composition. No autoload and no authority from OFF inspection."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    canonical,
    closed,
    digest,
    sha,
    utc,
)
from backend.adapters.outbound.generation.openai.p0_product_continuity_contract import mapping
from backend.adapters.outbound.generation.openai.p0_product_rejected import (
    P0RejectedProductGenerationAdapter,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_contract import (
    BoundChainV2,
    bind_chain_v2,
)
from backend.adapters.outbound.generation.openai.p0_product_rejected_continuity_ledger import (
    P0RejectedContinuityLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_continuation_contract import (
    UnknownContinuation,
    validate_adoption,
    validate_history,
    validate_intent,
    validate_plan,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_continuation_ledger import (
    P0UnknownContinuationLedger,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_contract import (
    ANCHOR_FIELDS,
    MANIFEST_FIELDS,
    validate_owner_diagnostic,
)
from backend.adapters.outbound.generation.openai.p0_product_unknown_off_contract import (
    validate_adoption as validate_off_adoption,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.p0_normal_profile import (
    read_descriptor,
    verify_source_package,
)
from backend.infrastructure.composition.factories.p0_normal_profile_contract import descriptor
from backend.infrastructure.composition.factories.p0_rejected_profile import (
    P0RejectedProductComposition,
    _ancestors,
    _anchor,
    _document,
    _external,
    _native,
    _proof,
)
from backend.infrastructure.composition.factories.p0_unknown_off import (
    PLAN_FIELDS as OFF_PLAN_FIELDS,
)
from backend.infrastructure.composition.factories.p0_unknown_off import _historical
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionView,
)
from backend.modules.work_orchestration.contracts.dto.p1_operation_intent import distinct_operation

Document = Mapping[str, Any]

def _json(value: object, *, canonical_required: bool = True) -> Document:
    return cast(Document, read_descriptor(value, canonical_required=canonical_required))


class P0UnknownContinuationGenerationAdapter(P0RejectedProductGenerationAdapter):
    def __init__(self, *, operation_context: Callable[[], UnknownContinuation], **kwargs: object) -> None:
        self.operation_context = operation_context
        super().__init__(**kwargs)  # type: ignore[arg-type]

    def _make_ledger(self, chain: BoundChainV2, rejected_chain: Callable[[], BoundChainV2]) -> P0RejectedContinuityLedger:
        return P0UnknownContinuationLedger(operation_context=self.operation_context,
            root=self.root, permission=self.permission, chain_loader=rejected_chain,
            broker_identity=self, clock=self.clock, selected=chain.disposition["target_attempt"],
            tariff=self.tariff, orientation=chain.evidence["owner_orientation_adoption"],
            diagnostic=chain.evidence["owner_diagnostic"], plan_sha256=chain.evidence["inspection_plan_sha256"])

    def _snapshot(self, request: Document, receipts: Sequence[Document]) -> tuple[bytes, dict[str, object], dict[str, object]]:
        raw, identities, proof = super()._snapshot(request, receipts)
        context = self.operation_context()
        cast(P0UnknownContinuationLedger, self.ledger).require_available()
        selected = mapping(context.unknown_disposition["target_attempt"], "P1_UNKNOWN_SELECTED")
        namespace = str(selected["namespace_sha256"])
        from backend.adapters.outbound.generation.openai.p0_normal_receipt import P0NormalReceipt
        old = P0NormalReceipt(self.root, namespace).read("DISPATCH")
        self._require_intent(request, raw, identities, proof, old, context.intent)
        return raw, identities, proof

    @staticmethod
    def _require_intent(request: Document, raw: bytes, identities: Document, proof: Document,
        old: Document, intent: Document) -> None:
        compared = distinct_operation(old["dispatch"], request)
        if (sha(raw) == sha(old["body"].encode()) or any(compared[k] != intent[k] for k in compared)
            or any(identities[k] != intent[k] for k in ("preparation_sha256", "request_sha256", "request_bytes",
                "context_sha256", "reference_set_sha256")) or proof["cost_bound_usd"] != intent["cost_bound_usd"]):
            raise ValueError("P1_UNKNOWN_NEW_PREPARATION_BINDING")


class P0UnknownContinuationComposition(P0RejectedProductComposition):
    def __init__(self, *, plan_path: Path, adoption_path: Path, expected_owner_sha256: str,
        target: Read15RuntimeTarget, saved_root: Path, application_root: Path, mode: str = "off") -> None:
        if mode not in {"off", "on"}:
            raise ValueError("P1_UNKNOWN_EXPLICIT_MODE_REQUIRED")
        self.operation_path, self.operation_adoption = plan_path, adoption_path
        self.expected_operation_owner = expected_owner_sha256
        initial, self.operation_sha256 = _document(plan_path)
        pair = mapping(initial["profile_envelopes"], "P1_UNKNOWN_PROFILE_PAIR")
        envelope = descriptor(pair[mode])
        self._operation: UnknownContinuation | None = None
        super().__init__(path=Path(str(envelope["path"])),
            adoption_path=Path(str(descriptor(initial["profile_adoption"])["path"])), target=target,
            saved_root=saved_root, application_root=application_root, mode=mode)

    def _context(self) -> UnknownContinuation:
        if self._operation is None:
            raise ValueError("P1_UNKNOWN_VALIDATED_CONTEXT_REQUIRED")
        return self._operation

    def _make_ledger(self, **kwargs: object) -> P0RejectedContinuityLedger:
        return P0UnknownContinuationLedger(operation_context=self._context, **kwargs)

    def _make_broker(self, **kwargs: object) -> P0RejectedProductGenerationAdapter:
        return P0UnknownContinuationGenerationAdapter(operation_context=self._context, **kwargs)

    def _chain_uncached(self) -> BoundChainV2:
        plan, pin = _document(self.operation_path)
        if pin != self.operation_sha256:
            raise ValueError("P1_UNKNOWN_OPERATION_CHANGED")
        history, intent = _json(plan["history"]), _json(plan["intent"])
        validate_history(history)
        validate_intent(intent)
        old_plan = _json(history["off_plan"])
        historical = _historical(old_plan, self.saved_root)
        old_manifest = _json(old_plan["manifest"])
        unknown = _json(old_manifest["unknown_disposition"])
        self._historical_static(old_plan, old_manifest, unknown, historical)
        self._history_adoption(history, old_plan, old_manifest, unknown, historical)
        validate_plan(plan, now=datetime.now(UTC), root=historical.root.permission)
        pair = mapping(plan["profile_envelopes"], "P1_UNKNOWN_PROFILE_PAIR")
        loaded = {key: _json(value) for key, value in pair.items()}
        profiles = {key: mapping(value["profile"], "P1_UNKNOWN_CURRENT_PROFILE") for key, value in loaded.items()}
        envelope, envelope_pin = _document(self.path)
        if (envelope_pin != self.envelope_sha256 or envelope_pin != descriptor(pair[self.mode])["sha256"]
            or canonical(envelope) != canonical(loaded[self.mode])
            or profiles["off"]["continuity_enabled"] is not False or profiles["on"]["continuity_enabled"] is not True
            or any(canonical(profiles[key][name]) != canonical(profiles[self.mode][name]) for key in profiles
                for name in ("source_manifest", "package", "continuity_anchor", "rejected_disposition"))):
            raise ValueError("P1_UNKNOWN_CURRENT_PAIR_BINDING")
        control, _ = _document(self.operation_adoption)
        book, owner = _json(control["book"]), _json(control["owner_evidence"], canonical_required=False)
        profile = profiles[self.mode]
        components = {"plan_sha256": pin, "history_sha256": descriptor(plan["history"])["sha256"],
            "intent_sha256": descriptor(plan["intent"])["sha256"],
            "source_manifest_sha256": descriptor(profile["source_manifest"])["sha256"],
            "package_sha256": descriptor(profile["package"])["sha256"],
            "profile_off_sha256": sha(canonical(profiles["off"])), "profile_on_sha256": sha(canonical(profiles["on"]))}
        validate_adoption(control, book, owner, expected_owner_sha256=self.expected_operation_owner,
            owner_raw_sha256=str(descriptor(control["owner_evidence"])["sha256"]), components=components)
        current = _proof(envelope, saved_root=self.saved_root)
        manifest = _json(profile["continuity_manifest"])
        anchor = _anchor(profile["continuity_anchor"])
        original = _anchor(anchor["original_anchor"])
        disposition = _json(profile["rejected_disposition"])
        evidence = _json(disposition["observed_evidence"])
        proofs, manifests = _ancestors(manifest["ancestors"], self.saved_root)
        expected = list(historical.origins)
        if self.mode == "on":
            expected.append(_proof(loaded["off"], saved_root=self.saved_root))
        if (len(proofs) != len(expected) or any(canonical(a.envelope) != canonical(b.envelope)
                for a, b in zip(proofs, expected, strict=True))
            or canonical(anchor) != canonical(historical.anchor)
            or canonical(disposition) != canonical(historical.disposition)
            or canonical(evidence) != canonical(historical.evidence)):
            raise ValueError("P1_UNKNOWN_EXACT_ANCESTRY_REQUIRED")
        manifests_pair = {key: descriptor(p["continuity_manifest"])["sha256"] for key, p in profiles.items()}
        _external(Path(str(descriptor(plan["profile_adoption"])["path"])), operation="OFF_ON_COMPONENT_REBIND",
            components={"observed_evidence_sha256": sha(canonical(evidence)), "disposition_sha256": sha(canonical(disposition)),
                "anchor2_sha256": sha(canonical(anchor)), "manifest2_sha256": manifests_pair,
                "profile4_OFF_sha256": components["profile_off_sha256"], "profile4_ON_sha256": components["profile_on_sha256"],
                "source_manifest_sha256": components["source_manifest_sha256"], "package_sha256": components["package_sha256"]})
        chain = bind_chain_v2(manifest, proofs, current, anchor=anchor, original_anchor=original,
            ancestor_manifests=manifests, disposition=disposition, evidence=evidence)
        runtime = mapping(profile["runtime"], "P1_UNKNOWN_RUNTIME")
        if (Path(str(runtime["path"])) != self.target.runtime_path or Path(str(runtime["data_root"])) != self.target.data_root
            or runtime["sha256"] != self.target.expected_sha256 or Path(str(profile["saved_root"])) != self.saved_root
            or canonical(_native(self.saved_root)) != canonical(old_plan["saved_root_native_identity"])
            or canonical(_native(self.root)) != canonical(old_plan["receipt_root_native_identity"])):
            raise ValueError("P1_UNKNOWN_ORIGINAL_STORES_REQUIRED")
        self.target.validate()
        verify_source_package(profile, application_root=self.application_root)
        self._operation = UnknownContinuation(plan, history, intent, historical, old_manifest, unknown, chain)
        return chain

    @staticmethod
    def _historical_static(plan: Document, manifest: Document, disposition: Document, chain: BoundChainV2) -> None:
        """Revalidate the historical evidence structure, without replay or freshness renewal."""
        closed(plan, OFF_PLAN_FIELDS, "P1_UNKNOWN_HISTORICAL_PLAN_FIELDS")
        closed(manifest, MANIFEST_FIELDS, "P1_UNKNOWN_HISTORICAL_MANIFEST_FIELDS")
        anchor = _json(plan["anchor"])
        closed(anchor, ANCHOR_FIELDS, "P1_UNKNOWN_HISTORICAL_ANCHOR_FIELDS")
        source = _json(plan["source_manifest"])
        profile = mapping(chain.current.envelope["profile"], "P1_UNKNOWN_HISTORICAL_PROFILE")
        if (plan["schema"] != "P0-UNKNOWN-OFF-PLAN-1.0" or plan["operation"] != "INSPECT_UNKNOWN_LOCAL_OFF"
            or plan["continuity_enabled"] is not False or plan["ledger_writes_allowed"] is not False
            or type(plan["provider_calls_allowed"]) is not int or plan["provider_calls_allowed"] != 0
            or not digest(plan["origin_tip_permission_sha256"])
            or plan["origin_tip_permission_sha256"] != chain.current.permission_sha256
            or source["source_commit"] != plan["baseline_commit"] or source["source_tree"] != plan["source_tree"]
            or anchor["schema"] != "P0-UNKNOWN-OFF-ANCHOR-1.0" or manifest["schema"] != "P0-UNKNOWN-OFF-MANIFEST-1.0"
            or canonical(manifest["anchor"]) != canonical(plan["anchor"])
            or canonical(manifest["historical_manifest"]) != canonical(profile["continuity_manifest"])
            or canonical(anchor["prior_anchor"]) != canonical(profile["continuity_anchor"])
            or canonical(anchor["original_anchor"]) != canonical(chain.anchor["original_anchor"])
            or any(anchor[k] != chain.manifest[k] for k in ("root_permission_sha256", "campaign_namespace_sha256", "root_lock_sha256"))
            or canonical(anchor["owner_diagnostic"]) != canonical(disposition["owner_diagnostic"])
            or canonical(plan["operator_delegation"]) != canonical(profile["operator_delegation"])
            or canonical(plan["target_runtime"]) != canonical(profile["runtime"])
            or not utc(chain.root.permission["issued_at_utc"]) <= utc(plan["issued_at_utc"])
                < utc(plan["expires_at_utc"]) <= utc(chain.root.permission["expires_at_utc"])):
            raise ValueError("P1_UNKNOWN_HISTORICAL_CONTEXT_BINDING")
        for key in ("orientation_adoption", "prior_design_review"):
            read_descriptor(anchor[key], json_document=False)

    @staticmethod
    def _history_adoption(history: Document, plan: Document, manifest: Document, disposition: Document,
        chain: BoundChainV2) -> None:
        control = _json(history["off_adoption"])
        book = _json(history["off_book"])
        if canonical(control["book"]) != canonical(history["off_book"]):
            raise ValueError("P1_UNKNOWN_HISTORICAL_BOOK_BINDING")
        owner = _json(control["owner_evidence"], canonical_required=False)
        components = {"plan_sha256": descriptor(history["off_plan"])["sha256"],
            "anchor_sha256": descriptor(plan["anchor"])["sha256"], "manifest_sha256": descriptor(plan["manifest"])["sha256"],
            "disposition_sha256": descriptor(manifest["unknown_disposition"])["sha256"],
            "source_manifest_sha256": descriptor(plan["source_manifest"])["sha256"], "package_sha256": descriptor(plan["package"])["sha256"]}
        validate_off_adoption(control, book, owner, components=components,
            owner_raw_sha256=str(descriptor(control["owner_evidence"])["sha256"]),
            expected_owner_sha256=str(history["off_expected_owner_sha256"]))
        validate_owner_diagnostic(_json(disposition["owner_diagnostic"], canonical_required=False), chain=chain, disposition=disposition)
        report = _json(history["off_result"], canonical_required=False)
        closed(report, {"schema", "timestamp_utc", "source_commit", "source_tree", "package_sha256", "plan_sha256",
            "book_sha256", "binding_sha256", "expected_owner_sha256", "provider_calls", "sql_queries", "original_mutations",
            "new_grants", "quota_reset", "on_activation", "course_qualification", "teaching_acceptance", "stage", "state", "observation"},
            "P1_UNKNOWN_ACQUIRED_RESULT_FIELDS")
        observed = mapping(report["observation"], "P1_UNKNOWN_ACQUIRED_OBSERVATION")
        projected = P1CampaignInspectionView({**observed, "schema": "P0-PRODUCT-UNKNOWN-OFF-OBSERVATION-1.0"}).as_dict()
        if (canonical(projected) != canonical(observed)
            or report["schema"] != "LU-P1-ACTUAL-APPLICATION-UNKNOWN-OFF-INSPECTION-1.0"
            or report["state"] != "APPLICATION_OFF_INSPECTION_SUCCEEDED_NO_EFFECT_AUTHORITY"
            or report["stage"] != "APPLICATION_INBOUND_INSPECT"
            or any(type(report[k]) is not int or report[k] != 0 for k in ("provider_calls", "sql_queries", "original_mutations", "new_grants"))
            or report["quota_reset"] is not False or report["on_activation"] is not False
            or report["course_qualification"] != "NOT_COMPLETED" or report["teaching_acceptance"] != "NOT_ENGAGED_NOT_SIGNED"
            or report["expected_owner_sha256"] != history["off_expected_owner_sha256"]
            or report["source_commit"] != plan["baseline_commit"] or report["source_tree"] != plan["source_tree"]
            or report["package_sha256"] != descriptor(plan["package"])["sha256"]
            or report["plan_sha256"] != components["plan_sha256"] or report["book_sha256"] != sha(canonical(book))
            or observed["inspection_plan_sha256"] != components["plan_sha256"]
            or any(observed[k] != chain.manifest[k] for k in ("campaign_namespace_sha256", "root_permission_sha256", "root_lock_sha256"))
            or observed["origin_tip_permission_sha256"] != chain.current.permission_sha256
            or observed["disposition_sha256"] != components["disposition_sha256"]
            or observed["reserved_budget_usd"] != manifest["expected_reserved_budget_usd"]
            or not utc(plan["issued_at_utc"]) <= utc(observed["timestamp_utc"]) < utc(plan["expires_at_utc"])):
            raise ValueError("P1_UNKNOWN_ACQUIRED_RESULT_BINDING")

    def _read_files(self) -> Mapping[Path, tuple[Path, str]]:
        files = dict(super()._read_files())
        seen: set[Path] = set()

        def add(path: Path, pin: str) -> None:
            if path in files and files[path][1] != pin:
                raise ValueError("P0_READSET_AMBIGUOUS_PIN")
            files[path] = (path.parent, pin)

        def walk(value: object) -> None:
            if isinstance(value, Mapping):
                if set(value) == {"path", "sha256"}:
                    desc = descriptor(value)
                    path, pin = Path(str(desc["path"])), str(desc["sha256"])
                    add(path, pin)
                    if path not in seen:
                        seen.add(path)
                        if path.suffix.casefold() == ".json":
                            walk(_json(desc, canonical_required=False))
                        else:
                            read_descriptor(desc, json_document=False)
                else:
                    for child in value.values():
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        for path in (self.operation_path, self.operation_adoption):
            value, pin = _document(path)
            add(path, pin)
            walk(value)
        return files
