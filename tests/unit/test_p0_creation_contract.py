"""Synthetic unit mutations, distinct from authenticated HTTP matrix proofs."""
import hashlib
from secrets import token_hex

import pytest

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain
from backend.modules.pedagogical_design.contracts.dto.p0_production import P0_PROVENANCE_LABEL
from backend.modules.work_orchestration.application.services.p0_creation import P0CreationService
from tests.integration.test_p0_creation_http import context
from tests.support.p0_generation_double import P0GenerationDouble


def service(double):
    excerpt = "Synthetic unit reference, no canonical authority."
    return P0CreationService(lambda selection: {"excerpt": excerpt, "reference": {
        "evidence_id": "evidence:" + "1" * 32, "source_ref": "unit:synthetic", "locator": "unit:v1",
        "checksum_or_version": "unit:v1", "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "provenance_label": P0_PROVENANCE_LABEL}}, generation=double)


class MutatedOutput(P0GenerationDouble):
    def __init__(self, mutation):
        super().__init__()
        self.mutation = mutation

    def generate(self, *, request):
        result = as_plain(super().generate(request=request))
        if self.mutation == "incomplete":
            del result["corrections"]
        elif self.mutation == "context":
            result["context"]["level"] = "FIRST_STMG"
        elif self.mutation == "identity":
            result["production_ref"] = "prod:" + "2" * 32
        elif self.mutation == "references":
            result["references"][0]["excerpt_sha256"] = "0" * 64
        elif self.mutation == "lineage":
            result["lineage"]["parent_version_ref"] = "ver:" + "3" * 32
        return result


@pytest.mark.parametrize("mutation", ("incomplete", "context", "identity", "references", "lineage"))
def test_output_substitution_never_publishes_or_replays(mutation):
    double = MutatedOutput(mutation)
    app = service(double)
    prepared = app.execute("prepare", {"command_id": token_hex(16), "context": context("BTS_CG_YEAR_2", "ASSESSMENT", None), "reference": {}})
    command = {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
               "preparation_sha256": prepared["preparation_sha256"]}
    with pytest.raises(ValueError):
        app.execute("generate", command)
    assert not app.records and len(double.requests) == 1
    assert app.execute("generate", command)["state"] in {"REFUSED", "OUTCOME_UNKNOWN"}
    with pytest.raises(ValueError, match="P0_PREPARATION_CHANGED"):
        app.execute("generate", dict(command, command_id=token_hex(16)))
    assert len(double.requests) == 1


def test_command_rebind_and_stale_version_are_rejected_without_parent_mutation():
    app = service(P0GenerationDouble())
    body = {"command_id": token_hex(16), "context": context("BTS_CG_YEAR_2", "ASSESSMENT", None), "reference": {}}
    prepared = app.execute("prepare", body)
    with pytest.raises(ValueError, match="P0_IDEMPOTENCY_CONFLICT"):
        app.execute("prepare", dict(body, context=context("FIRST_STMG", "COURSE", None)))
    view = app.execute("generate", {"command_id": token_hex(16), "preparation_ref": prepared["preparation_ref"],
                                   "preparation_sha256": prepared["preparation_sha256"]})["view"]
    parent = app.saved_source(view["production_ref"], view["version_ref"])
    with pytest.raises(ValueError, match="P0_VERSION_CHANGED"):
        app.execute("revise", {"command_id": token_hex(16), "production_ref": parent.production_ref,
            "version_ref": parent.version_ref, "bundle_sha256": "0" * 64, "edits": {"title": "Substitution"}})
    assert app.saved_source(parent.production_ref, parent.version_ref).sha256 == parent.sha256


def test_incomplete_context_refused_before_reference_and_dispatch():
    calls = []
    app = P0CreationService(lambda data: calls.append(data))
    with pytest.raises(ValueError):
        app.execute("prepare", {"command_id": token_hex(16), "context": {}, "reference": {}})
    assert calls == [] and app.records == {}
