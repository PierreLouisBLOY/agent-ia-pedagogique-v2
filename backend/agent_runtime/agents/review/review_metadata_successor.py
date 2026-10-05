"""Opt-in review diagnostic policy; no payload mutation or shared scanner change."""
import re
from collections.abc import Mapping
from enum import StrEnum

from backend.agent_runtime.agents.review.review_security import (
    reject_activatable_review_metadata,
    reject_review_authority,
)
from backend.agent_runtime.agents.review.review_security_model import (
    ReviewMetadataPolicyVersion,
    ReviewSecurityError,
    ReviewSecuritySignalCode,
)
from backend.agent_runtime.contracts.security import ContentThreatSignalCode
from backend.agent_runtime.security.content_isolation import scan_content_threats


class ReviewDiagnosticSurface(StrEnum):
    LIMITATIONS = "limitations"
    UNCERTAINTIES = "uncertainties"


_NEGATIVE_CODES = frozenset({"NO_AUTHORITATIVE_ORACLE", "NO_AUTHORITATIVE_BASIS_PROVIDED"})
# Only an anchored, closed absence clause. The remainder is checked independently.
_ABSENCE = re.compile(
    r"^(?:aucune source officielle(?: ou référentiel pédagogique attesté)? "
    r"n['’]est fourni(?:e)?|no authoritative (?:oracle|basis) is provided)[ \t]*(?:[.;]|$)",
    re.I,
)


def reject_review_diagnostics(
    value: object, *, version: ReviewMetadataPolicyVersion, surface: ReviewDiagnosticSurface,
) -> None:
    if type(version) is not ReviewMetadataPolicyVersion or type(surface) is not ReviewDiagnosticSurface:
        raise ReviewSecurityError(ReviewSecuritySignalCode.AUTHORITY_METADATA_FORBIDDEN)
    if version is ReviewMetadataPolicyVersion.HISTORICAL:
        reject_activatable_review_metadata(value)
        return
    reject_review_authority(value)
    if type(value) is not tuple:
        raise ReviewSecurityError(ReviewSecuritySignalCode.AUTHORITY_METADATA_FORBIDDEN)
    for item in value:
        if (not isinstance(item, Mapping) or type(item.get("code")) is not str
                or item.get("code") not in _NEGATIVE_CODES):
            reject_activatable_review_metadata(item)
            continue
        for key, field in item.items():
            reject_activatable_review_metadata(key)
            if key == "code":
                continue
            if key == "message" and type(field) is str:
                _reject_diagnostic_message(field)
            else:
                reject_activatable_review_metadata(field)


def _reject_diagnostic_message(text: str) -> None:
    signals = scan_content_threats(text, content_ref="review-metadata", logical_location="message")
    if any(signal.code is not ContentThreatSignalCode.AUTHORITY_CLAIM_TEXT for signal in signals):
        raise ReviewSecurityError(ReviewSecuritySignalCode.AUTHORITY_METADATA_FORBIDDEN)
    matched = _ABSENCE.match(text)
    reject_activatable_review_metadata(text[matched.end():] if matched else text)
