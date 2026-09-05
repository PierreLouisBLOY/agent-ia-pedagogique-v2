"""Explicit local entry point; no environment loading or side effects on import."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    build_local_read15,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="READ-15 local : cible explicite, aucune migration.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--bind-host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--runtime-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        composition = build_local_read15(
            LocalBrowserHttpConfiguration(port=args.port, bind_host=args.bind_host),
            Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
        )
    except Exception:
        print("LOCAL_READ15_STARTUP_REJECTED")
        return 1
    try:
        print(f"READ-15 local : {composition.url}", flush=True)
        composition.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception:
        print("LOCAL_READ15_EXECUTION_FAILED")
        return 1
    finally:
        composition.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
