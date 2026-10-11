"""Explicit product diffusion successor, with native media and no technical banners."""
import re
from dataclasses import replace
from io import BytesIO
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from backend.adapters.outbound.export.course_media_word import draw_image
from backend.adapters.outbound.export.diffusion_word_v6 import diffusion_v6_text
from backend.adapters.outbound.export.word import _paragraph
from backend.modules.materialization_export.contracts.dto.word_document import WordDocument
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data

PROFILE_ID = "PRODUCT-DIFFUSION-WORD-7.0"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
_TECHNICAL = re.compile(r"^(?:Version exacte : ver:|CANDIDATE\s*[—−-]|A16\s*:|PROMOTION EXPLICITE ENREGISTRÉE)")
_FICTIVE_TITLE = re.compile(r"^(Évaluation|Exercice|Cours|QCM|Quiz|Questions ouvertes)\s+ficti(?:f|ve|fs|ves)(?=\s*[—−-])", re.I)


class ProductWordWriter:
    def write(self, document: WordDocument) -> bytes:
        from backend.adapters.outbound.export.r6_readable_word import R6ReadableWordWriter

        if document.course_chapter is not None:
            return R6ReadableWordWriter().write(document)
        visible = replace(document, title=_FICTIVE_TITLE.sub(r"\1", document.title),
                          blocks=tuple(b for b in document.blocks if not (
            b.style == "Note" and _TECHNICAL.match(b.text))), production_media=())
        raw = R6ReadableWordWriter(profile="diffusion-v6").write(visible)
        if not document.production_media:
            return raw
        with ZipFile(BytesIO(raw)) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        root = fromstring(parts["word/document.xml"])
        body = root.find(W + "body")
        if body is None:
            raise ValueError("PRODUCTION_WORD_BODY")
        relationships = fromstring(parts["word/_rels/document.xml.rels"])
        types = fromstring(parts["[Content_Types].xml"])
        SubElement(types, "{http://schemas.openxmlformats.org/package/2006/content-types}Default",
                   {"Extension": "png", "ContentType": "image/png"})
        for number, attachment in enumerate(document.production_media, 1):
            heading = re.sub(r"^Q0*(\d+)(?=\s|$)", r"Question \1", attachment.anchor_heading)
            matches = [p for p in body if p.tag == W + "p" and
                       "".join(t.text or "" for t in p.iter(W + "t")) == heading]
            if len(matches) != 1:
                raise ValueError("PRODUCTION_WORD_ANCHOR_AMBIGUOUS")
            pair = attachment.media
            holder = Element("holder")
            draw_image(holder, pair, number)
            _paragraph(holder, "Normal", diffusion_v6_text(str(pair.brief.data["caption"]), kind=document.kind))
            provenance = object_data(pair.asset.data["provenance"])
            if provenance["licence"] in {"CC-BY-4.0", "CC-BY-SA-4.0"}:
                _paragraph(holder, "Note", "Source : " + str(provenance["source_ref"]) + " — " + str(provenance["licence"]))
            position = list(body).index(matches[0]) + 1
            if pair.brief.data["preferred_position"] == "AFTER_DOCUMENT":
                while position < len(body) and body[position].tag != W + "sectPr":
                    style = body[position].find(W + "pPr/" + W + "pStyle")
                    if style is not None and style.get(W + "val") in {"Heading1", "Heading2"}:
                        break
                    position += 1
            # Insert the observation before the prompt. The caption remains with its image.
            for offset, node in enumerate(holder):
                body.insert(position + offset, node)
            SubElement(relationships, PKG + "Relationship", {"Id": "rIdMedia" + str(number),
                       "Type": IMAGE_REL, "Target": "media/figure_" + str(number) + ".png"})
            parts["word/media/figure_" + str(number) + ".png"] = pair.asset.raw
        parts["word/document.xml"] = tostring(root, encoding="utf-8", xml_declaration=True)
        parts["word/_rels/document.xml.rels"] = tostring(relationships, encoding="utf-8", xml_declaration=True)
        parts["[Content_Types].xml"] = tostring(types, encoding="utf-8", xml_declaration=True)
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for name, payload in parts.items():
                info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, payload)
        return output.getvalue()
