"""Original V2 COURSE template, activated only by an explicit chapter projection."""
from io import BytesIO
from typing import cast
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.adapters.outbound.export.course_media_word import draw_image
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _w(name: str) -> str:
    return "{" + W + "}" + name


def _p(parent: Element, text: str, style: str = "Normal", *, before: bool = False) -> Element:
    p = SubElement(parent, _w("p"))
    pr = SubElement(p, _w("pPr"))
    SubElement(pr, _w("pStyle"), {_w("val"): style})
    if before:
        SubElement(pr, _w("pageBreakBefore"))
    for i, line in enumerate(text.split("\n")):
        run = SubElement(p, _w("r"))
        if i:
            SubElement(run, _w("br"))
        SubElement(run, _w("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = line
    return p


def _table(parent: Element, value: object, *, response: bool = False) -> None:
    data = object_data(value)
    columns = cast(tuple[str, ...], data["columns"])
    rows = cast(tuple[tuple[str, ...], ...], data["rows"])
    table = SubElement(parent, _w("tbl"))
    props = SubElement(table, _w("tblPr"))
    SubElement(props, _w("tblW"), {_w("w"): "9638", _w("type"): "dxa"})
    SubElement(props, _w("tblLayout"), {_w("type"): "fixed"})
    margins = SubElement(props, _w("tblCellMar"))
    for side in ("top", "bottom", "left", "right"):
        SubElement(margins, _w(side), {_w("w"): "100", _w("type"): "dxa"})
    borders = SubElement(props, _w("tblBorders"))
    for side in ("top", "bottom", "left", "right", "insideH", "insideV"):
        SubElement(borders, _w(side), {_w("val"): "single", _w("sz"): "4", _w("color"): "CCD4DE"})
    grid = SubElement(table, _w("tblGrid"))
    width = 9638 // len(columns)
    for _ in columns:
        SubElement(grid, _w("gridCol"), {_w("w"): str(width)})
    for i, row in enumerate((columns, *rows)):
        tr = SubElement(table, _w("tr"))
        pr = SubElement(tr, _w("trPr"))
        SubElement(pr, _w("cantSplit"))
        if i == 0:
            SubElement(pr, _w("tblHeader"))
        elif response:
            SubElement(pr, _w("trHeight"), {_w("val"): "460", _w("hRule"): "atLeast"})
        for text in row:
            cell = SubElement(tr, _w("tc"))
            cp = SubElement(cell, _w("tcPr"))
            SubElement(cp, _w("tcW"), {_w("w"): str(width), _w("type"): "dxa"})
            SubElement(cp, _w("vAlign"), {_w("val"): "center"})
            SubElement(cp, _w("shd"), {_w("fill"): "F5E6CC" if i == 0 else "F4F7FA" if i % 2 == 0 else "FFFFFF"})
            _p(cell, text, "TableHeader" if i == 0 else "TableText")
    _p(parent, "", "Spacer")


def _document(parent: Element, row: dict[str, object], number: int) -> None:
    _p(parent, f"Document {number} — {row['title']}", "DocumentTitle")
    _p(parent, str(row["text"]), "DocumentText")
    if row["table"] is not None:
        _table(parent, row["table"])


def _question(parent: Element, row: dict[str, object], answer: dict[str, object] | None, *, keep_responses: bool = False) -> None:
    _p(parent, f"{row['number']}. {row['prompt']}", "Question")
    if answer is not None:
        for label, field in (("Réponse attendue", "expected_answer"), ("Justification", "rationale"),
                             ("Point de vigilance", "vigilance"), ("Remédiation", "remediation")):
            _p(parent, label + " — " + str(answer[field]), "TeacherAnswer")
        return
    response = object_data(row["response"])
    if response["table"] is not None:
        _table(parent, response["table"], response=True)
    else:
        lines = cast(int, response["lines"])
        for i in range(lines):
            p = _p(parent, " ", "Response")
            if keep_responses and i < lines-1:
                pr = p.find(_w("pPr"))
                if pr is not None:
                    SubElement(pr, _w("keepNext"))


def _styles() -> Element:
    root = Element(_w("styles"))
    defaults = SubElement(root, _w("docDefaults"))
    rd = SubElement(SubElement(defaults, _w("rPrDefault")), _w("rPr"))
    SubElement(rd, _w("rFonts"), {_w("ascii"): "Calibri", _w("hAnsi"): "Calibri"})
    SubElement(rd, _w("lang"), {_w("val"): "fr-FR"})
    specs = {"Normal": (22, False, 100), "Title": (38, True, 200), "Chapter": (24, True, 120),
             "Heading1": (29, True, 160), "Heading2": (24, True, 120), "DocumentTitle": (22, True, 90),
             "DocumentText": (22, False, 100), "Question": (22, True, 80), "Response": (22, False, 80),
             "ConceptTitle": (22, True, 60), "ConceptText": (22, False, 140),
             "TeacherAnswer": (21, False, 80), "TableHeader": (21, True, 30), "TableText": (21, False, 30),
             "Footer": (18, False, 0), "Header": (20, True, 0), "Spacer": (8, False, 20)}
    for name, (size, bold, after) in specs.items():
        s = SubElement(root, _w("style"), {_w("type"): "paragraph", _w("styleId"): name})
        SubElement(s, _w("name"), {_w("val"): name})
        p = SubElement(s, _w("pPr"))
        SubElement(p, _w("spacing"), {_w("after"): str(after), _w("line"): "260", _w("lineRule"): "auto"})
        SubElement(p, _w("widowControl"))
        if name in {"Title", "Chapter", "Heading1", "Heading2", "DocumentTitle", "ConceptTitle", "Question"}:
            SubElement(p, _w("keepNext"))
        if name.startswith("Concept"):
            SubElement(p, _w("shd"), {_w("fill"): "E7F2F0"})
            SubElement(p, _w("ind"), {_w("left"): "120", _w("right"): "120"})
        if name == "Response":
            border = SubElement(p, _w("pBdr"))
            SubElement(border, _w("bottom"), {_w("val"): "dotted", _w("sz"): "4", _w("color"): "A6AFBB"})
        if name == "DocumentTitle":
            SubElement(p, _w("shd"), {_w("fill"): "F5E6CC"})
        run = SubElement(s, _w("rPr"))
        SubElement(run, _w("sz"), {_w("val"): str(size)})
        SubElement(run, _w("color"), {_w("val"): "000000"})
        if bold:
            SubElement(run, _w("b"))
    return root


class CourseOOXMLWordWriter:
    def write(self, document: WordDocument) -> bytes:
        chapter = object_data(document.course_chapter)
        teacher = document.kind == "correction"
        if document.kind not in {"student", "correction"} or ("teacher_answers" in chapter) != teacher:
            raise ValueError("COURSE_WORD_PROJECTION")
        projected_media = items(chapter.get("media_assets", []), 8)
        expected_media = tuple(p.asset.projection(p.brief) for p in document.course_media)
        if projected_media != expected_media or any(not p.brief.data["teacher_visibility" if teacher else "student_visibility"] for p in document.course_media):
            raise ValueError("COURSE_WORD_MEDIA_PROVENANCE_BINDING")
        root = Element(_w("document"))
        body = SubElement(root, _w("body"))
        emitted: set[str] = set()
        def media_at(section_ref: str, position: str) -> None:
            for number, pair in enumerate(document.course_media, 1):
                brief = pair.brief.data
                if (brief["section_ref"] == section_ref and brief["preferred_position"] == position
                        and str(brief["visual_id"]) not in emitted):
                    draw_image(body, pair, number)
                    _p(body, str(brief["caption"]), "DocumentText")
                    provenance = object_data(pair.asset.data["provenance"])
                    if provenance["licence"] in {"CC-BY-4.0", "CC-BY-SA-4.0"}:
                        _p(body, "Source : "+str(provenance["source_ref"])+" — "+str(provenance["licence"]), "Footer")
                    emitted.add(str(brief["visual_id"]))
        header = object_data(chapter["program_header"])
        _p(body, "CHAPITRE " + str(chapter["chapter_number"]), "Chapter")
        _p(body, str(chapter["title"]), "Title")
        _p(body, str(header["theme_label"]), "Heading2")
        caps = items(chapter["capabilities"])
        _table(body, {"columns": ("Repère", "Contenu"), "rows": (
            ("Question du programme", str(header["question_label"])),
            ("Capacités travaillées", "\n".join(str(c["label"]) for c in caps)),
            ("Notions mobilisées", ", ".join(cast(tuple[str, ...], chapter["notions"]))),
        )})
        story = object_data(chapter["context"])
        _p(body, "Contexte — " + str(story["title"]), "Heading2")
        _p(body, str(story["text"]))
        media_at("CONTEXT", "AFTER_CONTEXT")
        _p(body, "Votre travail — Lire les documents, relever les faits puis justifier chaque réponse avec les notions du chapitre.")
        docs = {str(d["id"]): d for d in items(chapter["documents"])}
        doc_numbers = {ref: i for i, ref in enumerate(docs, 1)}
        questions = {str(q["id"]): q for q in items(chapter["questions"], 60)}
        concepts = {str(c["id"]): c for c in items(chapter["concepts"])}
        answers = {str(a["id"]): a for a in items(chapter["teacher_answers"], 60)} if teacher else {}
        flowing_teacher = teacher and bool(document.course_media)
        enriched = any(p.brief.data["style_policy"] == "COURSE_LOCAL_ILLUSTRATION_V2" for p in document.course_media)
        for part_index, part in enumerate(items(chapter["parts"])):
            _p(body, str(part["title"]), "Heading1", before=part_index == 0 or not flowing_teacher)
            for ref in cast(tuple[str, ...], part["document_ids"]):
                _document(body, docs[ref], doc_numbers[ref])
                media_at(ref, "AFTER_DOCUMENT")
            for role in ("observation", "analysis"):
                for ref in cast(tuple[str, ...], part[role]):
                    _question(body, questions[ref], answers.get(ref), keep_responses=enriched)
            for ref in cast(tuple[str, ...], part["concept_ids"]):
                c = concepts[ref]
                _p(body, "Notion — " + str(c["notion"]), "ConceptTitle")
                _p(body, str(c["definition"]) + "\n" + str(c["explanation"]) + "\nExemple — " + str(c["example"]), "ConceptText")
                media_at(ref, "AFTER_CONCEPT")
            for ref in cast(tuple[str, ...], part["reinvestment"]):
                _question(body, questions[ref], answers.get(ref), keep_responses=enriched)
        _p(body, "Tester ses connaissances", "Heading1", before=not flowing_teacher and not enriched)
        for ref in cast(tuple[str, ...], chapter["knowledge_check"]):
            _question(body, questions[ref], answers.get(ref), keep_responses=enriched)
        _p(body, "À retenir", "Heading2")
        _p(body, str(chapter["synthesis"]), "ConceptText")
        transfer = object_data(chapter["transfer"])
        _p(body, str(transfer["title"]), "Heading1", before=not flowing_teacher)
        for ref in cast(tuple[str, ...], transfer["document_ids"]):
            _document(body, docs[ref], doc_numbers[ref])
            media_at(ref, "AFTER_DOCUMENT")
        for ref in cast(tuple[str, ...], transfer["question_ids"]):
            _question(body, questions[ref], answers.get(ref), keep_responses=enriched)
        section = SubElement(body, _w("sectPr"))
        SubElement(section, _w("headerReference"), {_w("type"): "default", "{" + R + "}id": "rId2"})
        SubElement(section, _w("footerReference"), {_w("type"): "default", "{" + R + "}id": "rId3"})
        SubElement(section, _w("pgSz"), {_w("w"): "11906", _w("h"): "16838"})
        SubElement(section, _w("pgMar"), {_w("top"): "1134", _w("bottom"): "1134", _w("left"): "1134", _w("right"): "1134", _w("header"): "567", _w("footer"): "567"})
        page_header = Element(_w("hdr"))
        _p(page_header, str(header["subject_label"]).upper() + " • " + str(header["level_label"]).upper(), "Header")
        page_footer = Element(_w("ftr"))
        p = _p(page_footer, "Chapitre " + str(chapter["chapter_number"]) + " • Version " + ("professeur" if teacher else "élève") + " | ", "Footer")
        field = SubElement(p, _w("fldSimple"), {_w("instr"): " PAGE "})
        SubElement(SubElement(field, _w("r")), _w("t")).text = "1"
        rels = Element("Relationships", {"xmlns": PKG})
        SubElement(rels, "Relationship", {"Id": "rId1", "Type": R + "/officeDocument", "Target": "word/document.xml"})
        doc_rels = Element("Relationships", {"xmlns": PKG})
        for number, kind, name in ((1, "styles", "styles.xml"), (2, "header", "header1.xml"), (3, "footer", "footer1.xml")):
            SubElement(doc_rels, "Relationship", {"Id": "rId" + str(number), "Type": R + "/" + kind, "Target": name})
        if len(emitted) != len(document.course_media):
            raise ValueError("COURSE_WORD_MEDIA_NOT_PLACED")
        for number, _ in enumerate(document.course_media, 1):
            SubElement(doc_rels, "Relationship", {"Id": "rIdMedia"+str(number), "Type": R+"/image", "Target": "media/figure_"+str(number)+".png"})
        types = Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
        SubElement(types, "Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
        if document.course_media:
            SubElement(types, "Default", {"Extension": "png", "ContentType": "image/png"})
        for name, kind in (("document.xml", "document.main"), ("styles.xml", "styles"), ("header1.xml", "header"), ("footer1.xml", "footer")):
            SubElement(types, "Override", {"PartName": "/word/" + name, "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml." + kind + "+xml"})
        parts = {"[Content_Types].xml": types, "_rels/.rels": rels, "word/document.xml": root,
                 "word/styles.xml": _styles(), "word/header1.xml": page_header,
                 "word/footer1.xml": page_footer, "word/_rels/document.xml.rels": doc_rels}
        result = BytesIO()
        with ZipFile(result, "w") as archive:
            for name, node in parts.items():
                info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, tostring(node, encoding="utf-8", xml_declaration=True))
            for number, pair in enumerate(document.course_media, 1):
                info = ZipInfo("word/media/figure_"+str(number)+".png", (2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, pair.asset.raw)
        return result.getvalue()
