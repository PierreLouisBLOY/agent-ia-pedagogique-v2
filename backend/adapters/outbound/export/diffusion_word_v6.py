"""Owner-adopted wording and course pagination; pedagogical versions are immutable."""
import re
from xml.etree.ElementTree import Element

from backend.adapters.outbound.export.classroom_word import W
from backend.adapters.outbound.export.diffusion_word import diffusion_document
from backend.modules.materialization_export.contracts.dto.lot1_word_table import Lot1WordDocument
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)

PROFILE_ID = "R6-DIFFUSION-WORD-6.0"
_CONVENTION = re.compile(r"\bconvention (?:du )?pilote\b", re.I)


def diffusion_v6_text(text: str, *, kind: str) -> str:
    text = _CONVENTION.sub(
        lambda match: ("Convention" if match[0][0].isupper() else "convention") + " de l’exercice", text,
    )
    if kind == "correction":
        text = text.replace("passage SQLite sélectionné", "passage sélectionné")
    return text


def diffusion_v6_document(document: WordDocument) -> WordDocument:
    projected = diffusion_document(document)
    blocks = tuple(WordBlock(block.style, diffusion_v6_text(block.text, kind=document.kind))
                   for block in projected.blocks)
    title = diffusion_v6_text(projected.title, kind=document.kind)
    if isinstance(projected, Lot1WordDocument):
        return Lot1WordDocument(projected.kind, title, blocks, projected.tables)
    return WordDocument(projected.kind, title, blocks)


def compact_course_pagination(document: WordDocument, styles: Element) -> None:
    # P0 courses have section headings and no question blocks; use the pre-layout DTO.
    if document.kind != "student" or document.title != "Document élève" or any(
        block.style == "Heading2" and re.fullmatch(r"Q0*\d+", block.text) for block in document.blocks
    ) or not any(block.style == "Heading1" for block in document.blocks):
        return
    for spacing in styles.findall("./" + W + "style/" + W + "pPr/" + W + "spacing"):
        spacing.set(W + "after", "80")  # 4 points, unchanged 11.5pt font and line spacing.
