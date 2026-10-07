"""Closed historical and explicitly selected successor P0 review envelopes."""

from collections.abc import Mapping

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
