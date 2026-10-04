"""Public official tariff retrieval, without credential or model invocation."""
import hashlib
import html
import json
import re
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser

URL = "https://developers.openai.com/api/docs/models/gpt-5.6-terra"


class Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def fetch_tariff() -> tuple[dict[str, str | int | bool], bytes]:
    with urllib.request.urlopen(URL, timeout=30) as response:
        if response.url.rstrip("/") != URL:
            raise ValueError("TARIFF_REDIRECT_REFUSED")
        raw = response.read(3_000_000)
    parser = Text()
    parser.feed(raw.decode("utf-8"))
    compact = re.sub(r"\s+", "", html.unescape(" ".join(parser.parts)))
    # Ordered model pricing table, including cached input; unrelated comparison tables cannot match.
    rates = re.findall(r"TexttokensPer1MtokensInput\$([0-9.]+)Cachedinput\$([0-9.]+)Output\$([0-9.]+)", compact)
    if rates != [("2.00", "0.20", "12.00")]:
        raise ValueError("OFFICIAL_TARIFF_CHANGED_OR_UNPARSABLE")
    if "Cachewritesarebilledat1.25xtheuncachedinputtokenrate." not in compact:
        raise ValueError("CACHE_WRITE_TARIFF_UNESTABLISHED")
    return {"model": "gpt-5.6-terra", "source_url": URL,
        "retrieved_utc": datetime.now(UTC).isoformat(), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "input_usd_per_million": "2.00", "cached_input_usd_per_million": "0.20",
        "output_usd_per_million": "12.00", "cache_write_input_factor": "1.25",
        "conservative_input_usd_per_million": "2.50", "short_context": True,
        "provider_calls": 0}, raw


if __name__ == "__main__":
    from pathlib import Path
    root = Path(__file__).resolve().parent / "MEGA_TOKENIZER_ACQUISITION_20261004"
    tariff, raw = fetch_tariff()
    (root / "official-terra-model-page.html").write_bytes(raw)
    (root / "03_CURRENT_OFFICIAL_TARIFF.json").write_text(json.dumps(tariff, indent=2) + "\n", "utf-8")
    print(json.dumps(tariff))
