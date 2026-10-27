"""Closed immutable identity of an owner-approved binary format reference."""
import re
from copy import deepcopy
from datetime import date

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    fingerprint,
    object_data,
)

FIELDS = {"schema", "reference_id", "title", "document_type", "level", "scope",
    "approval_status", "decision_date", "decision_sha256", "source_sha256", "size_bytes",
    "storage_ref", "provenance", "media_policy"}


class FormatReference:
    def __init__(self, value: object) -> None:
        data = deepcopy(object_data(value, FIELDS))
        ref = data["reference_id"]
        if type(ref) is not str or re.fullmatch(r"V2-FORMAT-[A-Z0-9-]{1,80}", ref) is None:
            raise ValueError("FORMAT_REFERENCE_ID")
        if (data["schema"] != "FORMAT-REFERENCE-1.0"
                or data["document_type"] != "cours_version_eleve"
                or data["approval_status"] != "OWNER_APPROVED_REFERENCE"
                or data["media_policy"] != "NO_REDISTRIBUTION_WITHOUT_RIGHTS"
                or data["storage_ref"] != "format-reference:" + ref + "/document.docx"):
            raise ValueError("FORMAT_REFERENCE_SCOPE")
        for key in ("title", "level", "decision_date"):
            text = data[key]
            if type(text) is not str or not 1 <= len(text) <= 300:
                raise ValueError("FORMAT_REFERENCE_TEXT")
        date.fromisoformat(str(data["decision_date"]))
        for key in ("decision_sha256", "source_sha256"):
            if type(data[key]) is not str or re.fullmatch(r"[0-9a-f]{64}", str(data[key])) is None:
                raise ValueError("FORMAT_REFERENCE_HASH")
        if type(data["size_bytes"]) is not int or not 1 <= data["size_bytes"] <= 16 * 1024 * 1024:
            raise ValueError("FORMAT_REFERENCE_SIZE")
        scope = object_data(data["scope"], {"approved_for", "excluded"})
        for values in scope.values():
            if (type(values) is not list or not 1 <= len(values) <= 20
                    or any(type(v) is not str or not 1 <= len(v) <= 200 for v in values)
                    or len(values) != len(set(values))):
                raise ValueError("FORMAT_REFERENCE_SCOPE")
        provenance = object_data(data["provenance"], {"kind", "filename", "decision_ref"})
        if (provenance["kind"] != "OWNER_PROVIDED_DOCX"
                or provenance["decision_ref"] != "owner-decision:" + str(data["decision_sha256"])
                or type(provenance["filename"]) is not str
                or re.fullmatch(r"[^/\\:]{1,200}\.docx", str(provenance["filename"])) is None):
            raise ValueError("FORMAT_REFERENCE_PROVENANCE")
        self._data = data

    def as_dict(self) -> dict[str, object]:
        return deepcopy(self._data)

    @property
    def reference_id(self) -> str:
        return str(self._data["reference_id"])

    @property
    def version_ref(self) -> str:
        return "format-version:" + fingerprint(self._data)
