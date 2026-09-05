"""M08 exact-version candidate projection; not an agent ProductionCandidate."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.conversation import (
    RETENTION,
    identity,
    plain,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping


@dataclass(frozen=True, slots=True)
class ProductionReadView:
    production_ref: str
    version_ref: str
    conversation_id: str
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        identity(self.production_ref, "prod")
        identity(self.version_ref, "ver")
        identity(self.conversation_id, "conv")
        if set(self.data) != {
            "production_ref", "version_ref", "production_kind", "content", "sections",
            "pedagogical_context", "context_sha256", "lineage", "references",
            "validation_state", "limitations", "retention",
        }:
            raise ValueError("INVALID_PRODUCTION_VIEW")
        lineage = self.data["lineage"]
        if not isinstance(lineage, Mapping) or set(lineage) != {
            "source_run_id", "source_step_id", "evidence_set_ref", "source_request_id",
            "conversation_id", "context_sha256", "parent_production_ref",
        }:
            raise ValueError("INVALID_PRODUCTION_LINEAGE")
        context = ConfirmedConversationContext(cast(Mapping[str, object], self.data["pedagogical_context"]))
        if (context.sha256 != self.data["context_sha256"] or lineage["context_sha256"] != context.sha256
                or lineage["conversation_id"] != self.conversation_id or lineage["parent_production_ref"] is not None):
            raise ValueError("INVALID_PRODUCTION_LINEAGE")
        identity(lineage["source_request_id"], "req")
        ConversationDraft(self.production_ref, cast(str, self.data["content"]),
            tuple(cast(tuple[Mapping[str, object], ...], self.data["sections"])),
            tuple(cast(tuple[Mapping[str, object], ...], self.data["references"])),
            {key: lineage[key] for key in ("source_run_id", "source_step_id", "evidence_set_ref")},
            tuple(cast(tuple[str, ...], self.data["limitations"])))
        if (self.data["production_ref"] != self.production_ref
                or self.data["version_ref"] != self.version_ref
                or self.data["production_kind"] != "ASSESSMENT"
                or self.data["validation_state"] != "CANDIDATE"
                or self.data["retention"] != RETENTION):
            raise ValueError("INVALID_PRODUCTION_VIEW")
        if len(json.dumps(plain(self.data), ensure_ascii=False).encode()) > 250 * 1024:
            raise ValueError("PRODUCTION_VIEW_TOO_LARGE")
        object.__setattr__(self, "data", freeze_safe_mapping(self.data))

    @classmethod
    def from_draft(
        cls, draft: ConversationDraft, request: ConversationDraftRequest, version_ref: str,
    ) -> ProductionReadView:
        if set(draft.lineage) != {"source_run_id", "source_step_id", "evidence_set_ref"}:
            raise ValueError("INVALID_DRAFT_LINEAGE")
        lineage = dict(draft.lineage)
        lineage.update(source_request_id=request.request_id,
                       conversation_id=request.conversation_id,
                       context_sha256=request.context.sha256, parent_production_ref=None)
        return cls(draft.production_ref, version_ref, request.conversation_id, {
            "production_ref": draft.production_ref, "version_ref": version_ref,
            "production_kind": "ASSESSMENT", "content": draft.content,
            "sections": draft.sections, "pedagogical_context": request.context.as_dict(),
            "context_sha256": request.context.sha256, "lineage": lineage,
            "references": draft.references, "validation_state": "CANDIDATE",
            "limitations": draft.limitations, "retention": RETENTION,
        })
