"""Explicit one-shot metadata action; no service, effect, recovery or generation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.infrastructure.composition.factories.p0_authentication_diagnostic import (
    compose_p0_authentication_diagnostic,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal-profile", type=Path, required=True)
    parser.add_argument("--normal-profile-sha256", required=True)
    parser.add_argument("--model", choices=["gpt-5.6-terra"], required=True)
    parser.add_argument("--execute-single-metadata-get", action="store_true")
    args = parser.parse_args()
    if not args.execute_single_metadata_get:
        print(json.dumps({"state": "NO_REQUEST_AUTHORIZED", "attempts": 0}))
        return 0
    try:
        query, resolver = compose_p0_authentication_diagnostic(
            profile_path=args.normal_profile,
            expected_sha256=args.normal_profile_sha256, model=args.model)
    except Exception:  # noqa: BLE001 - final inbound boundary must never print a secret-bearing exception
        result = {"state": "LOCAL_COMPOSITION_REJECTED", "attempts": 0}
    else:
        try:
            result = query.execute()
        except Exception:  # noqa: BLE001 - an observation failure after execution cannot establish zero attempts
            result = {"state": "AUTHENTICATION_DIAGNOSTIC_OUTCOME_INDETERMINATE", "attempts": None}
        finally:
            try:
                resolver.close()
            except Exception:  # noqa: BLE001 - cleanup cannot replace an already observed outcome
                result["resolver_cleanup_error"] = True
    print(json.dumps({**result, "scope": "ISOLATED_TARGET_COMPOSITION_NOT_HTTP_SERVER"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
