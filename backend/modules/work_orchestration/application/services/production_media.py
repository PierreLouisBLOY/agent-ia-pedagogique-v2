"""Closed local media selection; saved sources remain documentary, not reattested."""
import re
from collections.abc import Callable, Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    as_plain,
    encoded,
    fingerprint,
    identifier,
    items,
    nonempty,
    object_data,
)
from backend.modules.pedagogical_design.contracts.dto.visual_brief import VisualBrief
from backend.modules.work_orchestration.contracts.dto.saved_production import SavedProduction


class ProductionMediaService:
    def __init__(self, source: Callable[[str, str], SavedProduction],
                 prepare: Callable[..., SavedProduction],
                 publish: Callable[[SavedProduction, SavedProduction], None]) -> None:
        self.source, self.prepare, self.publish = source, prepare, publish
        self.commands: dict[str, tuple[str, dict[str, object]]] = {}

    def execute(self, body: Mapping[str, object]) -> dict[str, object]:
        data = object_data(body, {"command_id", "production_ref", "version_ref", "bundle_sha256", "selection"})
        if len(encoded(data)) > 80 * 1024:
            raise ValueError("P0_MEDIA_REQUEST_SIZE")
        command = data["command_id"]
        if not isinstance(command, str) or re.fullmatch(r"[0-9a-f]{32}", command) is None:
            raise ValueError("P0_MEDIA_COMMAND_ID")
        production = identifier(data["production_ref"], "prod")
        version = identifier(data["version_ref"], "ver")
        checksum = data["bundle_sha256"]
        if not isinstance(checksum, str) or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            raise ValueError("P0_MEDIA_BUNDLE_SHA256")
        selection = object_data(data["selection"])
        proposals: list[dict[str, object]] = []
        reason = None
        if selection.get("mode") == "NO_MEDIA":
            object_data(selection, {"mode", "reason"})
            reason = nonempty(selection["reason"], 1000)
        elif selection.get("mode") == "LOCAL_DIAGRAM":
            object_data(selection, {"mode", "entries"})
            entries = items(selection["entries"], 8)
            if not entries:
                raise ValueError("P0_MEDIA_LOCAL_ENTRIES_REQUIRED")
            for row in entries:
                object_data(row, {"brief", "required", "dependency_refs"})
                brief = VisualBrief(object_data(row["brief"]))
                if (brief.data["source_policy"] != "LOCAL_DETERMINISTIC"
                        or brief.data["style_policy"] != "COURSE_LOCAL_DIAGRAM_V1"):
                    raise ValueError("P0_MEDIA_LOCAL_DIAGRAM_REQUIRED")
                proposals.append({**row, "materialize": True, "admitted_bytes": None,
                                  "admission": None, "omission_reason": None})
        else:
            raise ValueError("P0_MEDIA_SELECTION_REJECTED")
        identity = fingerprint(data)
        prior = self.commands.get(command)
        if prior:
            if prior[0] != identity:
                raise ValueError("P0_MEDIA_IDEMPOTENCY_CONFLICT")
            return object_data(as_plain(prior[1]))
        if len(self.commands) >= 256:
            raise ValueError("P0_MEDIA_SESSION_FULL")
        self.commands[command] = (identity, {"state": "OUTCOME_UNKNOWN", "retry": 0})
        try:
            parent = self.source(production, version)
            bundle = parent.p0_bundle
            if (bundle is None or parent.production_ref != production or parent.version_ref != version
                    or bundle.sha256 != checksum):
                raise ValueError("P0_MEDIA_PARENT_CHANGED")
            child = self.prepare(parent, proposals, no_media_reason=reason)
            self.publish(parent, child)
            reports = items(child.data["validations"], 32)
            result: dict[str, object] = {"state": "CANDIDATE", "view": as_plain(child.view.data),
                "parent_version_ref": parent.version_ref, "parent_bundle_sha256": bundle.sha256,
                "record_sha256": child.sha256, "validation": as_plain(reports[-1]) if reports else None,
                "quality": {"sources": "RESERVE", "source_reason": "HISTORICAL_EVIDENCE_NOT_REVALIDATED"},
                "active_authority": "NONE_RESTORED", "provider_attempts": 0, "retry": 0,
                "promotion": "NOT_PERFORMED", "persistence": "EXPLICIT_APPLICATION_SAVE_REQUIRED"}
        except ValueError as exc:
            code = str(exc)
            if re.fullmatch(r"(?:P0|PRODUCTION_MEDIA)_[A-Z0-9_]{1,80}", code) is None:
                code = "P0_MEDIA_REQUEST_REJECTED"
            self.commands[command] = (identity, {"state": "REFUSED", "code": code})
            raise ValueError(code) from None
        except Exception:
            raise ValueError("P0_MEDIA_OUTCOME_UNKNOWN") from None
        self.commands[command] = (identity, result)
        return object_data(as_plain(result))
