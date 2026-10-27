import json
from hashlib import sha256

import pytest

from backend.adapters.inbound.api.p0_creation import P0CreationEndpoint
from backend.infrastructure.composition.factories.organization_capture import (
    organization_capture_reader,
)
from tests.test_organization_evidence_325 import official_identity


def test_pinned_capture_query_no_admission_or_injection(tmp_path):
    data = {
        "schema": "LOCAL-ORGANIZATION-CAPTURES-1.0",
        "records": [dict(official_identity().data)],
    }
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    path = tmp_path / "SYNTHETIC-capture.json"
    path.write_bytes(raw)
    descriptor = {"path": str(path), "sha256": sha256(raw).hexdigest()}
    reader = organization_capture_reader(descriptor)
    endpoint = P0CreationEndpoint(
        lambda *_: (_ for _ in ()).throw(AssertionError("NO_EFFECT")),
        lambda *_: {},
        [],
        nonce="synthetic",
    )
    endpoint.organization_capture_reader = reader.inspect
    status, _, body, _ = endpoint.respond(
        "GET", "/api/v2/p0/organizations/siren:306138900", b"", "synthetic326"
    )
    observed = json.loads(body)["data"]
    assert (
        status == 200
        and observed["canonical_admission"] == "NOT_GRANTED"
        and observed["provider_generation_calls"] == 0
    )
    assert observed["items"][0]["kind"] == "DOCUMENTED_FACT"
    assert path.read_bytes() == raw
    for method, target in (
        ("POST", "/api/v2/p0/organizations/siren:306138900"),
        ("GET", "/api/v2/p0/organizations/siren:306138900?url=https://evil"),
        ("GET", "/api/v2/p0/organizations/siren:000000000"),
    ):
        assert endpoint.respond(method, target, b"", "synthetic326")[0] == 409
    with pytest.raises(ValueError):
        organization_capture_reader({**descriptor, "sha256": "0" * 64})
    data["records"] *= 2
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="DUPLICATE"):
        organization_capture_reader({"path": str(path), "sha256": sha256(raw).hexdigest()})
