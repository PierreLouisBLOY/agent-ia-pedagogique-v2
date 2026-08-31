"""Single offline pricing source for the proposed V4 calibration matrix."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

SNAPSHOT_PATH = Path(__file__).with_name("pricing_snapshot_v4.json")
EXPECTED_PRICING_SNAPSHOT_SHA256 = (
    "31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8"
)


@dataclass(frozen=True, slots=True)
class ModelPriceQuote:
    provider: str
    model: str
    input_usd_per_million_tokens: Decimal
    cached_input_usd_per_million_tokens: Decimal
    output_usd_per_million_tokens: Decimal
    unit: str
    source_url: str
    verified_on: str


def pricing_snapshot_sha256() -> str:
    digest = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
    if digest != EXPECTED_PRICING_SNAPSHOT_SHA256:
        raise RuntimeError("PRICING_SNAPSHOT_SHA256_MISMATCH")
    return digest


def pricing_snapshot_payload() -> dict[str, object]:
    pricing_snapshot_sha256()
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    if type(payload) is not dict:
        raise RuntimeError("PRICING_SNAPSHOT_INVALID")
    return cast(dict[str, object], payload)


def _load_quotes() -> tuple[ModelPriceQuote, ...]:
    payload = pricing_snapshot_payload()
    snapshot_id = payload.get("snapshot_id")
    verified_on = payload.get("verified_on")
    raw_models = payload.get("models")
    if type(snapshot_id) is not str or type(verified_on) is not str:
        raise RuntimeError("PRICING_SNAPSHOT_INVALID")
    if type(raw_models) is not list:
        raise RuntimeError("PRICING_SNAPSHOT_INVALID")
    quotes: list[ModelPriceQuote] = []
    for raw in raw_models:
        if type(raw) is not dict:
            raise RuntimeError("PRICING_SNAPSHOT_INVALID")
        item = cast(dict[str, object], raw)
        try:
            quote = ModelPriceQuote(
                provider=cast(str, item["provider"]),
                model=cast(str, item["model"]),
                input_usd_per_million_tokens=Decimal(
                    cast(str, item["input_usd_per_million_tokens"])
                ),
                cached_input_usd_per_million_tokens=Decimal(
                    cast(str, item["cached_input_usd_per_million_tokens"])
                ),
                output_usd_per_million_tokens=Decimal(
                    cast(str, item["output_usd_per_million_tokens"])
                ),
                unit="USD per 1M tokens",
                source_url=cast(str, item["source"]),
                verified_on=verified_on,
            )
        except (KeyError, ArithmeticError, TypeError):
            raise RuntimeError("PRICING_SNAPSHOT_INVALID") from None
        if not all(
            type(value) is str and value
            for value in (quote.provider, quote.model, quote.source_url)
        ):
            raise RuntimeError("PRICING_SNAPSHOT_INVALID")
        quotes.append(quote)
    if len({quote.model for quote in quotes}) != len(quotes):
        raise RuntimeError("PRICING_SNAPSHOT_INVALID")
    return tuple(quotes)


PRICING_SNAPSHOT_ID = cast(str, pricing_snapshot_payload()["snapshot_id"])
MODEL_PRICE_QUOTES = _load_quotes()
MODEL_PRICE_BY_NAME = {quote.model: quote for quote in MODEL_PRICE_QUOTES}
