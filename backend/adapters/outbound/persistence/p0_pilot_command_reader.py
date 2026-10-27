"""Targeted read of one recipe's PENDING under its retained original LOCK.

There is no publication, recovery, credential, broker or transport entry point.
The adapter observes only linked files; absence is never remote non-execution.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from backend.adapters.outbound.generation.openai.p0_normal_policy import (
    HASH_FIELDS,
    canonical,
    closed,
    digest,
    money,
    sha,
    utc,
    validate_grant,
)
from backend.adapters.outbound.generation.openai.p0_normal_receipt import (
    P0NormalReceipt,
    decode,
    pinned_receipt_root,
)
from backend.adapters.outbound.generation.openai.p0_product_ledger import SLOT_FIELDS
from backend.adapters.outbound.persistence.p0_pilot_confirmation import P0PilotConfirmationStore
from backend.adapters.outbound.persistence.p0_pilot_incident import P0PilotIncidentDisposition
from backend.adapters.outbound.persistence.p0_pilot_retained_child import (
    RIGHT_ID,
    P0PilotRetainedChildDisposition,
)
from backend.core_contracts.outcome import ApplicationFailureKind
from backend.infrastructure.filesystem import capture_secure_path, read_file_nofollow
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionPortError,
)

DOCUMENTS = ("permission", "decision", "envelope", "authority", "effect")
EVENTS = ("RESERVED", "DISPATCH", "PROVIDER_ATTEMPTED", "RESULT", "RESPONSE_CAPTURED",
    "PARSED", "CONSUMED", "UNKNOWN", "PARSING_REJECTED")


@dataclass(frozen=True)
class ValidatedPilotCommandInspection:
    profile_sha256: str
    recipe: Mapping[str, object]
    confirmation_root: Path
    documents_root: Path
    receipt_root: Path
    parent: P0PilotIncidentDisposition
    original_lock: Callable[[], AbstractContextManager[None]]
    expected_documents: Callable[[Mapping[str, object]], Mapping[str, Mapping[str, object]]]
    command_id: str | None = None


class P0PilotCommandReader:
    """Public API is an inspection port, with no writable ledger exposed."""

    def __init__(self, *, loader: Callable[[], ValidatedPilotCommandInspection],
            profile_sha256: str, clock: Callable[[], datetime]) -> None:
        if not digest(profile_sha256):
            raise ValueError("P1_PILOT_INSPECTION_PROFILE_REQUIRED")
        self._loader, self._identity, self._clock = loader, profile_sha256, clock

    def inspect(self, *, inspection_ref: str,
            expected_plan_or_profile_sha256: str) -> Mapping[str, object]:
        if (inspection_ref != "p1-inspection:" + self._identity
                or expected_plan_or_profile_sha256 != self._identity):
            raise P1CampaignInspectionPortError(ApplicationFailureKind.AF_MAPPING_CORRUPTION)
        try:
            return self._inspect()
        except P1CampaignInspectionPortError:
            raise
        except ValueError as error:
            kind = (ApplicationFailureKind.AF_CONCURRENCY
                if str(error) == "P0_PRODUCT_CONCURRENT_DISPATCH"
                else ApplicationFailureKind.AF_MAPPING_CORRUPTION)
            raise P1CampaignInspectionPortError(kind) from None
        except OSError:
            raise P1CampaignInspectionPortError(ApplicationFailureKind.AF_PORT_UNAVAILABLE) from None

    @staticmethod
    def _read(root: Path, path: Path, observations: dict[Path, tuple[Path, str]],
              *, expected: str | None = None, maximum_bytes: int = 1_000_000
              ) -> tuple[dict[str, object], str]:
        before = capture_secure_path(path, allowed_root=root)
        raw = read_file_nofollow(path, allowed_root=root, maximum_bytes=maximum_bytes)
        if not before.same_state(capture_secure_path(path, allowed_root=root)):
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        pin = sha(raw)
        if expected is not None and pin != expected:
            raise ValueError("P1_PILOT_INSPECTION_LINK_CHANGED")
        observations[path] = (root, pin)
        return decode(raw), pin

    def _inspect(self) -> Mapping[str, object]:
        initial = self._loader()
        if initial.profile_sha256 != self._identity:
            raise ValueError("P1_PILOT_INSPECTION_PROFILE_CHANGED")
        with initial.original_lock():
            current = self._loader()
            if (current.profile_sha256 != self._identity
                    or canonical(current.recipe) != canonical(initial.recipe)
                    or current.command_id != initial.command_id
                    or (current.confirmation_root, current.documents_root, current.receipt_root)
                        != (initial.confirmation_root, initial.documents_root, initial.receipt_root)):
                raise ValueError("P1_PILOT_INSPECTION_BINDING_CHANGED")
            with (pinned_receipt_root(current.confirmation_root),
                    pinned_receipt_root(current.documents_root),
                    pinned_receipt_root(current.receipt_root)):
                result = self._locked_read(current)
                final = self._loader()
                if (final.profile_sha256 != self._identity
                        or canonical(final.recipe) != canonical(current.recipe)
                        or final.command_id != current.command_id):
                    raise ValueError("P1_PILOT_INSPECTION_BINDING_CHANGED")
                return result

    def _locked_read(self, loaded: ValidatedPilotCommandInspection) -> Mapping[str, object]:
        recipe_sha = sha(canonical(loaded.recipe))
        retained = isinstance(loaded.parent, P0PilotRetainedChildDisposition)
        if retained and (loaded.recipe.get("schema") != "P1-PILOT-CONFIRMATION-RECIPE-1.1"
                or loaded.recipe.get("right_id") != RIGHT_ID or loaded.command_id is None):
            raise ValueError("P1_PILOT_INSPECTION_RIGHT_CHANGED")
        confirmation = P0PilotConfirmationStore(loaded.confirmation_root,
            recipe_sha256=recipe_sha, baseline_slots=5 if retained else 4,
            right_id=RIGHT_ID if retained else None)
        # retained_pending only reads. An EXPIRED_NO_SLOT still consumes the
        # punctual right; this view never calls expiration or a recovery path.
        records = confirmation._pending_records()
        pending_rows = [row for row in records
            if row["schema"] == confirmation.pending_schema]
        if retained and not pending_rows:
            return self._no_pending(loaded, confirmation, records)
        if len(pending_rows) != 1:
            raise ValueError("P1_PILOT_INSPECTION_EXACT_PENDING_REQUIRED")
        pending = pending_rows[0]
        command = str(pending["command_id"])
        if (re.fullmatch(r"[0-9a-f]{32}", command) is None
                or command in {item.command for item in loaded.parent.retained()}
                or loaded.command_id is not None and command != loaded.command_id
                or pending["recipe_sha256"] != recipe_sha
                or any(pending[key] is not True for key in (
                    "transfer_accepted", "cost_bound_accepted", "double_execution_cost_risk_accepted"))):
            raise ValueError("P1_PILOT_INSPECTION_PENDING_CHANGED")
        observations: dict[Path, tuple[Path, str]] = {}
        absent_paths: list[tuple[Path, Path]] = []
        pending_path = loaded.confirmation_root / (
            f"p0-confirmation.{recipe_sha}.{command}.PENDING.json")
        observed_pending, pending_sha = self._read(loaded.confirmation_root,
            pending_path, observations, expected=sha(canonical(pending)))
        if observed_pending != pending:
            raise ValueError("P1_PILOT_INSPECTION_PENDING_CHANGED")
        confirmations = [{"state": "PENDING", "sha256": pending_sha,
            "timestamp_utc": pending["issued_at_utc"]}]
        terminals = [row for row in records
            if row["schema"] == "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0"]
        if retained:
            terminal_path = loaded.confirmation_root / (
                f"p0-confirmation.{recipe_sha}.{command}.EXPIRED_NO_SLOT.json")
            if capture_secure_path(terminal_path, allowed_root=loaded.confirmation_root).exists:
                terminal, _ = self._read(loaded.confirmation_root, terminal_path, observations)
                closed(terminal, {"schema", "recipe_sha256", "command_id", "pending_sha256",
                    "expired_at_utc", "state"}, "P1_PILOT_INSPECTION_CONFIRMATION_FIELDS")
                if (terminal["schema"] != "P1-PILOT-CONFIRMATION-EXPIRED-NO-SLOT-1.0"
                        or terminal["recipe_sha256"] != recipe_sha):
                    raise ValueError("P1_PILOT_INSPECTION_CONFIRMATION_CHANGED")
                terminals.append(terminal)
            else:
                absent_paths.append((loaded.confirmation_root, terminal_path))
        if len(terminals) > 1:
            raise ValueError("P1_PILOT_INSPECTION_CONFIRMATION_CHANGED")
        for terminal in terminals:
            if (terminal["command_id"] != command or terminal["pending_sha256"] != pending_sha
                    or terminal["state"] != "EXPIRED_NO_SLOT"):
                raise ValueError("P1_PILOT_INSPECTION_CONFIRMATION_CHANGED")
            _, terminal_sha = self._read(loaded.confirmation_root,
                loaded.confirmation_root / f"p0-confirmation.{recipe_sha}.{command}.EXPIRED_NO_SLOT.json",
                observations, expected=sha(canonical(terminal)))
            confirmations.append({"state": "EXPIRED_NO_SLOT", "sha256": terminal_sha,
                "timestamp_utc": terminal["expired_at_utc"]})
        revoked_path = confirmation._revoked()
        revoked_absent = not capture_secure_path(revoked_path, allowed_root=loaded.confirmation_root).exists
        if not revoked_absent:
            revoked, revoked_sha = self._read(loaded.confirmation_root, revoked_path, observations)
            closed(revoked, {"schema", "recipe_sha256", "revoked_at_utc", "operator"}
                | ({"right_id"} if retained else set()),
                "P1_PILOT_INSPECTION_REVOCATION_FIELDS")
            if (revoked["schema"] != "P1-PILOT-REVOKED-1.0"
                    or (revoked["right_id"] != RIGHT_ID if retained
                        else revoked["recipe_sha256"] != recipe_sha)):
                raise ValueError("P1_PILOT_INSPECTION_REVOCATION_CHANGED")
            confirmations.append({"state": "REVOKED", "sha256": revoked_sha,
                "timestamp_utc": revoked["revoked_at_utc"]})
        expected_docs = loaded.expected_documents(pending)
        docs: dict[str, dict[str, object]] = {}
        pins: dict[str, str] = {}
        for key in DOCUMENTS:
            docs[key], pins[key] = self._read(loaded.documents_root,
                loaded.documents_root / f"p0-derived.{command}.{key}.json",
                observations, expected=str(pending[f"{key}_sha256"]))
            if canonical(docs[key]) != canonical(expected_docs[key]):
                raise ValueError("P1_PILOT_INSPECTION_DERIVATION_CHANGED")
        if any(pending[key] != docs["authority"][key]
                for key in ("issued_at_utc", "expires_at_utc")):
            raise ValueError("P1_PILOT_INSPECTION_PENDING_CHANGED")
        permission = docs["permission"]
        campaign = permission["permission_namespace_sha256"]
        if not digest(campaign):
            raise ValueError("P1_PILOT_INSPECTION_NAMESPACE_CHANGED")
        slot_path = loaded.receipt_root / (
            f"{campaign}.P1.{pending['normal_preview_sha256']}.json")
        slot: dict[str, object] | None = None
        slot_sha: str | None = None
        rows: list[dict[str, object]] = []
        response_status: str | None = None
        response_metadata: dict[str, object] | None = None
        failure_evidence: dict[str, object] = {"state": "NOT_OBSERVED_WITHOUT_SLOT",
            "sha256": None, "document": None}
        if capture_secure_path(slot_path, allowed_root=loaded.receipt_root).exists:
            slot, slot_sha = self._read(loaded.receipt_root, slot_path, observations)
            self._slot(slot, pending=pending, recipe=loaded.recipe, permission=permission)
            rows, response_status, response_metadata, failure_evidence = self._receipts(
                loaded, slot=slot, observations=observations, absent_paths=absent_paths,
                include_diagnostic=retained)
        parents = self._parents(loaded, require_disposition=retained,
            observations=observations, absent_paths=absent_paths)
        parent = parents["parent_406a"]
        # Check the full targeted read set again before releasing the LOCK.
        if confirmation._pending_records() != records:
            raise ValueError("P1_PILOT_INSPECTION_PENDING_CHANGED")
        for path, (root, expected) in observations.items():
            self._read(root, path, {}, expected=expected)
        if slot is None and capture_secure_path(slot_path, allowed_root=loaded.receipt_root).exists:
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        if revoked_absent and capture_secure_path(revoked_path, allowed_root=loaded.confirmation_root).exists:
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        loaded.parent.sources_checked()
        if any(capture_secure_path(path, allowed_root=root).exists for root, path in absent_paths):
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        seen = {str(row["state"]) for row in rows}
        result: dict[str, object] = {"schema": ("P0-PILOT-COMMAND-INSPECTION-1.1" if retained
                else "P0-PILOT-COMMAND-INSPECTION-1.0"),
            "state": "RETAINED_PENDING_OBSERVED_NO_REPLAY", "timestamp_utc": self._clock().isoformat(),
            "inspection_profile_sha256": self._identity, "recipe_sha256": recipe_sha,
            "command_id": command,
            **{key: loaded.recipe[key] for key in ("request_sha256", "preparation_sha256",
                "context_sha256", "reference_set_sha256", "parent_unknown_request_sha256")},
            "pending_sha256": pending_sha,
            "stable_preview_sha256": pending["stable_preview_sha256"],
            "normal_preview_sha256": pending["normal_preview_sha256"],
            "issued_at_utc": pending["issued_at_utc"], "expires_at_utc": pending["expires_at_utc"],
            "confirmation_receipts": confirmations,
            "derived_document_sha256s": pins, "slot_sha256": slot_sha,
            "namespace_sha256": slot["namespace_sha256"] if slot else None,
            "reserved_usd": slot["reserved_usd"] if slot else None,
            "receipts": rows, "parent_406a": parent,
            "right_status": "CONSUMED_AT_PENDING_NO_NEW_RIGHT",
            "provider_departure_status": ("RESPONSE_ARTIFACT_OBSERVED" if "RESULT" in seen
                else "ATTEMPT_MARKER_OBSERVED_NOT_REMOTE_RECEIPT"
                if "PROVIDER_ATTEMPTED" in seen else "NOT_ESTABLISHED"),
            "response_artifact_present": "RESULT" in seen,
            "response_status": response_status,
            "actual_billed_cost_status": "NOT_ESTABLISHED",
            "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
            "reservation_scope": ("THIS_CHILD_406A_2F1E_NOT_CAMPAIGN_TOTAL" if retained
                else "THIS_CHILD_AND_406A_ONLY_NOT_CAMPAIGN_TOTAL"),
            "live_enabled": False, "effect_permitted": False,
            "provider_calls": 0, "ledger_mutations": 0}
        if retained:
            result.update(right_id=RIGHT_ID, parent_2f1e=parents["parent_2f1e"],
                response_metadata=response_metadata, failure_evidence=failure_evidence)
        return result

    def _parents(self, loaded: ValidatedPilotCommandInspection, *,
                 require_disposition: bool = False,
                 observations: dict[Path, tuple[Path, str]] | None = None,
                 absent_paths: list[tuple[Path, Path]] | None = None) -> dict[str, object]:
        result: dict[str, object] = {}
        for item in loaded.parent.retained():
            sources = item.sources_checked()
            present = capture_secure_path(item.path, allowed_root=loaded.confirmation_root).exists
            if present:
                item.read()
                if observations is not None:
                    self._read(loaded.confirmation_root, item.path, observations,
                        expected=item.expected_sha256, maximum_bytes=8192)
            elif require_disposition:
                raise ValueError("P1_PILOT_INSPECTION_DISPOSITION_REQUIRED")
            elif absent_paths is not None:
                absent_paths.append((loaded.confirmation_root, item.path))
            row = {"command_id": item.command, "state": "RETAINED_SEPARATE_OUTCOME_UNKNOWN",
                **{name + "_sha256": item.sources[name] for name in item.source_names},
                "reserved_usd": sources["slot"]["reserved_usd"],
                "actual_billed_cost_status": "NOT_ESTABLISHED"}
            if isinstance(item, P0PilotRetainedChildDisposition):
                row["disposition_sha256"] = item.expected_sha256 if present else None
                result["parent_2f1e"] = row
            else:
                result["parent_406a"] = row
        return result

    def _no_pending(self, loaded: ValidatedPilotCommandInspection,
                    confirmation: P0PilotConfirmationStore,
                    records: list[dict[str, object]]) -> Mapping[str, object]:
        observations: dict[Path, tuple[Path, str]] = {}
        absent_paths: list[tuple[Path, Path]] = []
        parents = self._parents(loaded, observations=observations, absent_paths=absent_paths)
        recipe_sha = sha(canonical(loaded.recipe))
        absent_names = [loaded.confirmation_root /
            f"p0-confirmation.{recipe_sha}.{loaded.command_id}.{kind}.json"
            for kind in ("PENDING", "EXPIRED_NO_SLOT")]
        if any(capture_secure_path(path, allowed_root=loaded.confirmation_root).exists
                for path in absent_names):
            raise ValueError("P1_PILOT_INSPECTION_PENDING_CHANGED")
        revoked_path = confirmation._revoked()
        revoked = confirmation._read(revoked_path)
        if revoked is not None:
            closed(revoked, {"schema", "recipe_sha256", "revoked_at_utc", "operator", "right_id"},
                "P1_PILOT_INSPECTION_REVOCATION_FIELDS")
            if revoked["schema"] != "P1-PILOT-REVOKED-1.0" or revoked["right_id"] != RIGHT_ID:
                raise ValueError("P1_PILOT_INSPECTION_REVOCATION_CHANGED")
        if confirmation._pending_records() != records or confirmation._read(revoked_path) != revoked:
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        if self._parents(loaded) != parents:
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        for path, (root, pin) in observations.items():
            self._read(root, path, {}, expected=pin)
        if any(capture_secure_path(path, allowed_root=root).exists for root, path in absent_paths):
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        if any(capture_secure_path(path, allowed_root=loaded.confirmation_root).exists
                for path in absent_names):
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        return {"schema": "P0-PILOT-COMMAND-INSPECTION-1.1",
            "state": "NO_PENDING_OBSERVED_NO_REPLAY", "timestamp_utc": self._clock().isoformat(),
            "inspection_profile_sha256": self._identity,
            "recipe_sha256": sha(canonical(loaded.recipe)), "command_id": loaded.command_id,
            **{key: loaded.recipe[key] for key in ("request_sha256", "preparation_sha256",
                "context_sha256", "reference_set_sha256", "parent_unknown_request_sha256")},
            "right_id": RIGHT_ID, "right_status": "NOT_ESTABLISHED_NO_NEW_RIGHT",
            "pending_sha256": None, "stable_preview_sha256": None, "normal_preview_sha256": None,
            "issued_at_utc": None, "expires_at_utc": None, "derived_document_sha256s": {},
            "confirmation_receipts": ([{"state": "REVOKED", "sha256": sha(canonical(revoked)),
                "timestamp_utc": revoked["revoked_at_utc"]}] if revoked else []),
            "slot_sha256": None, "namespace_sha256": None, "reserved_usd": None, "receipts": [],
            **parents, "provider_departure_status": "NOT_ESTABLISHED",
            "response_artifact_present": False, "response_status": None, "response_metadata": None,
            "failure_evidence": {"state": "NOT_OBSERVED_WITHOUT_SLOT", "sha256": None, "document": None},
            "actual_billed_cost_status": "NOT_ESTABLISHED",
            "financial_basis": "RESERVATIONS_NOT_BILLED_COST",
            "reservation_scope": "THIS_CHILD_406A_2F1E_NOT_CAMPAIGN_TOTAL",
            "live_enabled": False, "effect_permitted": False, "provider_calls": 0, "ledger_mutations": 0}

    @staticmethod
    def _slot(slot: Mapping[str, object], *, pending: Mapping[str, object],
            recipe: Mapping[str, object], permission: Mapping[str, object]) -> None:
        closed(slot, SLOT_FIELDS, "P1_PILOT_INSPECTION_SLOT_FIELDS")
        grant = slot["grant"]
        if (not isinstance(grant, Mapping)
                or slot["schema"] != "P0-PRODUCT-BUDGET-SLOT-1.0"
                or slot["command_id"] != pending["command_id"]
                or slot["preview_sha256"] != pending["normal_preview_sha256"]
                or slot["permission_sha256"] != pending["permission_sha256"]
                or slot["permission_sha256"] != sha(canonical(permission))
                or slot["grant_sha256"] != sha(canonical(grant))
                or slot["namespace_sha256"] != grant.get("namespace_sha256")
                or slot["request_sha256"] != recipe["request_sha256"]
                or any(grant.get(key) != recipe[key] for key in ("request_sha256",
                    "preparation_sha256", "context_sha256", "reference_set_sha256"))
                or money(slot["reserved_usd"]) != money(recipe["approved_cost_bound_usd"])
                or any(not digest(slot[key]) for key in ("preview_sha256", "grant_sha256",
                    "namespace_sha256", "request_sha256", "preflight_sha256"))):
            raise ValueError("P1_PILOT_INSPECTION_SLOT_CHANGED")
        if (any(grant.get(key) != permission[key] for key in
                (HASH_FIELDS & permission.keys()) | {"baseline_commit"})
                or not utc(pending["issued_at_utc"]) <= utc(grant["issued_at_utc"])
                    < utc(grant["expires_at_utc"]) <= utc(pending["expires_at_utc"])):
            raise ValueError("P1_PILOT_INSPECTION_GRANT_CHANGED")
        validate_grant(grant, identities={key: grant[key]
            for key in HASH_FIELDS | {"baseline_commit", "request_bytes"}},
            now=utc(grant["issued_at_utc"]))

    def _receipts(self, loaded: ValidatedPilotCommandInspection, *, slot: Mapping[str, object],
            observations: dict[Path, tuple[Path, str]],
            absent_paths: list[tuple[Path, Path]], include_diagnostic: bool) -> tuple[
                list[dict[str, object]], str | None, dict[str, object] | None, dict[str, object]]:
        namespace = str(slot["namespace_sha256"])
        receipt = P0NormalReceipt(loaded.receipt_root, namespace)
        records: dict[str, dict[str, object]] = {}
        rows = []
        absent = []
        for state in EVENTS:
            path = loaded.receipt_root / f"{namespace}.{state}.json"
            if not receipt.exists(state):
                absent.append(state)
                absent_paths.append((loaded.receipt_root, path))
                continue
            record, pin = self._read(loaded.receipt_root, path, observations)
            if any(record.get(key) != slot[key] for key in (
                    "grant_sha256", "request_sha256")):
                raise ValueError("P1_PILOT_INSPECTION_RECEIPT_CHANGED")
            if state != "RESULT" and any(record.get(key) != slot[key]
                    for key in ("namespace_sha256", "preflight_sha256")):
                raise ValueError("P1_PILOT_INSPECTION_RECEIPT_CHANGED")
            if state not in {"RESULT", "DISPATCH"} and (
                    record.get("schema") != "P0-NORMAL-TECHNICAL-RECEIPT-1.0"
                    or record.get("state") != state
                    or money(record.get("reserved_usd")) != money(slot["reserved_usd"])):
                raise ValueError("P1_PILOT_INSPECTION_RECEIPT_CHANGED")
            records[state] = record
            rows.append({"state": state, "sha256": pin,
                "timestamp_utc": record.get("timestamp_utc")})
        if "DISPATCH" in records:
            capture = records["DISPATCH"]
            if (capture.get("schema") != "P0-NORMAL-DISPATCH-CAPTURE-1.0"
                    or not isinstance(capture.get("body"), str)
                    or sha(str(capture["body"]).encode()) != slot["request_sha256"]
                    or not isinstance(capture.get("preflight"), Mapping)
                    or sha(canonical(capture["preflight"])) != slot["preflight_sha256"]
                    or not isinstance(capture.get("dispatch"), Mapping)
                    or sha(canonical(capture["dispatch"])) != capture.get("dispatch_sha256")
                    or canonical(capture.get("grant")) != canonical(slot["grant"])):
                raise ValueError("P1_PILOT_INSPECTION_CAPTURE_CHANGED")
        if "RESULT" in records:
            if "DISPATCH" not in records:
                raise ValueError("P1_PILOT_INSPECTION_ORPHAN_RESULT")
            self._result(records["RESULT"],
                dispatch_sha256=str(records["DISPATCH"]["dispatch_sha256"]))
        if any(receipt.exists(state) for state in absent):
            raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
        diagnostic_path = loaded.receipt_root / f"p0-diagnostic.{namespace}.json"
        diagnostic: dict[str, object] = {"state": "ABSENT_IN_LINKED_NAMESPACE",
            "sha256": None, "document": None}
        if not include_diagnostic:
            diagnostic["state"] = "LEGACY_DIAGNOSTIC_OUTSIDE_SCOPE"
        elif capture_secure_path(diagnostic_path, allowed_root=loaded.receipt_root).exists:
            if "DISPATCH" not in records:
                diagnostic["state"] = "PRESENT_NOT_QUALIFIABLE_WITHOUT_DISPATCH"
                _, diagnostic["sha256"] = self._read(loaded.receipt_root,
                    diagnostic_path, observations, maximum_bytes=8192)
            else:
                capture = records["DISPATCH"]
                value = receipt.read_failure_diagnostic(
                    grant=slot["grant"], preflight=capture["preflight"])  # type: ignore[arg-type]
                if value is None:
                    raise ValueError("P1_PILOT_INSPECTION_READ_CHANGED")
                _, pin = self._read(loaded.receipt_root, diagnostic_path, observations,
                    expected=sha(canonical(value)))
                diagnostic = {"state": "VERIFIED", "sha256": pin, "document": value}
        else:
            absent_paths.append((loaded.receipt_root, diagnostic_path))
        artifact = records.get("RESULT")
        metadata = ({"result_sha256": sha(canonical(artifact)),
            "output_text_sha256": sha(str(artifact["output_text"]).encode())
                if artifact["output_text"] is not None else None,
            "output_text_bytes": len(str(artifact["output_text"]).encode())
                if artifact["output_text"] is not None else None,
            "usage": artifact["usage"]} if artifact else None)
        return rows, str(artifact["response_status"]) if artifact else None, metadata, diagnostic

    @staticmethod
    def _result(artifact: Mapping[str, object], *, dispatch_sha256: str) -> None:
        # Observation accepts the transport's closed statuses. It never invokes
        # recover_binding(), whose completed-only predicate would turn a valid
        # incomplete/failed capture into a failure of the inspection itself.
        closed(artifact, {"schema", "grant_sha256", "request_sha256", "dispatch_sha256",
            "response_status", "output_text", "usage"}, "P1_PILOT_INSPECTION_RESULT_FIELDS")
        if (artifact["schema"] != "P0-NORMAL-CONFIRMED-RESULT-1.0"
                or artifact["dispatch_sha256"] != dispatch_sha256
                or artifact["response_status"] not in {"completed", "incomplete", "failed", "refused"}
                or artifact["output_text"] is not None and type(artifact["output_text"]) is not str
                or not isinstance(artifact["usage"], Mapping)):
            raise ValueError("P1_PILOT_INSPECTION_RESULT_CHANGED")
        usage = artifact["usage"]
        closed(usage, {"input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens",
            "total_tokens", "cache_write_input_tokens"}, "P1_PILOT_INSPECTION_USAGE_FIELDS")
        if any(value is not None and (type(value) is not int or value < 0) for value in usage.values()):
            raise ValueError("P1_PILOT_INSPECTION_USAGE_CHANGED")
        for part, total in (("cached_input_tokens", "input_tokens"),
                ("cache_write_input_tokens", "input_tokens"), ("reasoning_tokens", "output_tokens")):
            if (usage[part] is not None and usage[total] is not None
                    and int(str(usage[part])) > int(str(usage[total]))):
                raise ValueError("P1_PILOT_INSPECTION_USAGE_CHANGED")
