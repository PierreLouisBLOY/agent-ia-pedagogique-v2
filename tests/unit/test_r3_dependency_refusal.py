"""E08 is a precise local domain refusal, never a guessed provider status."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from tests.support import r3_fakes
from tests.support.r3_d3_fixtures import synthetic_dependency_failure

harness = cast(Callable[[], tuple[Any, Any, Any, Any]], r3_fakes.harness)
run = cast(Callable[..., tuple[Any, Any]], r3_fakes.run)
command = cast(Callable[..., Any], r3_fakes.command)

CODE = "DEPENDENCY_CHANGE_REQUIRES_APPROVAL"


@pytest.mark.parametrize("kind", ["duration", "points", "dossier"])
def test_real_domain_dependency_refusal_keeps_parent(kind: str) -> None:
    conv, r3, jobs, prod = harness()
    run(conv, r3, "assessment-preparations", prod)
    before = r3.service.assessment(prod.production_ref, prod.version_ref)
    jobs.dispatch = lambda request: synthetic_dependency_failure(kind)
    receipt, _ = run(conv, r3, "modifications", prod)
    assert receipt["state"] == "FAILED_OUTPUT" and receipt["error_code"] == CODE
    trace = r3.service.diagnostic(receipt["operation_ref"])
    assert trace["failure_stage"] == "BUNDLE_ASSEMBLY"
    after = r3.service.assessment(prod.production_ref, prod.version_ref)
    for key in ("bundle", "versions", "current_candidate"):
        assert after[key] == before[key]


@pytest.mark.parametrize(
    "kind", ["runtime", "subclass", "extra_arg", "wrong_text", "mapping", "prepare", "review"]
)
def test_homonyms_and_wrong_stages_remain_generic(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from backend.modules.pedagogical_design.application.commands.revise_assessment import (
        ReviseAssessmentCommand,
    )

    conv, r3, jobs, prod = harness()
    run(conv, r3, "assessment-preparations", prod)

    class Derived(ValueError):
        pass

    def fail(self: object, *args: Any, **kwargs: Any) -> Any:
        observer = kwargs.get("observe")
        if observer:
            observer("PARSED_OUTPUT_MAPPING" if kind == "mapping" else "BUNDLE_ASSEMBLY")
        if kind == "runtime":
            raise RuntimeError(CODE)
        if kind == "subclass":
            raise Derived(CODE)
        if kind == "extra_arg":
            raise ValueError(CODE, "second")
        if kind == "wrong_text":
            raise ValueError(CODE + " ")
        raise ValueError(CODE)

    monkeypatch.setattr(ReviseAssessmentCommand, "execute", fail)
    if kind in {"prepare", "review"}:
        # Recreate an independent synthetic session for PREPARE / REVIEW.
        if kind == "prepare":
            conv, r3, jobs, prod = harness()
        else:
            jobs.dispatch = lambda request: {"invalid": True}
    receipt, _ = run(
        conv,
        r3,
        {"prepare": "assessment-preparations", "review": "reviews"}.get(kind, "modifications"),
        prod,
    )
    assert receipt["state"] == "FAILED_OUTPUT"
    assert receipt["error_code"] != CODE


def test_failed_receipt_remains_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    conv, r3, jobs, prod = harness()
    run(conv, r3, "assessment-preparations", prod)
    jobs.dispatch = lambda request: synthetic_dependency_failure("duration")
    receipt = r3.service.execute(command(conv, r3, "modifications", prod))

    def fail(*args: object, **kwargs: object) -> None:
        raise ValueError("REVISION_CONFLICT")

    monkeypatch.setattr(conv.store, "r3_complete", fail)
    with pytest.raises(ValueError):
        r3.service.poll()
    trace = r3.service.diagnostic(receipt["operation_ref"])
    assert trace["receipt_state"] == "UNKNOWN"


def test_ui_uses_only_closed_terminal_code() -> None:
    source = (Path(__file__).resolve().parents[2] / "frontend/app.js").read_text("utf-8")
    assert 'result.error_code === "DEPENDENCY_CHANGE_REQUIRES_APPROVAL"' in source
    assert 'result.state === "FAILED_OUTPUT"' in source
