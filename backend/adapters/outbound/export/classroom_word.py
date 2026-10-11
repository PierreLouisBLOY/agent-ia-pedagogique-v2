"""Shared classroom presentation on the existing OOXML renderer, without content repair."""
from __future__ import annotations

import re
from xml.etree.ElementTree import Element, SubElement

from backend.modules.materialization_export.contracts.dto.lot1_word_table import Lot1WordDocument
from backend.modules.materialization_export.contracts.dto.word_document import (
    WordBlock,
    WordDocument,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PROFILE_ID = "R6-CLASSROOM-WORD-2.0"

# Underscores, operators, amounts and unmatched delimiters are literal data.
_INLINE = re.compile(r"\*\*(?P<bold>[^*\n]+)\*\*|(?<![\w*])\*(?P<italic>[^\s*\n](?:[^*\n]*[^\s*\n])?)\*(?![\w*])|`(?P<code>[^`\n]+)`")
_VERSION = re.compile(r"Version exacte : ver:[0-9a-f]{32}")


def presentation_document(document: WordDocument) -> WordDocument:
    if isinstance(document, Lot1WordDocument):
        return document  # Native table anchors and their original block indexes remain intact.
    blocks: list[WordBlock] = []
    for block_index, block in enumerate(document.blocks):
        if block.style == "Note" and _VERSION.fullmatch(block.text):
            continue  # Exact identity remains in Application/receipt, not the classroom page.
        following = document.blocks[block_index + 1].text if block_index + 1 < len(document.blocks) else ""
        if block.style in {"Heading1", "Heading2"}:
            nested_headings = re.findall(r"^#{1,3}\s+(.+)$", following, re.M)
            if any(h.casefold() == block.text.casefold() or h.casefold().startswith(block.text.casefold() + " —")
                   for h in nested_headings):
                continue  # The same heading is already supplied by the structured text.
            question = re.fullmatch(r"Q0*(\d+)", block.text)
            if question and re.match(r"^\*{0,2}" + question[1] + r"\.\s", following):
                continue  # The visible prompt already carries the same question number.
            renamed = re.sub(r"^Q0*(\d+)(?=\s|$)", r"Question \1", block.text)
            if renamed != block.text:
                block = WordBlock(block.style, renamed)
        lines = block.text.split("\n")
        index = 0
        while index < len(lines):
            line = lines[index]
            index += 1
            if not line.strip():
                continue  # Paragraph spacing supplies whitespace without blank Word paragraphs.
            if line.strip().startswith("|"):
                table_lines = [line]
                while index < len(lines) and lines[index].strip().startswith("|"):
                    table_lines.append(lines[index])
                    index += 1
                blocks.append(WordBlock(block.style, "\n".join(table_lines)))
                continue
            if re.fullmatch(r"\s*(?:---+|```[a-zA-Z]*)\s*", line):
                continue
            heading = re.fullmatch(r"\s*(#{1,3})\s+(.+)", line)
            if heading:
                blocks.append(WordBlock("Heading1" if len(heading[1]) < 3 else "Heading2", heading[2]))
            else:
                # A typographic list marker preserves every word and numeric value.
                blocks.append(WordBlock(block.style, re.sub(r"^\s*[-*]\s+", "• ", line)))
    return WordDocument(document.kind, document.title, tuple(blocks))


def format_paragraph(paragraph: Element) -> None:
    text = "".join("\n" if t.tag == W + "br" else t.text or ""
                   for t in paragraph.iter() if t.tag in {W + "t", W + "br"})
    # Existing writer paragraphs contain only text/break runs. Preserve paragraph properties.
    if not _INLINE.search(text):
        return
    for child in tuple(paragraph):
        if child.tag == W + "r":
            paragraph.remove(child)
    cursor = 0
    for match in _INLINE.finditer(text):
        _run(paragraph, text[cursor:match.start()])
        _run(paragraph, match.group("bold") or match.group("italic") or match.group("code") or "",
             "b" if match.group("bold") else "i" if match.group("italic") else None)
        cursor = match.end()
    _run(paragraph, text[cursor:])


def _run(paragraph: Element, text: str, emphasis: str | None = None) -> None:
    if not text:
        return
    run = SubElement(paragraph, W + "r")
    if emphasis:
        SubElement(SubElement(run, W + "rPr"), W + emphasis)
    for index, line in enumerate(text.split("\n")):
        if index:
            SubElement(run, W + "br")
        node = SubElement(run, W + "t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
        node.text = line


def apply_page_profile(root: Element, styles: Element) -> Element:
    section = root.find(".//" + W + "sectPr")
    if section is None:
        raise ValueError("R6_WORD_SECTION_REJECTED")
    size = section.find(W + "pgSz")
    if size is not None:
        size.set(W + "w", "11906")
        size.set(W + "h", "16838")  # A4 portrait
    margins = section.find(W + "pgMar")
    if margins is not None:
        for side in ("top", "right", "bottom", "left"):
            margins.set(W + side, "1134")  # 20 mm
    SubElement(section, W + "footerReference", {W + "type": "default", REL + "id": "rIdClassroomFooter"})
    for paragraph in root.iter(W + "p"):
        format_paragraph(paragraph)
    body = root.find(W + "body")
    if body is not None:
        for paragraph in tuple(body):
            if paragraph.tag == W + "p" and not any(t.text for t in paragraph.iter(W + "t")):
                body.remove(paragraph)
    for table in root.iter(W + "tbl"):
        width = table.find(W + "tblPr/" + W + "tblW")
        if width is not None:
            width.set(W + "w", "9638")
        for column in table.findall(W + "tblGrid/" + W + "gridCol"):
            column.set(W + "w", str(int(int(column.get(W + "w", "0")) * 9638 / 10080)))
        for cell_width in table.findall(".//" + W + "tcW"):
            cell_width.set(W + "w", str(int(int(cell_width.get(W + "w", "0")) * 9638 / 10080)))
        for shade in table.iter(W + "shd"):
            shade.set(W + "fill", "F2F2F2")
    for style in styles.findall(W + "style"):
        style_id = style.get(W + "styleId", "")
        for color in style.iter(W + "color"):
            color.set(W + "val", "000000")
        for font_size in style.iter(W + "sz"):
            font_size.set(W + "val", {"Title": "34", "Heading1": "28", "Heading2": "25", "Note": "20"}.get(style_id, "23"))
    footer = Element(W + "ftr")
    paragraph = SubElement(footer, W + "p")
    SubElement(SubElement(paragraph, W + "pPr"), W + "jc", {W + "val": "center"})
    _run(paragraph, "Page ")
    SubElement(paragraph, W + "fldSimple", {W + "instr": "PAGE"})
    _run(paragraph, " / ")
    SubElement(paragraph, W + "fldSimple", {W + "instr": "NUMPAGES"})
    return footer
