"""AG-03 proposes visual briefs through CAP-G02; it never renders or admits media."""
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from backend.agent_runtime.agents.generation import (
    GenerationCoordinator,
    GenerationPort,
    GenerationPreparationRequest,
    GeneratorAgent,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    ContractMeta,
    InvocationStatus,
    ProductionRequest,
)
from backend.core_contracts.capability import CapabilityId
from backend.infrastructure.composition.bindings.r3_agents import version_target
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    items,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.course_chapter import CourseChapter
from backend.modules.pedagogical_design.contracts.dto.visual_brief import (
    FIELDS,
    VisualBrief,
    visual_briefs,
)
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant


class CourseVisualBriefAdapter:
    def __init__(self, port: GenerationPort, *, authorize: Callable[[Mapping[str, object]], bool]) -> None:
        self.port, self.authorize = port, authorize

    def propose(self, record: SavedProduction, requirements: Mapping[str, object]) -> tuple[VisualBrief, ...]:
        bundle = record.p0_bundle
        if bundle is None or "course_chapter" not in bundle.data:
            raise ValueError("VISUAL_COURSE_REQUIRED")
        chapter = CourseChapter(object_data(bundle.data["course_chapter"]))
        student = chapter.projection()
        student.pop("media_assets", None)
        request = {"operation": "PROPOSE_VISUAL_BRIEFS", "record_sha256": record.sha256,
                   "production_ref": record.production_ref, "version_ref": record.version_ref,
                   "student_chapter": student, "requirements": as_plain(requirements)}
        if not self.authorize(request):
            raise ValueError("VISUAL_BRIEF_GENERATION_AUTHORIZATION_REQUIRED")
        now = Instant(datetime.now(UTC))
        meta = ContractMeta(AGENT_CONTRACT_SCHEMA_V1_0, "course-visual", "course-visual", None,
            CorrelationId("course.visual.brief"), now, ActorRef(ActorKind.AGENT, "AG-03"), InvocationStatus.PLANNED)
        canonical = ProductionRequest(meta, "COURSE", "PROPOSE_VISUAL_BRIEFS", "JSON",
            bundle.context.data, {"brief_only": True, "image_generation": False, "source_admission": False},
            (), version_target(record.production_ref, record.version_ref), ("VISUAL_BRIEFS",))
        prepared, result = GeneratorAgent(GenerationCoordinator(self.port)).transform_production(
            request=GenerationPreparationRequest(CapabilityId("CAP-G02"), canonical,
                resolved_inputs=request, output_contract={"contract_id": "VISUAL-BRIEFS-OUTPUT-1.0",
                    "fields": sorted(FIELDS), "maximum_briefs": 8, "no_image_bytes_or_urls": True,
                    "student_answers_excluded": True, "no_business_authority": True}))
        if result.status.value != "SUCCEEDED" or result.source_step_id != prepared.port_request.source_step_id:
            raise ValueError("VISUAL_BRIEF_GENERATION_FAILED")
        payload = object_data(result.structured_payload, {"contract_id", "visual_briefs"})
        if payload["contract_id"] != "VISUAL-BRIEFS-OUTPUT-1.0":
            raise ValueError("VISUAL_BRIEF_GENERATION_CONTRACT")
        briefs = visual_briefs(payload["visual_briefs"])
        context = bundle.context.institutional
        if context is None:
            raise ValueError("VISUAL_INSTITUTIONAL_REQUIRED")
        for brief in briefs:
            brief.bind(record.production_ref,
                documents={str(d["id"]) for d in items(chapter.data["documents"])},
                concepts={str(c["id"]) for c in items(chapter.data["concepts"])},
                capabilities={str(c["source_ref"]) for c in items(chapter.data["capabilities"])},
                notions={str(n) for n in context["notion_refs"]} if isinstance(context["notion_refs"], (tuple, list)) else set())
        return briefs
