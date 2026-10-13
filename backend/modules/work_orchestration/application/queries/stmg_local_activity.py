"""Pure Application qualification of an exact local STMG activity scope."""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence

from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    OWNER_ADMISSION_SHA256,
)
from backend.modules.knowledge_reference.contracts.dto.stmg_frames import STMG_FRAMES
from backend.modules.pedagogical_context.contracts.dto.stmg_local_activity import (
    LocalActivityChoice,
    LocalActivityOwnerScope,
    project_local_capacities,
    require_hash,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    fingerprint,
    items,
    object_data,
)

BASIS_FIELDS = {"contract_id", "owner_admission_sha256", "positioning", "fragments"}
FRAGMENT_FIELDS = {"purpose", "frame", "level", "program_ref", "program_version", "document", "question", "typed_capacities", "local_extracted_capacities", "native_relation_status"}

class PrepareSTMGLocalActivity:
    """Explicitly enabled pure Application readiness; has no dispatch operation."""
    def __init__(self, choices: Sequence[Mapping[str, object]], *, owner_scope: LocalActivityOwnerScope,
                 expected_owner_scope_sha256: str,
                 basis_reader: Callable[[str], Mapping[str, object]],
                 source_reader: Callable[[Mapping[str, object]], Mapping[str, object]], enabled: bool = False) -> None:
        if type(enabled) is not bool:
            raise ValueError("LOCAL_ACTIVITY_ENABLED_BOOL_REQUIRED")
        if (not isinstance(owner_scope, LocalActivityOwnerScope)
                or owner_scope.sha256 != require_hash(expected_owner_scope_sha256)):
            raise ValueError("LOCAL_ACTIVITY_OWNER_SCOPE")
        self.owner_scope = owner_scope
        self.owner_sha = require_hash(owner_scope.data["owner_local_decision_sha256"])
        self.choices: dict[str, LocalActivityChoice] = {}
        for raw in choices:
            choice = LocalActivityChoice(raw)
            if choice.data["owner_local_decision_sha256"] != self.owner_sha or choice.sha256 in self.choices:
                raise ValueError("LOCAL_ACTIVITY_OWNER_SCOPE")
            self.choices[choice.sha256] = choice
        if not self.choices or len(self.choices) > 64:
            raise ValueError("LOCAL_ACTIVITY_CHOICES")
        if sorted(self.choices) != list(owner_scope.choice_sha256s):
            raise ValueError("LOCAL_ACTIVITY_OWNER_SCOPE")
        self.basis_reader, self.source_reader, self._enabled = basis_reader, source_reader, enabled

    def metadata(self) -> list[dict[str, object]]:
        if not self._enabled:
            return []
        rows = []
        for choice in self.choices.values():
            checked = self.execute(choice.sha256)
            rows.append({"contract_id": "STMG-LOCAL-ACTIVITY-METADATA-1.0", "choice_ref": choice.data["choice_ref"],
                "choice_sha256": choice.sha256, "resource_type": choice.data["resource_type"], "question_mode": choice.data["question_mode"],
                "role": choice.data["role"], "positioning": as_plain(choice.data["positioning"]),
                "local_capability_choices": checked["available_local_capacities"],
                "provider_dispatch_allowed": False, "transmission_admission": "NOT_ADOPTED"})
        return rows

    def execute(self, choice_sha256: str, *, selected_local_capacity_refs: Sequence[str] | None = None) -> dict[str, object]:
        if not self._enabled:
            raise ValueError("LOCAL_ACTIVITY_DISABLED")
        choice = self.choices.get(require_hash(choice_sha256))
        if choice is None:
            raise ValueError("LOCAL_ACTIVITY_NOT_IN_OWNER_SCOPE")
        data = object_data(as_plain(choice.data))
        source = object_data(self.source_reader(object_data(data["source_identity"])))
        if (fingerprint(source) != data["source_snapshot_sha256"] or source.get("excerpt_truncated") is not False
                or source.get("authority", "UNKNOWN") != "UNKNOWN"
                or any(source.get(flag) is True for flag in ("is_private_evidence", "is_oracle", "is_teacher_reference"))):
            raise ValueError("LOCAL_ACTIVITY_NATIVE_SOURCE_CHANGED_OR_EXCLUDED")
        identity = object_data(data["source_identity"])
        if any(source.get(k) != identity[k] for k in ("object_ref", "object_kind", "passage_ref", "version_or_checksum")):
            raise ValueError("LOCAL_ACTIVITY_SOURCE_ID")
        text = source.get("excerpt")
        if (not isinstance(text, str) or len(text.encode("utf-8")) != identity["utf8_bytes"]
                or hashlib.sha256(text.encode("utf-8")).hexdigest() != identity["excerpt_sha256"]
                or source.get("notion_ref") != identity["notion_ref"]):
            raise ValueError("LOCAL_ACTIVITY_SOURCE_TEXT")
        basis = object_data(self.basis_reader(str(data["programme_support_sha256"])), BASIS_FIELDS)
        if (fingerprint(basis) != data["programme_support_sha256"]
                or basis.get("contract_id") != "STMG-LOCAL-PROGRAMME-SUPPORT-1.0"
                or basis.get("owner_admission_sha256") != OWNER_ADMISSION_SHA256):
            raise ValueError("LOCAL_ACTIVITY_PROGRAMME_BASIS_CHANGED")
        host = object_data(basis["positioning"])
        if host != object_data(data["positioning"]):
            raise ValueError("LOCAL_ACTIVITY_POSITIONING_CHANGED")
        fragments = items(basis["fragments"], 4)
        if not fragments:
            raise ValueError("LOCAL_ACTIVITY_PROGRAMME_BASIS_CHANGED")
        available_local: dict[str, dict[str, object]] = {}
        for fragment in fragments:
            object_data(fragment, FRAGMENT_FIELDS)
            support_frame = STMG_FRAMES.get(str(fragment["frame"]))
            if support_frame is None or support_frame[0] != fragment["level"]:
                raise ValueError("LOCAL_ACTIVITY_PROGRAMME_BASIS_CHANGED")
            document = object_data(fragment["document"])
            if ADMITTED_DOCUMENTS.get(str(document.get("candidate_id"))) != document.get("sha256"):
                raise ValueError("LOCAL_ACTIVITY_DOCUMENT_NOT_ADMITTED")
            if fragment["purpose"] not in {"POSITIONING_SUPPORT", "REACTIVATED_FOUNDATION"}:
                raise ValueError("LOCAL_ACTIVITY_BASIS_ROLE")
            question = object_data(fragment["question"])
            if (question["version_ref"] != fragment["program_version"]
                    or question["document_ref"] != document["id"] or question["element_type"] != "QUESTION"
                    or fragment["native_relation_status"] not in {"NOT_ADMITTED_FOR_POSITIONING", "ADMITTED_AT_FOUNDATION_ONLY"}):
                raise ValueError("LOCAL_ACTIVITY_PROGRAMME_BASIS_CHANGED")
            derived = items(fragment["local_extracted_capacities"], 16)
            if derived and as_plain(derived) != project_local_capacities(question, [str(c["exact_text"]) for c in derived]):
                raise ValueError("LOCAL_ACTIVITY_LOCAL_CAPACITY_CHANGED")
            for capacity in derived:
                ref = str(capacity["local_capacity_ref"])
                if ref in available_local:
                    raise ValueError("LOCAL_ACTIVITY_LOCAL_CAPACITY_CHANGED")
                available_local[ref] = {**capacity, "support_level": fragment["level"],
                    "support_frame": fragment["frame"], "positioning_level": host["level"]}
            items(fragment["typed_capacities"], 16)
            if fragment["level"] != host["level"] and (data["role"] != "REACTIVATION"
                    or fragment["purpose"] != "REACTIVATED_FOUNDATION"
                    or (fragment["level"], host["level"]) != ("FIRST_STMG", "FINAL_STMG")):
                raise ValueError("LOCAL_ACTIVITY_CROSS_LEVEL_BASIS")
        if selected_local_capacity_refs is not None and not isinstance(selected_local_capacity_refs, (list, tuple)):
            raise ValueError("LOCAL_ACTIVITY_LOCAL_CAPACITY_SELECTION")
        selected = tuple(available_local) if selected_local_capacity_refs is None else tuple(selected_local_capacity_refs)
        if (len(selected) > 16 or not all(isinstance(ref, str) and ref in available_local for ref in selected)
                or len(set(selected)) != len(selected)):
            raise ValueError("LOCAL_ACTIVITY_LOCAL_CAPACITY_SELECTION")
        local = "LOCAL_CONTEXT_CONTENT_INSUFFICIENT" if data["support_status"] == "INSUFFICIENT_FOR_HISTORICAL_CONTENT" else "LOCAL_CONTEXT_SUPPORTED_FOR_PREPARATION"
        result = {"contract_id": "STMG-LOCAL-ACTIVITY-READINESS-1.0", "state": local,
            "choice_ref": data["choice_ref"], "choice_sha256": choice.sha256, "owner_local_decision_sha256": self.owner_sha,
            "owner_scope_sha256": self.owner_scope.sha256, "owner_evidence_kind": "TECHNICAL_TRANSCRIPTION_NOT_SIGNATURE",
            "positioning": host, "programme_support": basis, "source_identity": identity,
            "source_authority": "UNKNOWN", "source_provenance": as_plain(source.get("provenance", {})),
            "source_status": as_plain(source.get("source_status", {})), "support_status": data["support_status"],
            "available_local_capacities": list(available_local.values()), "selected_local_capacity_refs": list(selected),
            "selected_local_capacities": [available_local[ref] for ref in selected],
            "support_limits": data["support_limits"], "native_relationship_status": "NOT_ADMITTED_FOR_POSITIONING",
            "institutional_alignment": "UNVERIFIED_FOR_LOCAL_ACTIVITY", "provider_dispatch_allowed": False,
            "transmission_admission": "NOT_ADOPTED", "teacher_acceptance": "NOT_PERFORMED", "provider_calls": 0}
        return object_data(as_plain(result))
