"""Offline R5 entry: explicit private copy, confirmed context, no provider authority."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast
from uuid import uuid4

from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.local_reference import prepare_local_references
from backend.infrastructure.filesystem.security import (
    assert_local_data_root,
    capture_secure_path,
    ensure_private_directory,
    harden_private_file,
    read_file_nofollow,
)
from backend.modules.pedagogical_context.contracts.dto.conversation_context import (
    ConfirmedConversationContext,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    ConversationDraftRequest,
)


def execute(*, target: Read15RuntimeTarget, request_path: Path, output: Path) -> str:
    repo = Path(__file__).resolve().parents[4]
    output = assert_local_data_root(output)
    request_path = assert_local_data_root(request_path)
    if output.is_relative_to(repo) or request_path.is_relative_to(repo):
        raise ValueError("PRIVATE_EXTERNAL_PATH_REQUIRED")
    if capture_secure_path(output, allowed_root=output.parent).exists:
        raise ValueError("FRESH_OUTPUT_REQUIRED")
    raw = read_file_nofollow(request_path, allowed_root=request_path.parent, maximum_bytes=65536)
    values = json.loads(raw)
    if (not isinstance(values, dict) or set(values) - {"brief", "context", "queries", "selection"}
            or not {"brief", "context", "queries"} <= set(values)
            or not isinstance(values["queries"], list)
            or not all(isinstance(q, str) for q in values["queries"])):
        raise ValueError("REFERENCE_REQUEST_INVALID")
    context = ConfirmedConversationContext(values["context"])
    request = ConversationDraftRequest("req:" + uuid4().hex, "conv:" + uuid4().hex,
        "gen:" + uuid4().hex, values["brief"], context)
    result = prepare_local_references(target, request=request, queries=tuple(values["queries"]),
        selection=values.get("selection"))
    result["confirmed_context"] = context.as_dict()
    result["request_sha256"] = hashlib.sha256(raw).hexdigest()
    encoded = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    refs = cast(list[dict[str, object]], result["provenance"])
    lines = ["# Références locales — préparation privée R5", "", "READY_NOT_SENT : aucun appel fournisseur.",
        "Sélection technique à apprécier ; aucun document complet ni autorité officielle attestée.", ""]
    for item in refs:
        lines.extend(["## " + str(item["query"]), "", "Source : " + str(item["source_ref"]),
            "Passage : " + str(item["locator"]), "Empreinte : " + str(item["version_or_checksum"]),
            "Lien documentaire : " + str(item["document_link_status"]), "", str(item["excerpt"]), ""])
    # Reserve a fresh directory; an incomplete export has no manifest and is never reused.
    output.mkdir(mode=0o700, exist_ok=False)
    ensure_private_directory(output, allowed_root=output.parent)
    files = {"projection.json": encoded, "references.md": "\n".join(lines).encode("utf-8")}
    manifest = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in files.items())
    files["MANIFEST_SHA256.txt"] = manifest.encode("ascii")
    for name, data in files.items():
        path = output / name
        with path.open("xb") as stream:
            stream.write(data)
        harden_private_file(path, allowed_root=output)
    return hashlib.sha256(files["MANIFEST_SHA256.txt"]).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R5 : préparation privée, aucun envoi.")
    for name in ("runtime", "data-root", "request", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--runtime-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        sha = execute(target=Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
                      request_path=args.request, output=args.output)
    except Exception:
        print("R5_REFERENCE_PREPARATION_REJECTED")
        return 1
    print("R5_REFERENCE_READY_NOT_SENT " + sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
