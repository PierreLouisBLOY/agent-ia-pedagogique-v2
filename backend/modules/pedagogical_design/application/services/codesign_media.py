"""Local retention of exact media; no renderer, network, authority or pixel claim."""

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.contracts.dto.production_media import (
    MEDIA_PRODUCTION_CONTRACT,
    ProductionMediaPlan,
)


def require_codesign_media_parent(parent: P0Production) -> None:
    if "media_plan" in parent.data:
        plan = ProductionMediaPlan(object_data(parent.data["media_plan"]))
        plan.bind(parent.data)
        for audience in ("student", "correction"):
            plan.media(audience)
    elif parent.media_review_context():
        # Chapter briefs have a different dependency contract. Never drop them.
        raise ValueError("P0_CODESIGN_CHAPTER_MEDIA_REBIND_REQUIRED")


def codesign_parent_projection(parent: P0Production) -> dict[str, object]:
    """Same documentary input for preview/execution; image bytes remain local."""
    projection = parent.teacher_projection()
    if "media_plan" not in parent.data and not parent.media_review_context():
        return projection
    projection.pop("media_assets", None)
    if "course_chapter" in projection:
        chapter = object_data(projection["course_chapter"])
        chapter.pop("media_assets", None)
        projection["course_chapter"] = chapter
    projection["retained_media"] = {
        "scope": "DOCUMENTARY_COMMITMENTS_ONLY_NO_PIXELS_SENT",
        "visuals": parent.media_review_context(),
        "pixel_inspection": "NOT_PERFORMED",
    }
    return projection


def retain_codesign_media(parent: P0Production, child: P0Production) -> P0Production:
    require_codesign_media_parent(parent)
    if "media_plan" not in parent.data:
        return child
    if (
        parent.production_ref != child.production_ref
        or parent.data["context_sha256"] != child.data["context_sha256"]
        or parent.data["references"] != child.data["references"]
    ):
        raise ValueError("P0_CODESIGN_MEDIA_PARENT_BINDING")
    if "media_plan" in child.data:
        raise ValueError("P0_CODESIGN_MEDIA_REPLACEMENT_FORBIDDEN")
    data = child.mutable_copy()
    plan = object_data(as_plain(parent.data["media_plan"]))
    # Every declared dependency keeps its old fingerprint. Nothing is reattested.
    plan["version_ref"] = child.version_ref
    exact = ProductionMediaPlan(plan)
    exact.bind(data)
    data.update(contract_id=MEDIA_PRODUCTION_CONTRACT, media_plan=exact.as_dict())
    return P0Production(data)
