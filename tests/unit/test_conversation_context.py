from unicodedata import normalize

import pytest

from backend.modules.pedagogical_context.application.services.conversation_context import (
    ConversationContextService,
)
from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
    ContextRejected,
    text_value,
    validated_values,
)
from tests.support.conversation_fakes import CONTEXT, PILOT


def test_french_pilot_and_followup_do_not_guess_year():
    service = ConversationContextService()
    initial = service.propose(text=PILOT, current={}, patch={})
    assert initial.values["duration_minutes"] == 60
    assert initial.values["total_points"] == "20"
    assert initial.values["resource_type"] == "ASSESSMENT"
    assert "level" in initial.missing_fields
    followup = service.propose(text="deuxième année ; difficulté standard", current=initial.values,
                              patch={}, previous_text=PILOT)
    assert followup.values["level"] == "BTS_CG_YEAR_2"
    assert followup.values["difficulty"] == "STANDARD"
    assert "objectives" in followup.missing_fields


def test_digest_is_normalized_and_order_independent():
    first = ConfirmedConversationContext(CONTEXT)
    second = ConfirmedConversationContext(dict(reversed(list(CONTEXT.items()))))
    assert first.sha256 == second.sha256
    assert text_value(normalize("NFD", "évaluation\r\n"), 120) == "évaluation"
    with pytest.raises(TypeError):
        first.values["level"] = "FIRST_STMG"


@pytest.mark.parametrize("patch", [
    {"duration_minutes": True}, {"duration_minutes": 0}, {"duration_minutes": 241},
    {"total_points": "NaN"}, {"total_points": 20.0}, {"total_points": "20.00"},
    {"discipline": "x" * 121}, {"provider": "injected"}, {"topics": ["x", "x"]},
    {"level": "BTS_CG"}, {"language": "en"}, {"resource_type": "LESSON"},
])
def test_invalid_context_is_rejected(patch):
    with pytest.raises(ContextRejected):
        validated_values(patch)


@pytest.mark.parametrize("text", ["\x00", "\x01", "\x85", "\u202e", "\ud800", "x" * 4001])
def test_reject_controls_surrogates_and_oversize(text):
    with pytest.raises(ContextRejected):
        text_value(text, 4000, 12288)


def test_contradictions_require_explicit_patch():
    service = ConversationContextService()
    update = service.propose(text="BTS CG première et deuxième année, durée 45 min", current=CONTEXT,
                             patch={})
    assert {"level", "duration_minutes"} <= set(update.conflicts)
    resolved = service.propose(text="45 min", current=CONTEXT, patch={"duration_minutes": 45})
    assert "duration_minutes" not in resolved.conflicts
