from copy import deepcopy

import pytest

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    AssessmentBundle,
    source_to_eur,
)
from tests.support.r3_synthetic import bundle


def test_explicit_source_scale_converts_and_never_guesses():
    assert source_to_eur("180.00", "kEUR", explicit_label="k€") == "180000.00"
    assert source_to_eur("180.00", "EUR", explicit_label="EUR") == "180.00"
    for scale, label in ((None, None), ("kEUR", "EUR"), ("EUR", "k€"), ("unknown", "euros")):
        with pytest.raises(ValueError, match="SOURCE_SCALE_REQUIRED"):
            source_to_eur("180.00", scale, explicit_label=label)


def test_bundle_immutable_bounded_and_hash_bound():
    b = bundle()
    with pytest.raises(TypeError):
        b.data["version_ref"] = "oops"
    for patch in ({"unknown": 1}, {"subject_sha256": "0" * 64}, {"version_ref": "latest"}):
        data = deepcopy(b.mutable_copy())
        data.update(patch)
        with pytest.raises(ValueError):
            AssessmentBundle(data)
