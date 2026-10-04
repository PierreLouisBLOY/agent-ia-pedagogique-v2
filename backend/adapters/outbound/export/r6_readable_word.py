"""Render bounded literal Markdown tables with the adopted LOT1 table contract.

Source records and other documents stay unchanged. This is representation only,
with no numerical interpretation or repair of source values.
"""
from __future__ import annotations

import re
from io import BytesIO
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter
from backend.modules.materialization_export.contracts.dto.lot1_word_table import (
    Lot1WordDocument,
    Lot1WordTable,
)
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)


def _cells(line: str) -> tuple[str, ...] | None:
    value = line.strip()
    if not value.startswith("|") or not value.endswith("|"):
        return None
    return tuple(cell.strip() for cell in value[1:-1].split("|"))


def readable_student(document: WordDocument) -> WordDocument:
    if document.kind != "student" or isinstance(document, Lot1WordDocument):
        return document
    blocks: list[WordBlock] = []
    tables: list[Lot1WordTable] = []
    for block in document.blocks:
        lines = block.text.split("\n")
        plain: list[str] = []
        i = 0
        while i < len(lines):
            header = _cells(lines[i])
            divider = _cells(lines[i+1]) if i+1 < len(lines) else None
            if (header is None or divider is None or len(header) != len(divider)
                    or not all(re.fullmatch(r":?-{3,}:?", c) for c in divider)):
                plain.append(lines[i])
                i += 1
                continue
            blocks.append(WordBlock(block.style, "\n".join(plain)))
            plain = []
            rows = [header]
            i += 2
            while i < len(lines) and (row := _cells(lines[i])) is not None:
                rows.append(row)
                i += 1
            # The canonical DTO rejects ragged, oversized or unbounded tables.
            tables.append(Lot1WordTable(len(blocks)-1, tuple(rows)))
        if plain:
            blocks.append(WordBlock(block.style, "\n".join(plain)))
    if not tables:
        return document
    return Lot1WordDocument(document.kind, document.title, tuple(blocks), tuple(tables))


class R6ReadableWordWriter(Lot1OOXMLWordWriter):
    def write(self, document: WordDocument) -> bytes:
        projected = readable_student(document)
        raw = super().write(projected)
        if projected is document:
            return raw
        with ZipFile(BytesIO(raw)) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        root = fromstring(parts["word/document.xml"])
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for row in root.findall(".//" + namespace + "tbl/" + namespace + "tr"):
            props = row.find(namespace + "trPr")
            if props is None:
                props = Element(namespace + "trPr")
                row.insert(0, props)
            SubElement(props, namespace + "cantSplit")
        parts["word/document.xml"] = tostring(root, encoding="utf-8", xml_declaration=True)
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for name, data in parts.items():
                info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, data)
        return output.getvalue()
