"""Closed historical and explicitly selected successor P0 review envelopes."""

from collections.abc import Mapping

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import encoded, items

HISTORICAL_CONTRACT = "P0-REVIEW-1.0"
DIAGNOSTIC_CONTRACT = "P0-REVIEW-1.1"
FIELDS = frozenset(
    {
        "contract_id",
        "status",
        "production_ref",
        "version_ref",
        "bundle_sha256",
        "overall_assessment",
        "correction_required",
        "coverage",
        "instruction_coverage",
        "findings",
        "limitations",
        "evidence_refs_used",
        "created_at",
        "promotion",
    }
)


def validate_p0_review_fields(report: Mapping[str, object]) -> None:
    contract = report.get("contract_id")
    if not isinstance(contract, str) or contract not in {HISTORICAL_CONTRACT, DIAGNOSTIC_CONTRACT}:
        raise ValueError("P0_REVIEW_CONTRACT")
    fields = FIELDS | {"uncertainties"} if contract == DIAGNOSTIC_CONTRACT else FIELDS
    if set(report) != fields:
        raise ValueError("P0_REVIEW_FIELDS")
    if contract == DIAGNOSTIC_CONTRACT:
        diagnostics = report["uncertainties"]
        if not isinstance(diagnostics, (tuple, list)) or len(diagnostics) > 16:
            raise ValueError("P0_REVIEW_UNCERTAINTIES")
        for diagnostic in diagnostics:
            if (
                not isinstance(diagnostic, Mapping)
                or set(diagnostic) not in ({"code"}, {"code", "message"})
                or not isinstance(diagnostic.get("code"), str)
                or not 1 <= len(diagnostic["code"]) <= 80
                or (
                    "message" in diagnostic
                    and (
                        not isinstance(diagnostic["message"], str)
                        or not 1 <= len(diagnostic["message"]) <= 1000
                    )
                )
            ):
                raise ValueError("P0_REVIEW_UNCERTAINTIES")


def validate_p0_review_binding(report: Mapping[str, object], *, production_ref: str,
                               version_ref: str, bundle_sha256: str, evidence_ids: set[str]) -> None:
    validate_p0_review_fields(report)
    used, coverage = report["evidence_refs_used"], report["coverage"]
    dimensions = {"REV-ACC", "REV-COV", "REV-PED", "REV-INS", "REV-STR", "REV-SRC", "REV-CON", "REV-FMT", "REV-RSK"}
    if (not isinstance(used, (list, tuple)) or any(not isinstance(ref, str) for ref in used)
            or len(set(used)) != len(used) or not set(used) <= evidence_ids
            or not isinstance(coverage, (list, tuple)) or any(not isinstance(value, str) for value in coverage)
            or len(set(coverage)) != len(coverage) or not set(coverage) <= dimensions
            or report["instruction_coverage"] not in {"FULL", "PARTIAL"}
            or (report["instruction_coverage"] == "FULL" and "REV-INS" not in coverage)
            or report["status"] not in {"completed", "incomplete"}
            or report["overall_assessment"] not in {"acceptable", "acceptable_with_reservations", "correction_required", "unusable", "incomplete"}
            or type(report["correction_required"]) is not bool
            or any(report.get(key) != value for key, value in (("production_ref", production_ref),
                ("version_ref", version_ref), ("bundle_sha256", bundle_sha256), ("promotion", "NOT_PERFORMED")))
            or len(encoded(report)) > 32768):
        raise ValueError("P0_REVIEW_BINDING")
    findings = items(report["findings"], 32)
    identities = [str(row.get("finding_id")) for row in findings]
    if len(set(identities)) != len(identities):
        raise ValueError("P0_REVIEW_BINDING")
    for finding in findings:
        refs = finding.get("evidence_refs")
        if (not isinstance(finding.get("finding_id"), str) or not finding["finding_id"]
                or finding.get("dimension") not in dimensions or type(finding.get("correction_required")) is not bool
                or not isinstance(refs, (list, tuple)) or any(not isinstance(ref, str) for ref in refs)
                or not set(refs) <= evidence_ids):
            raise ValueError("P0_REVIEW_BINDING")
