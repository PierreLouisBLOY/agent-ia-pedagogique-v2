"""New synthetic wire fixtures only; never a production repair/conversion path."""
from copy import deepcopy

from tests.support.r3_synthetic import supplements


def wire_supplements(scale="EUR"):
    return wire_fixture(supplements(scale))


def wire_fixture(canonical):
    """Project a KNOWN invented canonical fixture, never a received provider response."""
    data = deepcopy(canonical)
    for question in data["questions"]:
        question["locator"] = {k: question["locator"][k] for k in ("section_id", "exact_text")}
    unit = data["case_data"]["source_unit_locator"]
    data["case_data"]["source_unit_locator"] = {k: unit[k] for k in ("section_id", "exact_text")}
    for answer in data["correction"]["answers"]:
        for calculation in answer["calculations"]:
            del calculation["locator"]
    return data
