"""Entirely invented fixtures. No old output, user file, seed or credential access."""
from copy import deepcopy
from decimal import Decimal

from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.application.commands.revise_assessment import (
    ReviseAssessmentCommand,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from backend.modules.pedagogical_design.contracts.dto.assessment_revision import (
    PREPARE,
    AssessmentRevisionRequest,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraft,
    ConversationDraftRequest,
)
from backend.modules.work_orchestration.contracts.dto.production_read_view import ProductionReadView
from tests.support.conversation_fakes import CONTEXT, sample_draft

PROD = "prod:" + "1" * 32
V1 = "ver:" + "1" * 32
V2 = "ver:" + "2" * 32
CONV = "conv:" + "1" * 32


def locator(section, text, quote):
    start = text.index(quote)
    return {"section_id": section, "start": start, "end": start + len(quote), "exact_text": quote}


def source_case(scale="EUR", scenario=False):
    numbers = {"stable_resources": (220000, 80000), "stable_uses": (200000,),
               "current_assets": (45000, 95000 if scenario else 75000),
               "current_liabilities": (55000 if scenario else 50000, 30000),
               "cash_assets": (55000 if scenario else 70000,), "cash_liabilities": (10000,)}
    factor = Decimal(1000 if scale == "kEUR" else 1)
    components = {key: [{"component_id": key + str(i),
        "source_value": format(Decimal(v) / factor, ".2f"), "amount": format(Decimal(v), ".2f")}
        for i, v in enumerate(values)] for key, values in numbers.items()}
    return {"case_id": "shock" if scenario else "base", "components": components,
            "totals": {k: format(Decimal(sum(v)), ".2f") for k, v in numbers.items()},
            "computed": {"FRNG": "100000.00", "BFR": "55000.00" if scenario else "40000.00",
                         "TN": "45000.00" if scenario else "60000.00"}}


def subject(scale="EUR"):
    label = "k€" if scale == "kEUR" else "EUR"
    texts = [("CONSIGNES", "Contrôle BTS CG synthétique : 60 minutes, total vingt points."),
             ("CONTEXTE_ET_ANNEXES", "Cas entièrement synthétique. Montants en " + label + "."),
             ("DOSSIER_1", "Dossier 1 : calculer le FRNG et expliquer les emplois stables."),
             ("DOSSIER_2", "Dossier 2 : calculer le BFR et interpréter les créances."),
             ("DOSSIER_3", "Dossier 3 : calculer la trésorerie nette du cas de base.")]
    return {"content": "\n\n".join(t for _, t in texts),
            "sections": [{"section_id": code, "text": text} for code, text in texts]}


def question(qid, dossier, text, case, metric):
    return {"question_id": qid, "dossier_id": dossier, "locator": locator(dossier, text, text),
            "instruction": text, "expected_skill": "Calcul et interprétation argumentée",
            "calculation_refs": [case + ":" + metric]}


def answer(qid, case, metric, amount):
    text = amount + " EUR"
    left, right = {"FRNG": ("totals.stable_resources", "totals.stable_uses"),
                   "BFR": ("totals.current_assets", "totals.current_liabilities"),
                   "TN": ("computed.FRNG", "computed.BFR")}[metric]
    return {"question_id": qid, "expected_answer": text,
            "rationale": "Appliquer la relation financière aux données du scénario.",
            "calculations": [{"case_id": case, "metric": metric, "value": amount,
                              "expression": {"op": "SUB", "operands": [{"ref": left}, {"ref": right}]},
                              "locator": locator(qid, text, amount)}]}


def mark(qid, points):
    return {"question_id": qid, "points": points, "criteria": [
        {"criterion_id": qid + ".calculation", "description": "Calcul justifié", "points": points}]}


def supplements(scale="EUR"):
    subj = subject(scale)
    qs, ans, dossiers = [], [], []
    for i, (metric, amount, points) in enumerate((
            ("FRNG", "100000.00", "6.00"), ("BFR", "40000.00", "6.00"),
            ("TN", "60000.00", "8.00")), 1):
        qid, dossier = "q" + str(i), "DOSSIER_" + str(i)
        qs.append(question(qid, dossier, subj["sections"][i+1]["text"], "base", metric))
        ans.append(answer(qid, "base", metric, amount))
        dossiers.append({"dossier_id": dossier, "duration_minutes": 20, "questions": [mark(qid, points)]})
    unit_text = subj["sections"][1]["text"]
    return {"questions": qs, "correction": {"production_ref": PROD, "version_ref": V1, "answers": ans},
            "marking": {"production_ref": PROD, "version_ref": V1, "total_points": "20.00", "dossiers": dossiers},
            "case_data": {"currency": "EUR", "source_scale": scale,
                "source_unit_locator": locator("CONTEXTE_ET_ANNEXES", unit_text, "k€" if scale == "kEUR" else "EUR"),
                "base_case": source_case(scale), "scenarios": []},
            "limitations": ["CANDIDATE — NON VALIDÉE"]}


def lineage(parent=None):
    return {"operation_ref": "op:" + "1" * 32, "command_id": "00000000-0000-0000-0000-000000000001",
            "source_capability": "CAP-G02", "parent_version_ref": parent.version_ref if parent else None,
            "parent_bundle_sha256": parent.sha256 if parent else None,
            "instruction_sha256": fingerprint({"instruction": "synthetic"}),
            "changed_locators": ["DOSSIER_3"] if parent else [], "dependency_changes": []}


def production(scale="EUR", conversation_id=CONV):
    context = ConfirmedConversationContext(deepcopy(CONTEXT))
    req = ConversationDraftRequest("req:" + "1" * 32, conversation_id, "gen:" + "1" * 32,
                                   "Contrôle synthétique BTS CG bilan fonctionnel.", context)
    subj = subject(scale)
    draft = ConversationDraft(PROD, subj["content"], tuple(subj["sections"]),
        sample_draft().references, {"source_run_id": "r3-synthetic", "source_step_id": "r3-test",
                                   "evidence_set_ref": "r3-invented"}, ("CANDIDATE — NON VALIDÉE",))
    return ProductionReadView.from_draft(draft, req, V1)


def bundle(scale="EUR"):
    prod = production(scale)
    request = AssessmentRevisionRequest(PREPARE, PROD, V1, subject(scale),
                                        prod.data["pedagogical_context"], tuple(prod.data["references"]))
    return ReviseAssessmentCommand().execute(request, supplements(scale), version_ref=V1, lineage=lineage())


def harden_delta(scale="EUR"):
    text = ("Dossier 3 : créances +20000 EUR, fournisseurs +5000 EUR. "
            "Calculer le nouveau BFR, la TN et justifier la variation de trésorerie.")
    return {"dossier_3": {"section_id": "DOSSIER_3", "text": text},
            "questions_d3": [question("q3a", "DOSSIER_3", text, "shock", "TN"),
                             question("q3b", "DOSSIER_3", text, "shock", "BFR")],
            "answers_d3": [answer("q3a", "shock", "TN", "45000.00"), answer("q3b", "shock", "BFR", "55000.00")],
            "marking_d3": {"dossier_id": "DOSSIER_3", "duration_minutes": 20,
                           "questions": [mark("q3a", "6.00"), mark("q3b", "2.00")]},
            "scenarios_d3": [source_case(scale, True)], "limitations": ["CANDIDATE — NON VALIDÉE"]}
