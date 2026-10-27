"""Draft representation of observed text only; no SavedProduction or promotion."""
from __future__ import annotations

import json
from dataclasses import dataclass

from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)
from backend.modules.materialization_export.ports.outbound.word_writer import WordWriter
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import CapturedPartial


@dataclass(frozen=True, slots=True)
class CapturedSpan:
    start: int
    end: int
    style: str = "Normal"
    json_string: bool = False


class ExportCapturedPartialDraft:
    def __init__(self, writer: WordWriter) -> None:
        self.writer = writer

    def preview(self, capture: CapturedPartial, *,
                spans: tuple[CapturedSpan, ...] | None = None) -> WordDocument:
        if type(capture) is not CapturedPartial:
            raise ValueError("P0_CAPTURED_PARTIAL_TYPED_ARGUMENTS")
        blocks = [WordBlock("Note", "BROUILLON PARTIEL NON VALIDÉ"),
            WordBlock("Normal", "Réponse partielle du cours de Première STMG sur les différents "
                "types d’organisation. Le texte absent n’a pas été complété. "
                "Ce document doit être relu avant toute utilisation pédagogique."),
            WordBlock("Note", "Capture " + capture.request.command_id
                + " · Texte SHA256 " + capture.request.text_sha256)]
        if spans is None:
            spans = (CapturedSpan(0, len(capture.text)),)
        if type(spans) is not tuple:
            raise ValueError("P0_CAPTURED_PARTIAL_SPAN_CHANGED")
        cursor = 0
        for span in spans:
            if (type(span) is not CapturedSpan or type(span.start) is not int
                    or type(span.end) is not int or not cursor <= span.start < span.end <= len(capture.text)
                    or span.style not in {"Normal", "Heading1", "Heading2", "Note"}
                    or type(span.json_string) is not bool):
                raise ValueError("P0_CAPTURED_PARTIAL_SPAN_CHANGED")
            text = capture.text[span.start:span.end]
            if span.json_string:
                value = json.loads(text)
                if type(value) is not str:
                    raise ValueError("P0_CAPTURED_PARTIAL_SPAN_CHANGED")
                text = value
            blocks.append(WordBlock(span.style, text))
            cursor = span.end
        if not spans:
            raise ValueError("P0_CAPTURED_PARTIAL_EMPTY_DRAFT")
        return WordDocument("correction", "Capture partielle du cours de management", tuple(blocks))

    def execute(self, capture: CapturedPartial, *,
                spans: tuple[CapturedSpan, ...] | None = None) -> bytes:
        return self.writer.write(self.preview(capture, spans=spans))
