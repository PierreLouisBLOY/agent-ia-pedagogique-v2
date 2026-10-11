"""R2 counterexamples through current Application; all transports are declared doubles."""

from dataclasses import replace
from secrets import token_hex

import pytest

from backend.adapters.outbound.persistence.saved_production import LocalSavedProductionStore
from backend.adapters.outbound.review.p0_review import P0ReviewAdapter
from backend.agent_runtime.agents.review.review_security_model import ReviewMetadataPolicyVersion
from backend.modules.pedagogical_context.contracts.dto.p0_context import P0Context
from backend.modules.work_orchestration.application.services.p0_agentic import (
    effort_plan,
    quality_status,
)
from backend.modules.work_orchestration.application.services.saved_production import (
    SavedProductionService,
)
from tests.integration.test_p0_creation_http import context
from tests.support.p0_generation_double import P0GenerationDouble
from tests.support.r3_synthetic import bundle
from tests.unit.test_assessment_deterministic_validation import validate
from tests.unit.test_p0_agentic_routing import TechnicalCritic, candidate, identity
from tests.unit.test_p0_creation_contract import service

CASES = (
    (
        "TVA",
        "Déterminer la TVA à décaisser à partir de 10 000 euros HT de ventes au taux de 20 % et 800 euros de taxe déductible.",
    ),
    (
        "VAN",
        "Déterminer la valeur actuelle nette avec un investissement initial de 1000 euros et un flux de 1200 euros dans un an actualisé à 5 %.",
    ),
    (
        "Rentabilité",
        "Trouver le résultat net à partir du chiffre d’affaires et des charges donnés.",
    ),
    (
        "Fiscalité",
        "Quel montant de taxe reste à payer avec des ventes HT de 10 000 euros, un taux de 20 % et 800 euros déductibles ?",
    ),
    ("Investissement", "Estimer la valeur actualisée nette des flux et de l’investissement."),
    ("Performance", "Déduire le bénéfice net des recettes et des dépenses fournies."),
)


@pytest.mark.parametrize("topic,objective", CASES)
def test_requested_operations_require_independent_control(topic, objective):
    data = context("BTS_CG_YEAR_2", "EXERCISE", None)
    data.update(topics=[topic], objectives=[objective])
    plan = effort_plan(P0Context(data))
    assert plan["quantitative_review_required"] is True
    assert "INDEPENDENT_CALCULATION_ORACLE_REQUIRED" in plan["validations"]
    status = quality_status(plan)
    assert status["calculations"] == "ECHEC"
    assert status["calculation_reason"] == "INDEPENDENT_ORACLE_NOT_EXECUTED"


@pytest.mark.parametrize(
    "objective",
    [
        "Expliquer les rôles d’une organisation.",
        "Identifier les acteurs d’une organisation fondée en 2024.",
    ],
)
def test_explicit_qualitative_operation_can_justify_non_applicability(objective):
    data = context("FIRST_STMG", "COURSE", None)
    data.update(topics=["Organisation"], objectives=[objective])
    assert quality_status(effort_plan(P0Context(data)))["calculations"] == "NON_APPLICABLE"


def test_absence_of_signal_alone_does_not_prove_non_applicability():
    assert quality_status({"quantitative_review_required": False})["calculations"] == "A_DETERMINER"


class NumericOutput(P0GenerationDouble):
    def generate(self, *, request):
        output = dict(super().generate(request=request))
        output["corrections"] = [
            {
                "question_id": "Q01",
                "expected_answer": "1 200 euros",
                "rationale": "2 000 - 800 = 1 200 euros.",
            }
        ]
        return output


def test_generated_and_revised_numerical_work_is_rechecked_through_service():
    for double in (P0GenerationDouble(), NumericOutput()):
        app = service(double)
        data = context("BTS_CG_YEAR_2", "EXERCISE", None)
        data.update(topics=["Organisation"], objectives=["Expliquer les rôles des acteurs."])
        ready = app.execute(
            "prepare", {"command_id": token_hex(16), "context": data, "reference": {}}
        )
        output = app.execute(
            "generate",
            {
                "command_id": token_hex(16),
                "preparation_ref": ready["preparation_ref"],
                "preparation_sha256": ready["preparation_sha256"],
            },
        )
        assert ready["agentic"]["quality"]["calculations"] == "NON_APPLICABLE"
        view = output["view"]
        if isinstance(double, NumericOutput):
            assert output["agentic"]["quality"]["calculations"] == "ECHEC"
            assert output["agentic"]["plan"]["quantitative_review_required"] is True
        child = app.execute(
            "revise",
            {
                "command_id": token_hex(16),
                **identity(view),
                "edits": {
                    "corrections": [
                        {
                            "question_id": "Q01",
                            "expected_answer": "1 200 euros",
                            "rationale": "2 000 - 800 = 1 200 euros.",
                        }
                    ]
                },
            },
        )
        assert child["quality"]["calculations"] == "ECHEC"
        assert app.plans[child["view"]["version_ref"]]["quantitative_review_required"] is True
        assert app.plans[view["version_ref"]]["quantitative_review_required"] is isinstance(double, NumericOutput)
        checked = app.execute("validate", {"command_id": token_hex(16), **identity(child["view"])})
        assert checked["quality"]["calculations"] == "ECHEC"
        denied = app.execute("review", {"command_id": token_hex(16), **identity(child["view"])})
        assert denied["state"] == "AUTHORIZATION_REQUIRED"
        assert denied["quality"]["calculations"] == "ECHEC"
        assert len(double.requests) == 1


