from __future__ import annotations

from collections.abc import Mapping

from backend.shared_kernel._safe_data import freeze_safe_mapping

_PRIVATE_AGENT_KEYS = frozenset(
    {
        "chain_of_thought",
        "chainOfThought",
        "private_reasoning",
        "privateReasoning",
        "system_prompt",
        "systemPrompt",
        "prompt_system",
    }
)


def freeze_agent_safe_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Freeze structured data after rejecting private agent reasoning keys."""
    _reject_private_agent_keys(value)
    return freeze_safe_mapping(value)


def _reject_private_agent_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _PRIVATE_AGENT_KEYS:
                raise ValueError(f"forbidden agent runtime data key: {key}")
            _reject_private_agent_keys(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_agent_keys(item)
