"""Explicit local entry point; no environment loading or side effects on import."""

from __future__ import annotations

import argparse
import getpass
import sys
import tempfile
import warnings
from collections.abc import Sequence
from pathlib import Path

from backend.infrastructure.composition.factories.conversation import (
    build_r2_process_job,
    load_r2_grant,
    r2_source_material,
)
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
    parser.add_argument("--enable-conversation", action="store_true",
                        help="R2 volatile, sans autorisation fournisseur implicite")
    parser.add_argument("--live-authorization", type=Path,
                        help="Fichier explicite réservé au handoff live ; refusé tant que ses préconditions ne sont pas établies")
    args = parser.parse_args(argv)
    jobs = None
    secret_value = ""
    if args.live_authorization is not None:
        try:
            if not args.enable_conversation:
                raise ValueError("R2_CONVERSATION_REQUIRED")
            grant = load_r2_grant(args.live_authorization)
            baseline, scope = r2_source_material()
            jobs = build_r2_process_job(grant=grant, scope=scope, baseline=baseline,
                target=Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
                receipt_root=args.data_root / "r2-private-receipts",
                private_temp=Path(tempfile.gettempdir()),
                credential_input=lambda: secret_value)
            # Interactive entry is before the bounded job, after every preflight.
            # Never allow getpass's unmasked fallback on a redirected console.
            if not sys.stdin.isatty():
                raise ValueError("R2_MASKED_CONSOLE_REQUIRED")
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                secret_value = getpass.getpass("Clé OpenAI locale (masquée, non conservée) : ")
        except Exception:
            print("R2_LIVE_PREFLIGHT_NOT_READY")
            return 1
    try:
        composition = build_local_read15(
            LocalBrowserHttpConfiguration(port=args.port, bind_host=args.bind_host),
            Read15RuntimeTarget(args.runtime, args.data_root, args.runtime_sha256),
            enable_conversation=args.enable_conversation,
            generation_jobs=jobs,
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
        secret_value = ""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
