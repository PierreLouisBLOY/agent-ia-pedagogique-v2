"""Neutral creation brief and projection, distinct from the canonical agent C08."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
    text_value,
)
from backend.shared_kernel._safe_data import freeze_safe_mapping

SECTION_IDS = ("CONSIGNES", "CONTEXTE_ET_ANNEXES", "DOSSIER_1", "DOSSIER_2", "DOSSIER_3")
OUTPUT_CONTRACT_ID = "R2-ASSESSMENT-SECTIONS-1.0"
REFERENCE_PROVENANCE_CONTRACT = "CONVERSATION-REFERENCE-PROVENANCE-1.1"
SYNTHETIC_REFERENCE_LABEL = "SUPPORT_SYNTHETIQUE_R2 — aucune source officielle attestée"
LOCAL_REFERENCE_LABEL = "REFERENCE_LOCALE_R5_V1 — aucune autorité officielle attestée"


@dataclass(frozen=True, slots=True)
class ConversationDraftRequest:
    request_id: str
    conversation_id: str
    generation_id: str
    brief: str
    context: ConfirmedConversationContext

    def __post_init__(self) -> None:
        for value, prefix in ((self.request_id, "req"), (self.conversation_id, "conv"),
                              (self.generation_id, "gen")):
            if not isinstance(value, str) or re.fullmatch(prefix + r":[0-9a-f]{32}", value) is None:
                raise ValueError("INVALID_DRAFT_IDENTITY")
        text_value(self.brief, 4000, 12 * 1024)
        if type(self.context) is not ConfirmedConversationContext:
            raise TypeError("CONFIRMED_CONTEXT_REQUIRED")


@dataclass(frozen=True, slots=True)
class ConversationDraft:
    production_ref: str
    content: str
    sections: tuple[Mapping[str, object], ...]
    references: tuple[Mapping[str, object], ...]
    lineage: Mapping[str, object]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if re.fullmatch(r"prod:[0-9a-f]{32}", self.production_ref) is None:
            raise ValueError("INVALID_DRAFT_IDENTITY")
        text_value(self.content, 65536, 65536)
        if tuple(s.get("section_id") for s in self.sections) != SECTION_IDS:
            raise ValueError("INVALID_DRAFT_SECTIONS")
        total = 0
        for section in self.sections:
            if set(section) != {"section_id", "text"}:
                raise ValueError("INVALID_DRAFT_SECTIONS")
            text = text_value(section["text"], 65536, 65536)
            if len(text) < 20 or "exercice à compléter" in text.casefold():
                raise ValueError("INSUBSTANTIAL_DRAFT")
            total += len(text.encode("utf-8"))
        if total > 65536 or not 1 <= len(self.references) <= 3:
            raise ValueError("DRAFT_SIZE_OR_REFERENCES")
        ids = set()
        used = 0
        for reference in self.references:
            if set(reference) != {"evidence_id", "source_ref", "version_ref", "checksum_sha256",
                                  "locator", "provenance_label", "declared_used"}:
                raise ValueError("INVALID_DRAFT_REFERENCE")
            for name in ("evidence_id", "source_ref", "version_ref", "locator"):
                value = reference[name]
                if not isinstance(value, str) or re.fullmatch(
                    r"[A-Za-z0-9:._-]{1,240}", value
                ) is None:
                    raise ValueError("INVALID_DRAFT_REFERENCE")
            sha = reference["checksum_sha256"]
            if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
                raise ValueError("INVALID_DRAFT_REFERENCE")
            if (type(reference["declared_used"]) is not bool
                    or reference["provenance_label"] not in (SYNTHETIC_REFERENCE_LABEL, LOCAL_REFERENCE_LABEL)
                    or reference["evidence_id"] in ids):
                raise ValueError("INVALID_DRAFT_REFERENCE")
            ids.add(reference["evidence_id"])
            used += int(reference["declared_used"] is True)
        if len({reference["provenance_label"] for reference in self.references}) != 1:
            raise ValueError("MIXED_REFERENCE_PROVENANCE")
        if not used or set(self.lineage) != {"source_run_id", "source_step_id", "evidence_set_ref"}:
            raise ValueError("INVALID_DRAFT_LINEAGE_OR_GROUNDING")
        for value in self.lineage.values():
            if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9:._-]{1,240}", value) is None:
                raise ValueError("INVALID_DRAFT_LINEAGE")
        if len(self.limitations) > 16:
            raise ValueError("DRAFT_LIMITATIONS")
        for value in self.limitations:
            text_value(value, 500)
        object.__setattr__(self, "sections", tuple(freeze_safe_mapping(s) for s in self.sections))
        object.__setattr__(self, "references", tuple(freeze_safe_mapping(r) for r in self.references))
        object.__setattr__(self, "lineage", freeze_safe_mapping(self.lineage))
