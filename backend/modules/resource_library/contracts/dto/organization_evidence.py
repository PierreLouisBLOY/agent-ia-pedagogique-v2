"""Bounded public-source proposal; discovery never grants canonical admission."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from backend.shared_kernel._safe_data import freeze_safe_mapping


@dataclass(frozen=True, slots=True)
class OrganizationEvidence:
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        fields = {
            "schema",
            "organization_id",
            "organization_label",
            "fact",
            "source_url",
            "publisher",
            "retrieved_on",
            "license",
            "license_url",
            "reuse_scope",
            "attribution",
            "kind",
            "admission",
        }
        if not isinstance(self.data, Mapping) or set(self.data) != fields:
            raise ValueError("P0_EXTERNAL_EVIDENCE_FIELDS")
        data = dict(self.data)
        if (
            data["schema"] != "PUBLIC-ORGANIZATION-EVIDENCE-1.0"
            or data["kind"] != "DOCUMENTED_FACT"
            or data["admission"] != "PROPOSED_NOT_CANONICALLY_ADMITTED"
            or data["license"] != "Licence Ouverte / Open Licence 2.0"
        ):
            raise ValueError("P0_EXTERNAL_EVIDENCE_CONTRACT")
        for value in data.values():
            if not isinstance(value, str) or not value.strip() or len(value) > 4000:
                raise ValueError("P0_EXTERNAL_EVIDENCE_TEXT")
        for key in ("source_url", "license_url"):
            parsed = urlsplit(str(data[key]))
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ValueError("P0_EXTERNAL_EVIDENCE_URL")
        date.fromisoformat(str(data["retrieved_on"]))
        object.__setattr__(self, "data", freeze_safe_mapping(data))

    def documentary_text(self) -> str:
        d = self.data
        return (
            str(d["organization_label"])
            + " — "
            + str(d["fact"])
            + "\nSource : "
            + str(d["source_url"])
            + " ; "
            + str(d["publisher"])
            + " ; consulté le "
            + str(d["retrieved_on"])
            + "\nLicence : "
            + str(d["license"])
            + " ("
            + str(d["license_url"])
            + ") ; périmètre : "
            + str(d["reuse_scope"])
            + "\nAttribution : "
            + str(d["attribution"])
            + ". Proposition documentaire ; admission canonique distincte."
        )
