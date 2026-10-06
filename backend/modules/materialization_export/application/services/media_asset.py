"""Technical local worker, with no generation, admission or persistence authority."""
import base64
import hashlib
from collections.abc import Mapping

from backend.modules.materialization_export.contracts.dto.media_asset import (
    MediaAsset,
    validate_png,
)
from backend.modules.materialization_export.ports.outbound.media_renderer import MediaRenderer
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief


class MediaAssetWorker:
    def __init__(self, renderer: MediaRenderer) -> None:
        self.renderer = renderer

    def execute(self, brief: VisualBrief, *, admitted_bytes: bytes | None = None,
                admission: Mapping[str, object] | None = None) -> MediaAsset:
        if brief.data["source_policy"] == "LOCAL_DETERMINISTIC":
            if admitted_bytes is not None or admission is not None:
                raise ValueError("MEDIA_LOCAL_INPUT_SUBSTITUTION")
            raw = self.renderer.render(brief)
            provenance: dict[str, object] = {"source_kind": "LOCAL_DETERMINISTIC",
                "source_ref": "visual-brief:" + brief.sha256, "source_sha256": brief.sha256,
                "licence": "LOCAL_ORIGINAL", "rights_basis": "Original local drawing from the explicit pedagogical brief",
                "admission_ref": "local-authoring:" + brief.sha256}
            renderer = self.renderer.renderer_id
        else:
            if admitted_bytes is None or admission is None:
                raise ValueError("MEDIA_ADMITTED_BYTES_REQUIRED_NO_FETCH")
            raw = admitted_bytes
            provenance = object_data(admission, {"source_kind", "source_ref", "source_sha256", "licence", "rights_basis", "admission_ref"})
            if provenance["source_kind"] != brief.data["source_policy"]:
                raise ValueError("MEDIA_SOURCE_POLICY_BINDING")
            renderer = "ADMITTED_PNG_BYTES_1"
        width, height = validate_png(raw)
        asset = MediaAsset({"contract_id": "MEDIA-ASSET-1.0", "visual_id": brief.data["visual_id"],
            "brief_sha256": brief.sha256, "png_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes_base64": base64.b64encode(raw).decode("ascii"), "width": width, "height": height,
            "mime_type": "image/png", "renderer_id": renderer, "provenance": provenance})
        asset.bind(brief)
        return asset
