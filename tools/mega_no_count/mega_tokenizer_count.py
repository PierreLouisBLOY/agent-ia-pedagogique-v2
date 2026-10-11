"""Offline model resolver and text counter using the isolated official tokenizer."""
import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import TypedDict
from unittest.mock import patch


class Field(TypedDict):
    path: str
    tokens: int


def main() -> None:
    root = Path(__file__).resolve().parent / "MEGA_TOKENIZER_ACQUISITION_20261004"
    manifest = json.loads((root / "02_HELPER_INPUT_MANIFEST.json").read_text())
    for distribution in manifest["distributions"]:
        assert importlib.metadata.version(distribution["package"]) == distribution["version"]
    encoding = manifest["encoding"]
    assert hashlib.sha256((root / "o200k_base.tiktoken").read_bytes()).hexdigest() == encoding["sha256"]
    key = hashlib.sha1(encoding["url"].encode()).hexdigest()
    assert hashlib.sha256((root / "encoding-cache" / key).read_bytes()).hexdigest() == encoding["sha256"]
    os.environ["TIKTOKEN_CACHE_DIR"] = str(root / "encoding-cache")

    def refuse(*args: object, **kwargs: object) -> None:
        raise RuntimeError("TOKENIZER_NETWORK_FORBIDDEN")

    import tiktoken
    import tiktoken.load
    import tiktoken.model

    patch("socket.socket", side_effect=refuse).start()
    patch("tiktoken.load.read_file", side_effect=refuse).start()
    published = json.loads((root / "01_ACQUISITION_MANIFEST.json").read_text())
    assert hashlib.sha256(Path(tiktoken.model.__file__).read_bytes()).hexdigest() == published["published_model_sha256"]
    data = json.loads(sys.stdin.buffer.read(300000))
    model = data["model"]
    resolved = tiktoken.model.encoding_name_for_model(model)
    if resolved != encoding["name"]:
        raise ValueError("TOKENIZER_ENCODING_NOT_QUALIFIED")
    enc = tiktoken.encoding_for_model(model)
    body = data["request"]
    rows: list[Field] = []

    def walk(value: object, path: str) -> None:
        if isinstance(value, str):
            rows.append({"path": path, "tokens": len(enc.encode(value, disallowed_special=()))})
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(k, path + "/@key:" + k)
                walk(v, path + "/" + k)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, path + "/" + str(i))

    walk(body, "")
    text_count = sum(row["tokens"] for row in rows)
    serialized = len(enc.encode(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")), disallowed_special=()))
    prefix = next((p for p in tiktoken.model.MODEL_PREFIX_TO_ENCODING if model.startswith(p)), None)
    print(json.dumps({"schema": "MEGA-OFFLINE-TOKEN-COUNT-1.0", "model": model,
        "tokenizer": "tiktoken", "version": published["version"], "encoding": resolved,
        "recognition": "OFFICIAL_UNMODIFIED_PACKAGE_RESOLVER", "published_prefix": prefix,
        "model_mapping_sha256": published["published_model_sha256"],
        "encoding_sha256": encoding["sha256"], "all_string_values_and_keys_tokens": text_count,
        "serialized_json_tokens": serialized, "local_text_tokens": max(text_count, serialized),
        "fields": rows, "network_forbidden_during_count": True, "provider_calls": 0}))


if __name__ == "__main__":
    main()
