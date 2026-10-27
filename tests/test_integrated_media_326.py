import json
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.infrastructure.composition.factories.local_browser import build_saved_application
from backend.modules.pedagogical_design.application.services.codesign_media import (
    codesign_parent_projection,
    retain_codesign_media,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production
from backend.modules.pedagogical_design.contracts.dto.production_media import ProductionMediaPlan
from tests.integrated_326_fixture import media_composition
from tests.test_codesign_safety_324 import command


@pytest.mark.parametrize("direction", ["V2_TO_AI", "AI_TO_V2"])
def test_native_media_chain_keeps_original_and_no_png_in_agent_request(direction, tmp_path):
    service, generation, review, dispatch, _ = media_composition()
    parent = service.records[dispatch["version_ref"]]
    before = parent.sha256
    request = {**command(parent), "direction": direction}
    result = service.execute("codesign", request)
    assert result["state"] == "CODESIGN_CANDIDATE", result
    child = service.records[result["view"]["version_ref"]]
    assert parent.sha256 == before and child.version_ref != parent.version_ref
    old = as_plain(parent.data["media_plan"])
    new = as_plain(child.data["media_plan"])
    assert {**new, "version_ref": old["version_ref"]} == old
    body = json.dumps(as_plain(generation.calls[0].resolved_inputs))
    assert "bytes_base64" not in body and "DOCUMENTARY_COMMITMENTS_ONLY_NO_PIXELS_SENT" in body
    assert "bytes_base64" not in json.dumps(as_plain(review.calls[0].target_payload))
    assert len(generation.calls) == len(review.calls) == 1
    saved = build_saved_application(
        tmp_path / "SYNTHETIC-media",
        create=True,
        source=service.saved_source,
        word_profile="product-v7",
    )
    view = result["view"]
    saved.execute(
        "save",
        body={k: view[k] for k in ("production_ref", "version_ref")},
        correlation="synthetic-326",
    )
    opened = build_saved_application(tmp_path / "SYNTHETIC-media", word_profile="product-v7")
    assert (
        opened.read_local_p0(view["production_ref"], view["version_ref"]).p0_bundle.sha256
        == child.sha256
    )
    for kind in ("student", "correction"):
        raw = opened.execute(
            "word",
            view["production_ref"],
            view["version_ref"],
            kind=kind,
            correlation="synthetic-326",
        )
        with ZipFile(BytesIO(raw)) as z:
            assert (
                z.read("word/media/figure_1.png")
                == ProductionMediaPlan(parent.data["media_plan"]).media(kind)[0].asset.raw
            )
    assert service.execute("codesign", request) == result
    assert len(generation.calls) == 1


def test_changed_anchor_stops_before_review_or_publication():
    service, generation, review, dispatch, content = media_composition()
    parent = service.records[dispatch["version_ref"]]
    generation.content = deepcopy(content)
    generation.content["sections"][0]["text"] += " Nouvelle situation."
    result = service.execute("codesign", command(parent))
    assert result["state"] != "CODESIGN_CANDIDATE", result
    assert len(generation.calls) == 1 and review.calls == []
    assert service.records[parent.version_ref].sha256 == parent.sha256
    assert len(service.records) == 2


def test_no_authority_still_no_effect_with_valid_media():
    service, generation, review, dispatch, _ = media_composition(authority=False)
    result = service.execute("codesign", command(service.records[dispatch["version_ref"]]))
    assert result["state"] == "AUTHORIZATION_REQUIRED"
    assert generation.calls == review.calls == []


def test_rebind_refuses_substitution_and_stale_declared_dependency():
    service, _, _, dispatch, _ = media_composition()
    parent = service.records[dispatch["version_ref"]]
    data = parent.mutable_copy()
    data.pop("media_plan")
    data["contract_id"] = "R6-P0-PRODUCTION-1.0"
    data["version_ref"] = "ver:" + "f" * 32
    data["lineage"]["parent_version_ref"] = parent.version_ref
    candidate = P0Production(data)
    result = retain_codesign_media(parent, candidate)
    assert result.data["media_plan"]["version_ref"] == candidate.version_ref
    with pytest.raises(ValueError, match="REPLACEMENT_FORBIDDEN"):
        retain_codesign_media(parent, result)
    data["sections"][0]["text"] += " modification"
    with pytest.raises(ValueError, match="DEPENDENCY_STALE"):
        retain_codesign_media(parent, P0Production(data))
    assert "bytes_base64" not in json.dumps(codesign_parent_projection(parent))
