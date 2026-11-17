"""Closed companion routes; the historical R2/R3/R4 registry stays versioned."""
import json
import re
from collections.abc import Callable, Mapping

from backend.adapters.inbound.api.p0_notion_evidence import P0NotionEvidenceEndpoint
from backend.adapters.inbound.api.p0_pilot_command_followup import P0PilotCommandFollowup
from backend.adapters.inbound.api.production_media import ProductionMediaEndpoint
from backend.adapters.inbound.api.routes import P0_NOTION_EVIDENCE_TEMPLATE, resolve_p0_route

P0_HTTP_CONTRACT = "R6-P0-HTTP-LOCAL-1.0"


class P0CreationEndpoint:
    def __init__(self, execute: Callable[..., dict[str, object]], read: Callable[..., dict[str, object]], metadata: list[dict[str, object]],
                 *, nonce: str, generation_bound: bool = False, review_bound: bool = False,
                 institutional_catalog: Callable[[], dict[str, object]] | None = None,
                 media_endpoint: ProductionMediaEndpoint | None = None,
                 consent_execute: Callable[[str, Mapping[str, object]], dict[str, object]] | None = None,
                 exact_notion_reader: Callable[[str], Mapping[str, object]] | None = None,
                 local_reference_contexts: Callable[[], list[dict[str, object]]] | None = None,
                 campaign_snapshot: Callable[[], dict[str, object]] | None = None,
                 intention_execute: Callable[[Mapping[str, object]], dict[str, object]] | None = None,
                 pilot_preview_execute: Callable[[Mapping[str, object]], dict[str, object]] | None = None,
                 pilot_candidate_read: Callable[[], dict[str, object]] | None = None,
                 pilot_revoke_execute: Callable[[Mapping[str, object]], dict[str, object]] | None = None,
                 codesign_command_read: Callable[[str], Mapping[str, object] | None] | None = None) -> None:
        self.execute, self.read, self.metadata, self.nonce = execute, read, metadata, nonce
        self.generation_bound, self.review_bound = generation_bound, review_bound
        self.institutional_catalog = institutional_catalog
        self.media_endpoint = media_endpoint
        self.consent_execute = consent_execute
        self.exact_notion_reader = exact_notion_reader
        self.local_reference_contexts = local_reference_contexts
        self.intention_execute = intention_execute
        self.campaign_snapshot = campaign_snapshot
        self.pilot_preview_execute = pilot_preview_execute
        self.pilot_candidate_read = pilot_candidate_read
        self.pilot_revoke_execute = pilot_revoke_execute
        self.pilot_effect_binding = "NONE"
        self.pilot_recovery_incident: str | None = None
        self.pilot_command_followup: P0PilotCommandFollowup | None = None
        self.normal_command_followup: P0PilotCommandFollowup | None = None
        self.normal_mode = "NONE"
        self.codesign_command_read = codesign_command_read
        self.codesign_command_followup: P0PilotCommandFollowup | None = None
        self.codesign_binding = "DISARMED_NO_MULTI_OPERATION_AUTHORITY"
        self.codesign_profile: Mapping[str, object] | None = None
        self.organization_capture_reader: Callable[[str], dict[str, object]] | None = None
        self.organization_search: Callable[[dict[str, object]], dict[str, object]] | None = None
        self.manual_test_start: Callable[[Mapping[str, object]], dict[str, object]] | None = None
        self.manual_test_read: Callable[[str], dict[str, object]] | None = None
        self.manual_test_stop: Callable[[Mapping[str, object]], dict[str, object]] | None = None
        self.manual_test_metadata: Callable[[], dict[str, object]] | None = None
        self.course_organization_catalogue: Callable[[], list[dict[str, object]]] | None = None
        self.documentary_catalogue: Callable[[], dict[str, object]] | None = None
        self.documentary_read: Callable[[str], dict[str, object]] | None = None

    def respond(self, method: str, target: str, raw: bytes, correlation: str) -> tuple[int, str, bytes, str]:
        status, template = 200, "/{unmatched}"
        result: dict[str, object]
        try:
            if target.partition("?")[0] == P0_NOTION_EVIDENCE_TEMPLATE:
                if self.exact_notion_reader is None:
                    raise ValueError("P0_REFERENCE_NOT_ENABLED")
                return P0NotionEvidenceEndpoint(self.exact_notion_reader).respond(method, target, raw, correlation)
            operation, production, version, teacher, template = resolve_p0_route(method, target)
            if operation == "documentary-read":
                if raw or self.documentary_read is None:
                    raise ValueError("DOCUMENTARY_LIBRARY_NOT_CONFIGURED")
                result = self.documentary_read(production)
            elif operation == "organization-capture":
                if raw:
                    raise ValueError("P0_REQUEST_REJECTED")
                if self.organization_capture_reader is None:
                    raise ValueError("P0_ORGANIZATION_CAPTURES_NOT_CONFIGURED")
                result = self.organization_capture_reader(production)
            elif operation == "command-followup":
                observed: Mapping[str, object] | None = None
                if self.manual_test_read is not None:
                    value = self.manual_test_read(production)
                    if value.get('state') != 'LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE':
                        observed = value
                if self.normal_command_followup is not None and self.normal_command_followup.handles(production):
                    observed = self.normal_command_followup.read(production)
                if observed is None and self.codesign_command_followup is not None:
                    value = self.codesign_command_followup.read(production)
                    if value.get("state") != "LOCAL_COMMAND_FOLLOWUP_UNAVAILABLE":
                        observed = value
                if observed is None and self.codesign_command_read is not None:
                    observed = self.codesign_command_read(production)
                if observed is not None:
                    result = dict(observed)
                else:
                    followup = self.normal_command_followup or self.pilot_command_followup
                    if followup is None:
                        raise ValueError("P1_PILOT_FOLLOWUP_NOT_BOUND")
                    result = followup.read(production)
            elif operation == "metadata":
                result = {"transport_nonce": self.nonce, "state": "READY", "references": self.metadata,
                          "live_binding": "EXPLICIT_PORT" if self.generation_bound else "NONE",
                          "review_binding": "EXPLICIT_PORT" if self.review_bound else "NONE", "authority": "NONE"}
                result["media_binding"] = "LOCAL_DIAGRAM_OR_NO_MEDIA" if self.media_endpoint is not None else "NONE"
                if self.organization_capture_reader is not None:
                    result["organization_capture_binding"] = "PINNED_LOCAL_PROPOSALS_READ_ONLY"
                result["course_organizations"] = ([] if self.course_organization_catalogue is None
                    else self.course_organization_catalogue())
                result["documentary_library"] = None if self.documentary_catalogue is None else self.documentary_catalogue()
                result["codesign_binding"] = self.codesign_binding
                if self.manual_test_metadata is not None:
                    result['manual_test_session'] = self.manual_test_metadata()
                if self.codesign_profile is not None:
                    result["codesign_profile"] = dict(self.codesign_profile)
                result["normal_consent_binding"] = "EXPLICIT_PRODUCT_PERMISSION" if self.consent_execute is not None else "NONE"
                if self.normal_mode != "NONE":
                    result["normal_mode"] = self.normal_mode
                    result["credential_source"] = "OPENAI_API_KEY"
                    if self.normal_mode == "PREPARE_ONLY":
                        result["normal_consent_binding"] = "NONE"
                if self.normal_command_followup is not None:
                    result["normal_command_followup"] = "EXPLICIT_SINGLE_COMMAND_FOLLOWUP"
                result["pilot_preview_binding"] = "OFF_PREVIEW_ONLY" if self.pilot_preview_execute is not None else "NONE"
                result["pilot_candidate_binding"] = ("PILOT_EFFECT_CANDIDATE" if self.pilot_effect_binding != "NONE"
                    else "OFF_RECOVERABLE" if self.pilot_candidate_read is not None else "NONE")
                result["pilot_effect_binding"] = self.pilot_effect_binding
                if self.pilot_recovery_incident is not None:
                    result["pilot_recovery_incident"] = self.pilot_recovery_incident
                if self.pilot_command_followup is not None:
                    result["pilot_command_followup"] = "EXPLICIT_SINGLE_COMMAND_FOLLOWUP"
                if self.institutional_catalog is not None:
                    result["institutional_catalog"] = self.institutional_catalog()
                result["local_reference_contexts"] = [] if self.local_reference_contexts is None else self.local_reference_contexts()
                result["local_reference_context_binding"] = "NONE" if self.local_reference_contexts is None else "EXPLICIT_OWNER_LOCAL_CONTEXT"
                if self.campaign_snapshot is not None:
                    result["campaign_snapshot"] = self.campaign_snapshot()
            elif operation == "pilot-candidate":
                if self.pilot_candidate_read is None:
                    raise ValueError("P0_PILOT_CANDIDATE_NOT_BOUND")
                result = self.pilot_candidate_read()
            elif operation == "media":
                if self.media_endpoint is None:
                    raise ValueError("P0_MEDIA_NOT_ENABLED")
                return self.media_endpoint.respond(method, target, raw, correlation)
            elif method == "POST":
                def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
                    if len(dict(entries)) != len(entries):
                        raise ValueError("P0_REQUEST_REJECTED")
                    return dict(entries)
                data = json.loads(raw, object_pairs_hook=pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError("P0_REQUEST_REJECTED")))
                if not isinstance(data, dict):
                    raise ValueError("P0_REQUEST_REJECTED")
                if operation == 'manual-stop':
                    if self.manual_test_stop is None:
                        raise ValueError('P0_MANUAL_TEST_NOT_ENABLED')
                    result = self.manual_test_stop(data)
                elif operation == 'generate' and self.manual_test_start is not None:
                    result = self.manual_test_start(data)
                    status = 202
                elif operation == "organization-search":
                    if self.organization_search is None:
                        raise ValueError("P0_ORGANIZATION_SEARCH_INDEX_NOT_CONFIGURED")
                    result = self.organization_search(data)
                elif operation in {"consent-preview", "consent-generate"}:
                    if self.consent_execute is None:
                        raise ValueError("P0_PRODUCT_PERMISSION_REQUIRED")
                    followup = self.normal_command_followup or self.pilot_command_followup
                    if operation == "consent-generate" and followup is not None:
                        result = followup.start(data)
                        status = 202
                    else:
                        result = self.consent_execute(operation.replace("-", "_"), data)
                elif operation == "pilot-revoke":
                    if self.pilot_revoke_execute is None:
                        raise ValueError("P1_PILOT_REVOCATION_NOT_BOUND")
                    result = self.pilot_revoke_execute(data)
                elif operation == "pilot-preview":
                    if self.pilot_preview_execute is None:
                        raise ValueError("P1_PILOT_OFF_PREVIEW_NOT_BOUND")
                    result = self.pilot_preview_execute(data)
                else:
                    if operation in {"codesign", "codesign-consent"} and self.codesign_command_followup is not None:
                        if operation == "codesign" and self.codesign_binding.startswith("FINITE_CHAIN"):
                            raise ValueError("P0_CHAIN_EXACT_CONSENT_REQUIRED")
                        result = self.codesign_command_followup.start(data)
                        status = 202
                    elif operation == "intention":
                        if self.intention_execute is None:
                            raise ValueError("P0_INTENTION_NOT_ENABLED")
                        result = self.intention_execute(data)
                    else:
                        result = self.execute(operation, data)
            elif operation == "version":
                result = self.read(production, version, teacher=teacher)
            else:
                raise ValueError("P0_ROUTE_REJECTED")
            envelope = {"data": result}
        except (ValueError, TypeError) as error:
            status = 409
            code = str(error)
            # Only bounded symbolic codes can leave the Application boundary.
            if re.fullmatch(r"(?:P0|P1|R6|COURSE|PRODUCTION_MEDIA|FORMULA)_[A-Z0-9_]{1,80}", code) is None:
                code = "P0_REQUEST_REJECTED"
            envelope = {"error": {"code": code}}
        except Exception:
            status, envelope = 500, {"error": {"code": "P0_APPLICATION_FAILURE"}}
        envelope["meta"] = {"contract_id": P0_HTTP_CONTRACT, "correlation_id": correlation}
        return status, "application/json; charset=utf-8", json.dumps(envelope, ensure_ascii=False,
            allow_nan=False).encode("utf-8"), template
