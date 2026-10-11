from dataclasses import replace

import pytest

from backend.modules.resource_library.application.queries.get_exact_notion_evidence import (
    GetExactNotionEvidenceQuery,
)
from backend.modules.resource_library.ports.outbound.canonical_notion_catalog import (
    CanonicalNotionIdentityRecord,
)
from backend.modules.resource_library.ports.outbound.exact_notion_evidence import (
    ExactNotionEvidence,
)
from backend.modules.resource_library.ports.outbound.local_search import AdmittedLocalPassage


class Port:
    def __init__(self, value):
        self.value = value
        self.ids = []

    def get_exact_notion_evidence(self, notion_id):
        self.ids.append(notion_id)
        return self.value


def projection():
    return ExactNotionEvidence(
        CanonicalNotionIdentityRecord("notion:cout", "Coût", "CANONICAL"),
        (AdmittedLocalPassage("notion:cout", "NOTION", "chunk:cout", "a" * 64,
                             "Coût", False),),
    )


def test_exact_identity_and_absence_do_not_use_label_or_alias():
    port = Port(projection())
    assert GetExactNotionEvidenceQuery(port).execute("notion:cout") == port.value
    assert port.ids == ["notion:cout"]
    assert GetExactNotionEvidenceQuery(Port(None)).execute("notion:absent") is None


@pytest.mark.parametrize("value", ["../seed", "notion:cout OR 1=1", "", "x" * 257])
def test_invalid_identifier_never_reaches_port(value):
    port = Port(projection())
    with pytest.raises(ValueError, match="INVALID_SEARCH_PROJECTION"):
        GetExactNotionEvidenceQuery(port).execute(value)
    assert port.ids == []


@pytest.mark.parametrize("mutation", ["wrong_identity", "merged", "duplicate"])
def test_identity_and_duplicate_mutations_are_rejected(mutation):
    value = projection()
    if mutation == "wrong_identity":
        value = replace(value, identity=replace(value.identity, notion_id="notion:production"))
    elif mutation == "merged":
        value = replace(value, identity=replace(value.identity, identity_status="MERGED"))
    else:
        value = replace(value, passages=value.passages * 2)
    with pytest.raises(ValueError, match="R6_EXACT_NOTION_IDENTITY_MISMATCH"):
        GetExactNotionEvidenceQuery(Port(value)).execute("notion:cout")
