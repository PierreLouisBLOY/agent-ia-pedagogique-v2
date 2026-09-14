"""Exact existing-version restoration data; not an import or publication command."""

from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    encoded,
    fingerprint,
    object_data,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialValidationScope,
    verify_editorial_scope,
)
from backend.modules.work_orchestration.contracts.dto.conversation import ConversationState
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.shared_kernel._safe_data import freeze_safe_mapping


@dataclass(frozen=True, slots=True)
class R3RestorationSnapshot:
    state: ConversationState
    views: tuple[ProductionReadView, ProductionReadView]
    bundles: tuple[AssessmentBundle, AssessmentBundle]
    review: Mapping[str, object]
    receipt: Mapping[str, object]
    scope: EditorialValidationScope

    def __post_init__(self) -> None:
        if (
            type(self.state) is not ConversationState
            or type(self.views) is not tuple
            or type(self.bundles) is not tuple
            or len(self.views) != 2
            or len(self.bundles) != 2
            or type(self.scope) is not EditorialValidationScope
        ):
            raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
        parent, child = self.bundles
        if any(type(b) is not AssessmentBundle for b in self.bundles):
            raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
        for view, bundle in zip(self.views, self.bundles, strict=True):
            if (
                type(view) is not ProductionReadView
                or (view.production_ref, view.version_ref, view.conversation_id)
                != (bundle.production_ref, bundle.version_ref, self.state.conversation_id)
                or fingerprint({"content": view.data["content"], "sections": view.data["sections"]})
                != bundle.data["subject_sha256"]
                or self.state.view.get("confirmed_context_sha256") != view.data["context_sha256"]
            ):
                raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
        if (
            parent.production_ref != child.production_ref
            or parent.version_ref == child.version_ref
            or self.state.view.get("current_candidate")
            != {"production_ref": child.production_ref, "version_ref": child.version_ref}
            or self.state.view.get("active_generation") is not None
            or self.state.receipts
            or self.state.conflicts
            or self.scope.parent.sha256 != parent.sha256
            or self.scope.child.sha256 != child.sha256
            or not verify_editorial_scope(self.scope, parent=parent, candidate=child.data)
            or encoded(self.review) != encoded(self.scope.evidence.review)
        ):
            raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
        receipt = object_data(
            self.receipt,
            {
                "operation_ref",
                "state",
                "command_id",
                "production_ref",
                "version_ref",
                "revision",
                "review_ref",
                "bundle_sha256",
                "review_status",
                "validation_status",
            },
        )
        if (
            receipt["state"] != "SUCCEEDED"
            or receipt["operation_ref"] != self.scope.operation_ref
            or receipt["command_id"] != self.scope.command_id
            or receipt["production_ref"] != child.production_ref
            or receipt["version_ref"] != child.version_ref
            or receipt["bundle_sha256"] != child.sha256
            or type(receipt["revision"]) is not int
            or receipt["revision"] < 1
            or receipt["review_ref"] is not None
            or receipt["review_status"] != "REVIEW_NOT_RUN"
            or receipt["validation_status"] not in {"PASS", "WARNING"}
        ):
            raise ValueError("RESTORATION_SOURCE_INCOMPLETE")
        object.__setattr__(self, "review", freeze_safe_mapping(self.review))
        object.__setattr__(self, "receipt", freeze_safe_mapping(receipt))
