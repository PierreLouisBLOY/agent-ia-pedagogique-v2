"""Declared synthetic permission/tokenizer/transport; zero provider calls."""

import pytest

from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_product import P0ProductGenerationAdapter
from tests.unit.test_p0_product_permission import configured_product, preview


def test_destination_is_closed_bound_permission_projection_without_dispatch(tmp_path):
    settings, _, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    shown = preview(adapter, prepared, dispatch, receipts)
    assert shown["transfer_destination"] == {
        "provider": settings["permission"]["provider"], "model": settings["permission"]["model"],
        "endpoint": settings["permission"]["endpoint"],
        "permission_sha256": sha(canonical(settings["permission"]))}
    assert shown["transfer_destination"]["permission_sha256"] == shown["preview"]["permission_sha256"]
    assert shown["preview_sha256"] == sha(canonical(shown["preview"]))
    assert "transfer_destination" not in shown["preview"]
    assert resolver.calls == transport.calls == 0 and adapter.ledger.slots() == []


@pytest.mark.parametrize("key,value", [("provider", "OTHER"), ("model", "OTHER"),
    ("endpoint", "https://example.org/v1/responses")])
def test_mutated_permission_refuses_before_destination_or_effect(tmp_path, key, value):
    settings, _, prepared, dispatch, receipts, _, _, resolver, transport = configured_product(tmp_path)
    adapter = P0ProductGenerationAdapter(**settings)
    adapter.permission[key] = value
    with pytest.raises(ValueError):
        preview(adapter, prepared, dispatch, receipts)
    assert resolver.calls == transport.calls == 0 and adapter.ledger.slots() == []
