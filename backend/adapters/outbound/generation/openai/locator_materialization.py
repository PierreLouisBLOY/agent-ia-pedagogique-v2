"""Pure PREPARE wire anchors -> canonical locators, before domain/CAP authority."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

from backend.adapters.outbound.generation.openai.prepare_contract import (
    MAX_BYTES,
    normalized_prepare_text,
)
from backend.adapters.outbound.generation.parse_diagnostic import (
    ParseCode,
    ParseDiagnostic,
    ParseStage,
)
from backend.agent_runtime.agents.generation import (
    GenerationPortError,
    GenerationPortErrorCode,
    GenerationPortRequest,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data


class LocatorMaterializationError(ValueError):
    """Closed reason only, never retain the failed text or section collection."""

    code: ParseCode

    def __init__(self, code: ParseCode) -> None:
        if code not in {
            ParseCode.LOCATOR_SECTION_UNKNOWN,
            ParseCode.LOCATOR_ANCHOR_NOT_FOUND,
            ParseCode.LOCATOR_ANCHOR_AMBIGUOUS,
            ParseCode.CALC_VALUE_OCCURRENCE_INSUFFICIENT,
            ParseCode.CALC_ANSWER_SECTION_INVALID,
        } or type(code) is not ParseCode:
            raise TypeError("LOCATOR_CODE_CLOSED")
        self.code = code
        super().__init__(code.value)


def _locator(section_id: str, text: str, quote: str, start: int) -> dict[str, object]:
    end = start + len(quote)
    if not 0 <= start < end <= len(text) or text[start:end] != quote:
        raise LocatorMaterializationError(ParseCode.LOCATOR_ANCHOR_NOT_FOUND)
    return {"section_id": section_id, "start": start, "end": end, "exact_text": quote}


def materialize_anchor(
    section_id: str, exact_text: str, sections: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Exact unique occurrence, counting overlaps; Python Unicode indices only."""
    matches = [s for s in sections if s.get("section_id") == section_id]
    if not isinstance(section_id, str) or not section_id or len(matches) != 1:
        raise LocatorMaterializationError(ParseCode.LOCATOR_SECTION_UNKNOWN)
    text = matches[0].get("text")
    if not isinstance(text, str):
        raise LocatorMaterializationError(ParseCode.LOCATOR_SECTION_UNKNOWN)
    if not isinstance(exact_text, str) or not exact_text:
        raise LocatorMaterializationError(ParseCode.LOCATOR_ANCHOR_NOT_FOUND)
    start = text.find(exact_text)
    if start < 0:
        raise LocatorMaterializationError(ParseCode.LOCATOR_ANCHOR_NOT_FOUND)
    if text.find(exact_text, start + 1) >= 0:
        raise LocatorMaterializationError(ParseCode.LOCATOR_ANCHOR_AMBIGUOUS)
    return _locator(section_id, text, exact_text, start)


def calculation_locators(
    question_id: str, expected_answer: str, values: Sequence[str],
) -> tuple[dict[str, object], ...]:
    """Group by exact value; ordered distinct spans, no alternative assignment."""
    if (not isinstance(question_id, str) or not question_id or len(question_id) > 80
            or not isinstance(expected_answer, str) or not expected_answer):
        raise LocatorMaterializationError(ParseCode.CALC_ANSWER_SECTION_INVALID)
    groups: dict[str, list[int]] = {}
    for index, value in enumerate(values):
        if not isinstance(value, str) or re.fullmatch(r"-?(?:0|[1-9][0-9]{0,8})\.[0-9]{2}", value) is None:
            raise LocatorMaterializationError(ParseCode.CALC_VALUE_OCCURRENCE_INSUFFICIENT)
        groups.setdefault(value, []).append(index)
    assigned: dict[int, dict[str, object]] = {}
    used: list[tuple[int, int]] = []
    for value, indices in groups.items():
        occurrences: list[int] = []
        cursor = 0
        while (start := expected_answer.find(value, cursor)) >= 0:
            occurrences.append(start)
            cursor = start + len(value)
        if len(occurrences) < len(indices):
            raise LocatorMaterializationError(ParseCode.CALC_VALUE_OCCURRENCE_INSUFFICIENT)
        for index, start in zip(indices, occurrences[:len(indices)], strict=True):
            end = start + len(value)
            if any(start < right and left < end for left, right in used):
                raise LocatorMaterializationError(ParseCode.CALC_VALUE_OCCURRENCE_INSUFFICIENT)
            assigned[index] = _locator(question_id, expected_answer, value, start)
            used.append((start, end))
    return tuple(assigned[i] for i in range(len(values)))


def materialized_prepare_text(
    output_text: str | None, request: GenerationPortRequest, diagnostic: ParseDiagnostic,
) -> str:
    """Validate the new closed wire shape FIRST; old offsets are never overwritten."""
    text = normalized_prepare_text(output_text, diagnostic)
    diagnostic.begin(ParseStage.DOMAIN_MAP)
    try:
        data = object_data(json.loads(text))
        try:
            sections = items(object_data(request.resolved_inputs["subject"])["sections"], 5)
        except (ValueError, TypeError, KeyError):
            raise LocatorMaterializationError(ParseCode.LOCATOR_SECTION_UNKNOWN) from None
        questions = items(data["questions"], 30)
        for question in questions:
            anchor = object_data(question["locator"], {"section_id", "exact_text"})
            if anchor["section_id"] != question["dossier_id"]:
                raise LocatorMaterializationError(ParseCode.LOCATOR_SECTION_UNKNOWN)
            question["locator"] = materialize_anchor(
                str(anchor["section_id"]), str(anchor["exact_text"]), sections)
        data["questions"] = questions
        case = object_data(data["case_data"])
        anchor = object_data(case["source_unit_locator"], {"section_id", "exact_text"})
        case["source_unit_locator"] = materialize_anchor(
            str(anchor["section_id"]), str(anchor["exact_text"]), sections)
        data["case_data"] = case
        correction = object_data(data["correction"])
        answers = items(correction["answers"], 60)
        ids = [a["question_id"] for a in answers]
        question_ids = [q["question_id"] for q in questions]
        for answer in answers:
            qid = str(answer["question_id"])
            if ids.count(qid) != 1 or question_ids.count(qid) != 1:
                raise LocatorMaterializationError(ParseCode.CALC_ANSWER_SECTION_INVALID)
            calculations = items(answer["calculations"], 60)
            locators = calculation_locators(qid, str(answer["expected_answer"]),
                                            [str(c["value"]) for c in calculations])
            for calculation, locator in zip(calculations, locators, strict=True):
                calculation["locator"] = locator
            answer["calculations"] = calculations
        correction["answers"] = answers
        data["correction"] = correction
        result = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if len(result.encode("utf-8")) > MAX_BYTES:
            diagnostic.fail(ParseCode.CARDINALITY_INVALID)
            raise GenerationPortError(GenerationPortErrorCode.INVALID_RESPONSE,
                                      "OPENAI_PREPARE_MATERIALIZATION_BOUND")
        return result
    except LocatorMaterializationError as error:
        diagnostic.fail(error.code)
        raise GenerationPortError(GenerationPortErrorCode.INVALID_RESPONSE, error.code.value) from None
    except (ValueError, TypeError, KeyError):
        diagnostic.fail(ParseCode.DOMAIN_MAPPING_FAILURE)
        raise GenerationPortError(GenerationPortErrorCode.INVALID_RESPONSE,
                                  "OPENAI_PREPARE_MATERIALIZATION_INVALID") from None
