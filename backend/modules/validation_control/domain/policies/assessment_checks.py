"""Sixteen pure, closed checks. Generated assertions cannot become authority."""
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import cast

from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    DOSSIERS,
    AssessmentBundle,
    decimal_value,
    fingerprint,
    items,
    locate,
    nonempty,
    object_data,
    source_to_eur,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import SECTION_IDS
from backend.modules.validation_control.contracts.dto.deterministic_validation import (
    AssessmentCheck,
)

GROUPS = ("stable_resources", "stable_uses", "current_assets", "current_liabilities",
          "cash_assets", "cash_liabilities")


def evaluate_expression(expression: object, case: Mapping[str, object], *, depth: int = 1) -> Decimal:
    """Closed data AST, one case only; no executable expression or implicit rounding."""
    if depth > 4:
        raise ValueError("EXPRESSION_DEPTH")
    node = object_data(expression)
    if set(node) == {"ref"}:
        ref = nonempty(node["ref"], 80)
        section, separator, key = ref.partition(".")
        if not separator or section not in {"totals", "computed"}:
            raise ValueError("EXPRESSION_REFERENCE")
        return decimal_value(object_data(case[section])[key])
    object_data(node, {"op", "operands"})
    operands = items(node["operands"], 16)
    if node["op"] not in {"ADD", "SUB"} or not 2 <= len(operands) <= 16:
        raise ValueError("EXPRESSION_OPERATOR")
    values = [evaluate_expression(n, case, depth=depth + 1) for n in operands]
    result = values[0]
    for value in values[1:]:
        result = result + value if node["op"] == "ADD" else result - value
    if abs(result) > Decimal("999999999.99") or result != result.quantize(Decimal("0.01")):
        raise ValueError("EXPRESSION_DECIMAL")
    return result


def case_values(case: Mapping[str, object]) -> dict[str, Decimal]:
    totals = object_data(case["totals"], set(GROUPS))
    return {key: decimal_value(value) for key, value in totals.items()}


