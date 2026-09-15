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
    build_local_saved,
)
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="READ-15 local : cible explicite, aucune migration.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--bind-host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--runtime-sha256")
    parser.add_argument("--saved-root", type=Path, help="Stockage R4 explicitement désigné hors dépôt")
    parser.add_argument("--create-saved", action="store_true", help="Créer une racine R4 neuve uniquement")
    parser.add_argument("--saved-only", action="store_true", help="Ouvrir R4 sans bibliothèque ni fournisseur")
    parser.add_argument("--enable-conversation", action="store_true",
                        help="R2 volatile, sans autorisation fournisseur implicite")
    parser.add_argument("--enable-review-modify", action="store_true",
                        help="R3 volatile ; aucun provider autorisé")
    parser.add_argument("--live-authorization", type=Path,
                        help="Fichier explicite réservé au handoff live ; refusé tant que ses préconditions ne sont pas établies")
    args = parser.parse_args(argv)
    if args.saved_only:
        if (args.saved_root is None or any((args.runtime, args.data_root, args.runtime_sha256,
                args.enable_conversation, args.enable_review_modify, args.live_authorization))):
            print("R4_EXPLICIT_STORE_ONLY_REQUIRED")
            return 1
        try:
            saved = build_local_saved(LocalBrowserHttpConfiguration(port=args.port, bind_host=args.bind_host),
                                      args.saved_root, create=args.create_saved)
        except Exception:
            print("R4_STARTUP_REJECTED")
            return 1
        try:
            print(f"R4 local : {saved.url}", flush=True)
            saved.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            saved.close()
        return 0
    if (args.runtime is None or args.data_root is None or args.runtime_sha256 is None
            or (args.create_saved and args.saved_root is None)):
        print("EXPLICIT_RUNTIME_REQUIRED")
        return 1
    if args.enable_review_modify and (not args.enable_conversation or args.live_authorization is not None):
        print("R3_SYNTHETIC_ONLY")
        return 1
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
            enable_review_modify=args.enable_review_modify,
            saved_root=args.saved_root, create_saved=args.create_saved,
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
