"""Synthetic media dossier; production agents and guards stay real."""

from copy import deepcopy

from backend.adapters.inbound.application.stmg_alignment import STMGAlignmentInbound
from backend.modules.knowledge_reference.application.queries.stmg_alignment import ReadSTMGAlignment
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.contracts.dto.production_media import (
    MEDIA_PLAN_CONTRACT,
    MEDIA_PRODUCTION_CONTRACT,
    dependencies,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
from tests import normal_on_323a_fixture as f
from tests.test_codesign_global_324 import composition, simple


def media_composition(*, authority=True, correction=False):
    dispatch, content = simple()
    context = f.context()
    context["institutional_resolution"] = STMGAlignmentInbound(
        ReadSTMGAlignment(f.Catalog())
    ).resolve(context["institutional"], {**f.SOURCE, "notion_id": "notion:shared"})
    dispatch["context"] = context
    dispatch["context_sha256"] = dispatch["lineage"]["context_sha256"] = P0Context(context).sha256
    ref = dispatch["references"][0]
    ref.update(
        source_ref=f.SOURCE["object_ref"],
        locator=f.SOURCE["passage_ref"],
        checksum_or_version=f.SOURCE["version_or_checksum"],
        excerpt_sha256=f.sha(f.SOURCE_TEXT.encode()),
    )
    dispatch["evidence"] = {ref["evidence_id"]: f.SOURCE_TEXT}
    service, generation, review = composition(
        dispatch, content, authority=authority, correction=correction
    )
    raw = service.records[dispatch["version_ref"]].mutable_copy()
    from backend.adapters.outbound.export.local_media import WindowsLocalDiagramRenderer
    from backend.modules.materialization_export.application.services.media_asset import (
        MediaAssetWorker,
    )
    from tests.unit.test_course_media import brief_data

    brief = brief_data(raw["production_ref"])
    brief.update(
        production_ref=raw["production_ref"],
        section_ref="S1",
        institutional_capability_ref="capacity:SGN_PREMIERE",
        notion_refs=["notion:shared"],
        preferred_position="AFTER_DOCUMENT",
    )
    typed = VisualBrief(brief)
    from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
    asset = as_plain(MediaAssetWorker(WindowsLocalDiagramRenderer()).execute(typed).data)
    asset["brief_sha256"] = typed.sha256
    asset["provenance"].update(
        source_sha256=typed.sha256, source_ref="local-original:SYNTHETIC-326"
    )
    raw.update(
        contract_id=MEDIA_PRODUCTION_CONTRACT,
        media_plan={
            "contract_id": MEDIA_PLAN_CONTRACT,
            "version_ref": raw["version_ref"],
            "context_sha256": raw["context_sha256"],
            "no_media_reason": None,
            "entries": [
                {
                    "brief": brief,
                    "asset": asset,
                    "required": True,
                    "dependencies": {
                        k: v for k, v in dependencies(raw).items() if k in {"context", "section:S1"}
                    },
                    "omission_reason": None,
                }
            ],
        },
    )
    root_version = raw["version_ref"]
    raw["version_ref"] = "ver:" + "c" * 32
    raw["lineage"]["parent_version_ref"] = root_version
    raw["media_plan"]["version_ref"] = raw["version_ref"]
    dispatch = deepcopy(dispatch)
    dispatch["version_ref"] = raw["version_ref"]
    dispatch["lineage"] = deepcopy(raw["lineage"])
    parent = P0Production(raw)
    service._receive_generated(dispatch, parent.mutable_copy(), recovered=False)
    return service, generation, review, dispatch, content