def _all_cases(data: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    case = object_data(data["case_data"], {"currency", "source_scale", "source_unit_locator",
                                         "base_case", "scenarios"})
    return (object_data(case["base_case"]), *items(case["scenarios"], 10))


def _questions(data: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    return items(data["questions"], 30)


def _mark_questions(data: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    marking = object_data(data["marking"], {"production_ref", "version_ref", "total_points", "dossiers"})
    return tuple(q for d in items(marking["dossiers"], 3) for q in items(d["questions"], 30))


def check_rule(index: int, data: Mapping[str, object], *,
               parent: AssessmentBundle | None, references: tuple[Mapping[str, object], ...]) -> bool:
    subject = object_data(data["subject"])
    sections = subject["sections"]
    questions = _questions(data)
    answers = items(object_data(data["correction"], {"production_ref", "version_ref", "answers"})["answers"])
    qids = tuple(q["question_id"] for q in questions)
    if index == 1:
        return all((object_data(data[p])["production_ref"], object_data(data[p])["version_ref"]) ==
                   (data["production_ref"], data["version_ref"]) for p in ("correction", "marking"))
    if index == 2:
        return tuple(s["section_id"] for s in items(sections, 5)) == SECTION_IDS and bool(questions)
    if index == 3:
        for q in questions:
            object_data(q, {"question_id", "dossier_id", "locator", "instruction",
                            "expected_skill", "calculation_refs"})
            nonempty(q["question_id"], 80)
            nonempty(q["instruction"])
            nonempty(q["expected_skill"])
            if q["dossier_id"] not in DOSSIERS or object_data(q["locator"])["section_id"] != q["dossier_id"]:
                return False
            locate(q["locator"], sections)
        return len(qids) == len(set(qids)) and {q["dossier_id"] for q in questions} == set(DOSSIERS)
    if index == 4:
        for a in answers:
            object_data(a, {"question_id", "expected_answer", "rationale", "calculations"})
            nonempty(a["expected_answer"])
            nonempty(a["rationale"])
        return len(answers) == len(qids) and {a["question_id"] for a in answers} == set(qids)
    if index == 5:
        marked = _mark_questions(data)
        owning_dossier = {q["question_id"]: q["dossier_id"] for q in questions}
        for dossier in items(object_data(data["marking"])["dossiers"], 3):
            object_data(dossier, {"dossier_id", "duration_minutes", "questions"})
            if any(owning_dossier.get(q["question_id"]) != dossier["dossier_id"]
                   for q in items(dossier["questions"], 30)):
                return False
        criteria_ids = []
        for q in marked:
            object_data(q, {"question_id", "points", "criteria"})
            for criterion in items(q["criteria"], 8):
                object_data(criterion, {"criterion_id", "description", "points"})
                nonempty(criterion["description"])
                criteria_ids.append(nonempty(criterion["criterion_id"], 80))
        return (len(marked) == len(qids) and {q["question_id"] for q in marked} == set(qids)
                and len(criteria_ids) == len(set(criteria_ids)))
    if index == 6:
        marked = _mark_questions(data)
        for q in marked:
            points = decimal_value(q["points"])
            criteria = items(q["criteria"], 8)
            if not criteria or not Decimal(0) < points <= Decimal(20):
                return False
            if any(not Decimal(0) < decimal_value(c["points"]) <= points for c in criteria):
                return False
            if sum((decimal_value(c["points"]) for c in criteria), Decimal(0)) != points:
                return False
        return (decimal_value(object_data(data["marking"])["total_points"]) == Decimal(20)
                and sum((decimal_value(q["points"]) for q in marked), Decimal(0)) == Decimal(20))
    if index == 7:
        case_data = object_data(data["case_data"])
        label = locate(case_data["source_unit_locator"], sections)
        if case_data["currency"] != "EUR":
            return False
        for case in _all_cases(data):
            object_data(case, {"case_id", "components", "totals", "computed"})
            nonempty(case["case_id"], 80)
            components = object_data(case["components"], set(GROUPS))
            for value in components.values():
                for c in items(value, 16):
                    object_data(c, {"component_id", "source_value", "amount"})
                    nonempty(c["component_id"], 80)
                    if source_to_eur(c["source_value"], case_data["source_scale"], explicit_label=label) != c["amount"]:
                        return False
            case_values(case)
            for value in object_data(case["computed"], {"FRNG", "BFR", "TN"}).values():
                decimal_value(value)
        return True
    if index == 8:
        for case in _all_cases(data):
            components = object_data(case["components"], set(GROUPS))
            values = case_values(case)
            ids: list[object] = []
            for group in GROUPS:
                parts = items(components[group], 16)
                if not parts or sum((decimal_value(c["amount"]) for c in parts), Decimal(0)) != values[group]:
                    return False
                ids.extend(c["component_id"] for c in parts)
            if len(ids) != len(set(ids)):
                return False
            if values["stable_uses"] + values["current_assets"] + values["cash_assets"] != values["stable_resources"] + values["current_liabilities"] + values["cash_liabilities"]:
                return False
        return True
    if index in {9, 10, 11}:
        for case in _all_cases(data):
            v = case_values(case)
            computed = object_data(case["computed"], {"FRNG", "BFR", "TN"})
            frng = v["stable_resources"] - v["stable_uses"]
            bfr = v["current_assets"] - v["current_liabilities"]
            expected = {9: frng, 10: bfr, 11: frng - bfr}[index]
            metric = {9: "FRNG", 10: "BFR", 11: "TN"}[index]
            if decimal_value(computed[metric]) != expected:
                return False
            if index == 11 and expected != v["cash_assets"] - v["cash_liabilities"]:
                return False
        return True
    if index == 12:
        context = object_data(data["pedagogical_context"])
        dossiers = items(object_data(data["marking"])["dossiers"], 3)
        return (context.get("level") in {"BTS_CG_YEAR_1", "BTS_CG_YEAR_2"} and context.get("resource_type") == "ASSESSMENT"
                and context.get("duration_minutes") == 60 and context.get("total_points") == "20"
                and context.get("language") == "fr" and fingerprint(context) == data["context_sha256"]
                and tuple(d["dossier_id"] for d in dossiers) == DOSSIERS
                and all(type(d["duration_minutes"]) is int and 0 < d["duration_minutes"] <= 60 for d in dossiers)
                and sum(int(str(d["duration_minutes"])) for d in dossiers) == 60)
    if index == 13:
        actual = items(data["references"], 3)
        return (bool(actual) and actual == tuple(dict(r) for r in references)
                and all(r["provenance_label"] == "SUPPORT_SYNTHETIQUE_R2 — aucune source officielle attestée" for r in actual))
    if index == 14:
        lineage = object_data(data["lineage"], {"operation_ref", "command_id", "source_capability",
            "parent_version_ref", "parent_bundle_sha256", "instruction_sha256",
            "changed_locators", "dependency_changes"})
        if lineage["dependency_changes"] not in ([], ()):
            return False
        if parent is None:
            return lineage["parent_version_ref"] is None and lineage["parent_bundle_sha256"] is None
        if (lineage["parent_version_ref"] != parent.version_ref
                or lineage["parent_bundle_sha256"] != parent.sha256
                or data["production_ref"] != parent.production_ref or data["version_ref"] == parent.version_ref):
            return False
        before = parent.data
        if tuple(items(object_data(before["subject"])["sections"]))[:-1] != tuple(items(sections))[:-1]:
            return False
        if any(before[k] != data[k] for k in ("pedagogical_context", "context_sha256", "references")):
            return False
        before_case, after_case = object_data(before["case_data"]), object_data(data["case_data"])
        if any(before_case[k] != after_case[k] for k in ("currency", "source_scale", "source_unit_locator", "base_case")):
            return False
        def non_d3(d: Mapping[str, object]) -> tuple[object, ...]:
            qs = tuple(q for q in _questions(d) if q["dossier_id"] != "DOSSIER_3")
            ids = {q["question_id"] for q in qs}
            ans = tuple(a for a in items(object_data(d["correction"])["answers"]) if a["question_id"] in ids)
            marks = items(object_data(d["marking"])["dossiers"])[:2]
            return qs, ans, marks
        return non_d3(before) == non_d3(data)
    if index == 15:
        cases = {c["case_id"]: c for c in _all_cases(data)}
        if len(cases) != len(_all_cases(data)):
            return False
        if sum(len(items(a["calculations"], 60)) for a in answers) > 60:
            return False
        expected_by_question = {q["question_id"]: q["calculation_refs"] for q in questions}
        for answer in answers:
            observed_refs = []
            for calculation in items(answer["calculations"], 60):
                object_data(calculation, {"case_id", "metric", "value", "locator", "expression"})
                selected_case = cases.get(calculation["case_id"])
                if selected_case is None or object_data(selected_case["computed"]).get(str(calculation["metric"])) != calculation["value"]:
                    return False
                if evaluate_expression(calculation["expression"], selected_case) != decimal_value(calculation["value"]):
                    return False
                observed_refs.append(str(calculation["case_id"]) + ":" + str(calculation["metric"]))
                decimal_value(calculation["value"])
                text = locate(calculation["locator"], [{"section_id": answer["question_id"],
                                                        "text": answer["expected_answer"]}])
                if text != calculation["value"]:
                    return False
            if sorted(observed_refs) != sorted(cast(tuple[str, ...], expected_by_question[answer["question_id"]])):
                return False
        expected_refs = {str(c["case_id"]) + ":" + str(metric) for c in _all_cases(data)
                         for metric in object_data(c["computed"])}
        for q in questions:
            refs = q["calculation_refs"]
            if not isinstance(refs, (tuple, list)) or any(r not in expected_refs for r in refs):
                return False
        return True
    if index == 16:
        # PASS means only the formalized answers were covered, not pedagogical approval.
        # Free answer prose is visible as WARNING even if a provider omits a limitation.
        for answer in answers:
            text = nonempty(answer["expected_answer"])
            spans = [object_data(c["locator"]) for c in items(answer["calculations"], 60)]
            for span in sorted(spans, key=lambda s: int(str(s["start"])), reverse=True):
                text = text[:int(str(span["start"]))] + text[int(str(span["end"])):]
            if re.sub(r"[\s,;:=().+\-]|EUR|€", "", text):
                return False
        return "UNFORMALIZED_CONTENT" not in cast(tuple[str, ...], data["limitations"])
    return True


def evaluate_checks(bundle: AssessmentBundle | None, *, parent: AssessmentBundle | None,
                    references: tuple[Mapping[str, object], ...]) -> tuple[AssessmentCheck, ...]:
    result = []
    for index in range(1, 17):
        status, reason = "PASS", "CHECK_SATISFIED"
        try:
            if bundle is None:
                status, reason = "FAIL", "ASSESSMENT_BUNDLE_MISSING"
            elif not check_rule(index, bundle.data, parent=parent, references=references):
                status, reason = ("WARNING", "SEMANTIC_HUMAN_REVIEW_REQUIRED") if index == 16 else ("FAIL", f"A{index:02}_REJECTED")
        except (ValueError, TypeError, KeyError, InvalidOperation, OverflowError):
            status, reason = "FAIL", f"A{index:02}_INVALID_OR_NON_EVALUABLE"
        result.append(AssessmentCheck(f"A{index:02}", status, reason))
    return tuple(result)
