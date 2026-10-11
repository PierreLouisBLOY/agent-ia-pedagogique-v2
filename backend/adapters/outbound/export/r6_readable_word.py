"""Render bounded literal Markdown tables with the adopted LOT1 table contract.

Source records and other documents stay unchanged. This is representation only,
with no numerical interpretation or repair of source values.
"""
from __future__ import annotations

import re
from io import BytesIO
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.adapters.outbound.export.classroom_word import (
    apply_page_profile,
    presentation_document,
)
from backend.adapters.outbound.export.diffusion_word import diffusion_document
from backend.adapters.outbound.export.diffusion_word_v6 import (
    compact_course_pagination,
    diffusion_v6_document,
)
from backend.adapters.outbound.export.lot1_word import Lot1OOXMLWordWriter, _table
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


def readable_document(document: WordDocument) -> tuple[WordDocument, tuple[Lot1WordTable, ...]]:
    if isinstance(document, Lot1WordDocument):
        return document, ()
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
        return document, ()
    return WordDocument(document.kind, document.title, tuple(blocks)), tuple(tables)


class R6ReadableWordWriter(Lot1OOXMLWordWriter):
    def __init__(self, *, profile: str = "classroom-v2") -> None:
        if profile not in {"classroom-v2", "readable-v1", "diffusion-v5", "diffusion-v6", "product-v7"}:
            raise ValueError("R6_WORD_PROFILE_REJECTED")
        self.classroom = profile != "readable-v1"
        self.diffusion = profile == "diffusion-v5"
        self.diffusion_v6 = profile == "diffusion-v6"
        self.product_v7 = profile == "product-v7"

    def write(self, document: WordDocument) -> bytes:
        if self.product_v7:
            from backend.adapters.outbound.export.product_word import ProductWordWriter

            return ProductWordWriter().write(document)
        if document.course_chapter is not None:
            from backend.adapters.outbound.export.course_word import CourseOOXMLWordWriter

            return CourseOOXMLWordWriter().write(document)
        if self.diffusion_v6:
            document = diffusion_v6_document(document)
        if self.diffusion:
            document = diffusion_document(document)
        pagination_document = document
        if self.classroom:
            document = presentation_document(document)
        projected, tables = readable_document(document)
        raw = super().write(projected)
        if projected is document and not self.classroom:
            return raw
        with ZipFile(BytesIO(raw)) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        root = fromstring(parts["word/document.xml"])
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        body = root.find(namespace + "body")
        if body is None:
            raise ValueError("R6_WORD_BODY_REJECTED")
        for value in sorted(tables, key=lambda t: t.after_block_index, reverse=True):
            body.insert(value.after_block_index + 2, _table(value))
        for row in root.findall(".//" + namespace + "tbl/" + namespace + "tr"):
            props = row.find(namespace + "trPr")
            if props is None:
                props = Element(namespace + "trPr")
                row.insert(0, props)
            SubElement(props, namespace + "cantSplit")
        if self.classroom:
            styles = fromstring(parts["word/styles.xml"])
            footer = apply_page_profile(root, styles)
            if self.diffusion_v6:
                compact_course_pagination(pagination_document, styles)
            parts["word/styles.xml"] = tostring(styles, encoding="utf-8", xml_declaration=True)
            parts["word/footer1.xml"] = tostring(footer, encoding="utf-8", xml_declaration=True)
            relationships = fromstring(parts["word/_rels/document.xml.rels"])
            SubElement(relationships, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship", {
                "Id": "rIdClassroomFooter", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer",
                "Target": "footer1.xml",
            })
            parts["word/_rels/document.xml.rels"] = tostring(relationships, encoding="utf-8", xml_declaration=True)
            types = fromstring(parts["[Content_Types].xml"])
            SubElement(types, "{http://schemas.openxmlformats.org/package/2006/content-types}Override", {
                "PartName": "/word/footer1.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
            })
            parts["[Content_Types].xml"] = tostring(types, encoding="utf-8", xml_declaration=True)
        parts["word/document.xml"] = tostring(root, encoding="utf-8", xml_declaration=True)
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for name, data in parts.items():
                info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, data)
        return output.getvalue()
