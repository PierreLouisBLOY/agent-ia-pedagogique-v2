"""Diffusion V5: presentation only; source versions and authority are unchanged."""
from __future__ import annotations

import re

from backend.modules.materialization_export.contracts.dto.lot1_word_table import Lot1WordDocument
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)

PROFILE_ID = "R6-DIFFUSION-WORD-5.0"
# Only the declared provenance markers, including combined lists/ranges, are metadata.
_MARKER = re.compile(r"\[(?=[^\]\n]*(?:[SCF](?:\d{2}|xx)))[SCF\d x;,–—−\-]*(?:\s*;\s*(?:règle|principe(?: du cycle)?|données FICTIVES|hypothèses FICTIVES|principes?)\s+[SCF]\d{2})?\]", re.I)
_TECHNICAL_NOTE = re.compile(r"^(?:Version exacte : ver:|CANDIDATE\s*[—−-]|A16\s*:|PROMOTION EXPLICITE ENREGISTRÉE)")
_PROVENANCE_PREFIXES = (
    "Les principes signalés", "Les repères de méthode", "Référence de correction exacte Atelier",
    "À confirmer avant utilisation :", "Aucune validation ou signature n'est présumée.",
)
_ANNOTATION = re.compile(r"^\s*\[[SCF](?:\d{2}|xx).*?\]\s+.*(?:sourc|conventionnel|étayé|Relation TN|Diagnostic sur le cas|Propositions pédagogiques)", re.I)


def diffusion_text(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(_PROVENANCE_PREFIXES) or _ANNOTATION.match(stripped):
            continue
        if re.fullmatch(r"#{1,3}\s+Validation enseignante", stripped):
            continue
        line = _MARKER.sub("", line)
        # The longer mixed marker forms use an explicitly closed vocabulary.
        line = re.sub(r"\[(?=[^\]\n]*\b[SCF]\d{2})[SCF\d\s;,–—−\-]*(?:(?:règle|principe(?: du cycle)?|données FICTIVES|hypothèses FICTIVES|principes?)\s+[SCF\d\s;,–—−\-]*)+\]", "", line)
        line = re.sub(r"\bFICTIF\s*/\s*À VALIDER\b", "Cas fictif", line)
        line = re.sub(r"\s*[—−-]\s*Version\s+\d+\b", "", line)
        line = line.replace(" ; elles restent soumises à validation enseignante.", ".")
        line = re.sub(r"\bConventions\s+\*\*\s*\*\*\.", "Conventions.", line)
        line = re.sub(r"\*\*\s*\*\*", "", line)
        line = re.sub(r"[ \t]{2,}", " ", line)
        line = re.sub(r"\s+([.,])", r"\1", line)
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def diffusion_document(document: WordDocument) -> WordDocument:
    blocks: list[WordBlock] = []
    for index, block in enumerate(document.blocks):
        following = document.blocks[index + 1].text if index + 1 < len(document.blocks) else ""
        if not isinstance(document, Lot1WordDocument):
            if block.style == "Note" and _TECHNICAL_NOTE.match(block.text):
                continue
            if block.style == "Heading2" and block.text == "Justification" and following.startswith(_PROVENANCE_PREFIXES):
                continue
        text = diffusion_text(block.text)
        if text or isinstance(document, Lot1WordDocument):
            blocks.append(WordBlock(block.style, text))
    title = diffusion_text(document.title)
    if isinstance(document, Lot1WordDocument):
        return Lot1WordDocument(document.kind, title, tuple(blocks), document.tables)
    return WordDocument(document.kind, title, tuple(blocks))
