"""Default OFF composition with exact technical owner evidence injected outside requests."""
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence

from backend.adapters.inbound.application.stmg_local_activity import STMGLocalActivityInbound
from backend.modules.pedagogical_context.contracts.dto.stmg_local_activity import (
    LocalActivityOwnerScope,
    require_hash,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data
from backend.modules.work_orchestration.application.queries.stmg_local_activity import (
    PrepareSTMGLocalActivity,
)


def build_stmg_local_activity_application(*, choices: Sequence[Mapping[str, object]],
        owner_scope: LocalActivityOwnerScope, expected_owner_scope_sha256: str,
        owner_decision_evidence: bytes, expected_owner_decision_sha256: str,
        basis_reader: Callable[[str], Mapping[str, object]],
        source_reader: Callable[[Mapping[str, object]], Mapping[str, object]],
        enabled: bool = False) -> STMGLocalActivityInbound:
    """Normal composition: trusted owner evidence/scope outside request; no I/O."""
    if type(enabled) is not bool:
        raise ValueError("LOCAL_ACTIVITY_ENABLED_BOOL_REQUIRED")
    if (not isinstance(owner_decision_evidence, bytes) or not 1 <= len(owner_decision_evidence) <= 65536
            or hashlib.sha256(owner_decision_evidence).hexdigest() != require_hash(expected_owner_decision_sha256)):
        raise ValueError("LOCAL_ACTIVITY_OWNER_EVIDENCE")
    if (not isinstance(owner_scope, LocalActivityOwnerScope)
            or owner_scope.sha256 != require_hash(expected_owner_scope_sha256)
            or owner_scope.data["owner_local_decision_sha256"] != expected_owner_decision_sha256):
        raise ValueError("LOCAL_ACTIVITY_OWNER_SCOPE")
    try:
        evidence = object_data(json.loads(owner_decision_evidence))
        decisions = items(evidence.get("decisions"), 32)
        decision = decisions[int(str(owner_scope.data["decision_item"]))]
    except (ValueError, IndexError, TypeError, UnicodeError, KeyError) as error:
        raise ValueError("LOCAL_ACTIVITY_OWNER_EVIDENCE") from error
    if (evidence.get("schema") != "LU-OWNER-LOCAL-DECISIONS-UI-REPLY-1.0"
            or decision.get("item") != owner_scope.data["decision_item"]
            or decision.get("proposal_sha256") != owner_scope.data["owner_proposal_sha256"]
            or not isinstance(decision.get("answer_verbatim"), str)
            or not decision.get("answer_verbatim")):
        raise ValueError("LOCAL_ACTIVITY_OWNER_EVIDENCE")
    query = PrepareSTMGLocalActivity(choices, owner_scope=owner_scope,
        expected_owner_scope_sha256=expected_owner_scope_sha256,
        basis_reader=basis_reader, source_reader=source_reader, enabled=enabled)
    return STMGLocalActivityInbound(query)
