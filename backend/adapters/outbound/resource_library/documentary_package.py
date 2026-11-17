"""Bounded attachment parser. Original pieces and local synthesis stay distinct."""
import csv
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from backend.infrastructure.filesystem import read_file_nofollow
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    items,
    object_data,
)
from backend.modules.resource_library.contracts.dto.documentary_library import (
    SCHEMA,
    DocumentaryAttachment,
    DocumentarySnapshot,
    documentary_hash,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _text(node: ET.Element) -> str:
    return "".join(n.text or "" for n in node.iter(W + "t"))


def _capsules(file: DocumentaryAttachment) -> dict[str, dict[str, object]]:
    with zipfile.ZipFile(io.BytesIO(file.content)) as archive:
        entry = archive.getinfo("word/document.xml")
        if entry.file_size > 2_000_000:
            raise ValueError("DOCUMENTARY_DOCX_SIZE")
        xml = archive.read(entry)
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise ValueError("DOCUMENTARY_XML_REJECTED")
    body = ET.fromstring(xml).find(W + "body")
    if body is None:
        raise ValueError("DOCUMENTARY_DOCX_BODY")
    result: dict[str, dict[str, object]] = {}
    current: list[dict[str, object]] | None = None
    for ordinal, node in enumerate(body, 1):
        if node.tag == W + "p":
            text = _text(node)
            style_node = node.find(W + "pPr/" + W + "pStyle")
            style = "" if style_node is None else str(style_node.get(W + "val", ""))
            match = re.match(r"^([DO][0-9]{2})\s", text) if style == "Heading2" else None
            if match:
                key = match[1]
                if key in result:
                    raise ValueError("DOCUMENTARY_CAPSULE_AMBIGUOUS")
                current = []
                result[key] = {"origin": {"file": file.name, "file_sha256": file.sha256,
                    "part": "word/document.xml", "capsule_id": key, "heading_block_ordinal": ordinal},
                    "blocks": current}
            elif style in {"Heading1", "Heading2"}:
                current = None
            if current is not None:
                current.append({"kind": "PARAGRAPH", "text": text, "style": style,
                    "drawing_present": node.find(".//" + W + "drawing") is not None})
        elif node.tag == W + "tbl" and current is not None:
            current.append({"kind": "TABLE", "rows": [
                ["\n".join(_text(p) for p in cell.findall(W + "p")) for cell in row.findall(W + "tc")]
                for row in node.findall(W + "tr")]})
    return result


class LocalDocumentaryPackage:
    def __init__(self, path: Path, expected_sha256: str) -> None:
        self.path, self.expected_sha256 = path, documentary_hash(expected_sha256)

    def read(self) -> tuple[DocumentarySnapshot, tuple[DocumentaryAttachment, ...]]:
        raw = read_file_nofollow(self.path, allowed_root=self.path.parent, maximum_bytes=10_000_000)
        import hashlib
        if hashlib.sha256(raw).hexdigest() != self.expected_sha256:
            raise ValueError("DOCUMENTARY_ARCHIVE_CHANGED")
        files: dict[str, DocumentaryAttachment] = {}
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 100 or sum(e.file_size for e in entries) > 20_000_000:
                raise ValueError("DOCUMENTARY_ARCHIVE_BOUND")
            for entry in entries:
                parts = PurePosixPath(entry.filename).parts
                if (len(parts) != 2 or "\\" in entry.filename or any(p in {"..", "."} for p in parts)
                        or entry.is_dir() or entry.file_size > 4_000_000
                        or entry.external_attr >> 16 & 0o170000 == 0o120000 or parts[1] in files):
                    raise ValueError("DOCUMENTARY_ARCHIVE_ENTRY")
                files[parts[1]] = DocumentaryAttachment(parts[1], archive.read(entry))
        declared = object_data(json.loads(files["08_MANIFESTE_SHA256.json"].content))
        listed = items(declared["files"], 100)
        if (len(listed) != declared["count"] or {r["filename"] for r in listed} != set(files) - {"08_MANIFESTE_SHA256.json"}):
            raise ValueError("DOCUMENTARY_MANIFEST_INVENTORY")
        for row in listed:
            f = files[str(row["filename"])]
            if f.sha256 != row["sha256"] or len(f.content) != row["bytes"]:
                raise ValueError("DOCUMENTARY_ORIGINAL_HASH_CHANGED")
        manifest = object_data(json.loads(files["05_MANIFESTE_SOURCES_POUR_V2.json"].content))
        if manifest.get("schema") != "v2.documentary_source_package.1.0":
            raise ValueError("DOCUMENTARY_INPUT_SCHEMA")
        sources = items(manifest["sources"], 1000)
        csv_rows = list(csv.DictReader(io.StringIO(files["04_INDEX_SOURCES_VERIFIEES.csv"].content.decode("utf-8-sig")), delimiter=";"))
        if (len(csv_rows) != len(sources) or {r["id"] for r in csv_rows} != {s["id"] for s in sources}
                or any(not any(s["id"] == row["id"] and s["url"] == row["url"] for s in sources) for row in csv_rows)):
            raise ValueError("DOCUMENTARY_CSV_MANIFEST_CHANGED")
        parsed: dict[str, dict[str, object]] = {}
        for name, file in files.items():
            if name.startswith(("01_", "02_")) and name.endswith(".docx"):
                values = _capsules(file)
                if set(parsed) & set(values):
                    raise ValueError("DOCUMENTARY_CAPSULE_AMBIGUOUS")
                parsed.update(values)
        metadata = items(manifest["documents"], 1000)
        if set(parsed) != {d["id"] for d in metadata} or len(metadata) != len(parsed):
            raise ValueError("DOCUMENTARY_CAPSULE_COVERAGE")
        organizations = {str(d["organisation"]) for d in metadata}
        docs = [{"id": d["id"], "organization_id": d["organisation"], "metadata": d,
            **parsed[str(d["id"])], "source_ids": d["sources"],
            "content_sha256": fingerprint(parsed[str(d["id"])]["blocks"])} for d in metadata]
        snapshot = DocumentarySnapshot({"schema": SCHEMA, "archive_sha256": self.expected_sha256,
            "manifest": manifest, "organizations": [{"id": name, "label": name,
                "entity_scope": "GROUP_AS_DESCRIBED_BY_SUPPLIED_SOURCES", "legal_anchor_status": "NOT_MAPPED_TO_CANONICAL_IDENTITY"}
                for name in sorted(organizations)], "documents": docs, "sources": sources,
            "files": [{"name": f.name, "sha256": f.sha256, "bytes": len(f.content)} for f in files.values()],
            "authority": {"canonical_admission": "NOT_GRANTED", "pedagogical_validation": "NOT_GRANTED",
                          "transfer_consent": "NOT_GRANTED", "generation_right": "NONE"}})
        return snapshot, tuple(files.values())