@pytest.mark.parametrize("production", [
    {"numeric_data": [{"quantity": 12, "unit_price": 5}]},
    {"corrections": [{"expected_answer": 60}]},
    {"calculation_steps": [{"expression": "12 * 5"}]},
])
def test_structured_quantities_and_steps_override_a_qualitative_plan(production):
    data = context("FIRST_STMG", "COURSE", None)
    data.update(topics=["Organisation"], objectives=["Expliquer les rôles des acteurs."])
    plan = effort_plan(P0Context(data), production=production)
    assert plan["quantitative_review_required"] is True
    assert quality_status(plan, production=production)["calculations"] == "ECHEC"


def test_executed_existing_oracle_only_attests_its_exact_bundle():
    value = bundle("EUR")
    control = validate(value)
    assert control.overall_status == "PASS"
    plan = {"quantitative_review_required": True}
    result = quality_status(plan, production=value.data, calculation_control=control)
    assert result["calculations"] == "CALCULS_VERIFIES"
    changed = value.mutable_copy()
    changed["limitations"].append("Changed version content")
    with pytest.raises(ValueError, match="CALCULATION_CONTROL_BINDING"):
        quality_status(plan, production=changed, calculation_control=control)


class DiagnosticCritic(TechnicalCritic):
    def __init__(self, diagnostics):
        super().__init__()
        self.diagnostics = diagnostics

    def review(self, *, request):
        result = super().review(request=request)
        return replace(
            result,
            structured_payload={
                **result.structured_payload,
                "overall_assessment": "acceptable",
                "correction_required": False,
            },
            uncertainties=tuple(self.diagnostics),
        )


@pytest.mark.parametrize(
    "successor,diagnostics",
    [
        (False, []),
        (True, []),
        (
            True,
            [
                {
                    "code": "NO_AUTHORITATIVE_ORACLE",
                    "message": "No authoritative oracle is provided.",
                }
            ],
        ),
    ],
)
def test_review_crosses_real_successor_and_service_then_reopens_exactly(
    tmp_path, successor, diagnostics
):
    app = service(P0GenerationDouble())
    critic = DiagnosticCritic(diagnostics)
    app.review = P0ReviewAdapter(
        critic,
        authorize=lambda request: True,
        metadata_policy_version=ReviewMetadataPolicyVersion.NEGATIVE_AUTHORITY_DIAGNOSTICS_V1
        if successor
        else ReviewMetadataPolicyVersion.HISTORICAL,
    )
    view, _ = candidate(app)
    result = app.execute("review", {"command_id": token_hex(16), **identity(view)})
    report = result["report"]
    assert report["contract_id"] == ("P0-REVIEW-1.1" if successor else "P0-REVIEW-1.0")
    assert report.get("uncertainties", []) == diagnostics
    assert ("uncertainties" in report) is successor
    assert result["quality"]["review"] == ("RESERVE" if diagnostics else "REVUE_OK")
    assert result["quality"]["calculations"] != "CALCULS_VERIFIES"
    assert report["promotion"] == "NOT_PERFORMED" and len(critic.requests) == 1
    saved = app.saved_source(view["production_ref"], view["version_ref"])
    root = tmp_path / "synthetic-store"
    writer = SavedProductionService(LocalSavedProductionStore(root, create=True))
    assert writer.save(saved)["saved"] is True
    reader = SavedProductionService(LocalSavedProductionStore(root))
    reopened = reader.open(saved.production_ref, saved.version_ref)
    assert reopened["record_sha256"] == saved.sha256
    assert reopened["record"]["reviews"] == [report]
    assert reopened["active_authority"] == "NONE_RESTORED"


@pytest.mark.parametrize(
    "fault", ["unknown", "type", "diagnostic_key", "contract", "legacy_extra", "version", "hash"]
)
def test_closed_review_contract_mutations_refuse_without_replay(fault):
    app = service(P0GenerationDouble())
    critic = DiagnosticCritic([])
    adapter = P0ReviewAdapter(
        critic,
        authorize=lambda request: True,
        metadata_policy_version=ReviewMetadataPolicyVersion.NEGATIVE_AUTHORITY_DIAGNOSTICS_V1,
    )

    class MutatedPort:
        def authorize(self, *, request):
            return adapter.authorize(request=request)

        def review(self, *, request):
            output = dict(adapter.review(request=request))
            if fault == "unknown":
                output["unapproved"] = True
            elif fault == "type":
                output["uncertainties"] = "not a collection"
            elif fault == "diagnostic_key":
                output["uncertainties"] = [{"code": "RESERVE", "unapproved": True}]
            elif fault == "contract":
                output["contract_id"] = "P0-REVIEW-99.0"
            elif fault == "legacy_extra":
                output["contract_id"] = "P0-REVIEW-1.0"
            elif fault == "version":
                output["version_ref"] = "ver:" + "0" * 32
            elif fault == "hash":
                output["bundle_sha256"] = "0" * 64
            return output

    app.review = MutatedPort()
    view, _ = candidate(app)
    command = {"command_id": token_hex(16), **identity(view)}
    with pytest.raises(ValueError):
        app.execute("review", command)
    assert not app.reports and len(critic.requests) == 1
    assert app.execute("review", command)["state"] == "REFUSED"
    assert len(critic.requests) == 1
