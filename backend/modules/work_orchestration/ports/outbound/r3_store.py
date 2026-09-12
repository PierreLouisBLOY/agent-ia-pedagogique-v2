from collections.abc import Mapping
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import AssessmentBundle
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    AssessmentValidation,
)
from backend.modules.validation_control.contracts.dto.editorial_scope import (
    EditorialValidationScope,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from backend.modules.work_orchestration.contracts.dto.r3_review_modify import R3Command
from backend.modules.work_orchestration.ports.outbound.conversation_store import ConversationStore
from backend.modules.work_orchestration.ports.outbound.production_store import ProductionStore


class R3Store(ConversationStore, ProductionStore, Protocol):
    def r3_bundle(self, production_ref: str, version_ref: str) -> AssessmentBundle | None: ...
    def r3_receipt(self, command: R3Command) -> dict[str, object] | None: ...
    def r3_reserve(self, command: R3Command, operation_ref: str) -> dict[str, object]: ...
    def r3_complete(self, operation_ref: str, result: Mapping[str, object], *,
                    production: ProductionReadView | None = None,
                    bundle: AssessmentBundle | None = None,
                    validation: AssessmentValidation | None = None,
                    review: Mapping[str, object] | None = None,
                    editorial_scope: EditorialValidationScope | None = None) -> None: ...
    def r3_report(self, reference: str, *, review: bool = False) -> dict[str, object]: ...
    def r3_snapshot(self, production_ref: str, version_ref: str) -> dict[str, object]: ...
    def r3_editorial_scope(self, production_ref: str, version_ref: str) -> EditorialValidationScope | None: ...
    def r3_clear(self) -> None: ...
