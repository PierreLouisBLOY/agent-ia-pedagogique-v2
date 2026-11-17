"""Local Application tool for the separate documentary library; no provider entry point."""
import argparse
import json
import sqlite3
from pathlib import Path

from backend.infrastructure.composition.factories.documentary_library import (
    build_documentary_library,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bibliothèque documentaire V2 indépendante, sans admission automatique")
    parser.add_argument("operation", choices=("import", "summary", "read", "verify"))
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--archive-sha256")
    parser.add_argument("--package")
    parser.add_argument("--document")
    args = parser.parse_args(argv)
    if (not args.database.is_absolute() or not args.data_root.is_absolute()
            or (args.operation == "import") != (args.archive is not None and args.archive_sha256 is not None)
            or args.operation != "import" and (args.archive is not None or args.archive_sha256 is not None)
            or args.document is not None and args.operation != "read"):
        parser.error("Descripteur explicite requis ; les consultations ne configurent jamais un import.")
    try:
        app = build_documentary_library(database=args.database, data_root=args.data_root,
            archive=args.archive, archive_sha256=args.archive_sha256)
        result = app.execute(args.operation, archive=args.package or "", document=args.document)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, KeyError) as error:
        code = str(error) if isinstance(error, ValueError) and str(error).startswith("DOCUMENTARY_") else "DOCUMENTARY_LOCAL_OPERATION_REFUSED"
        print(json.dumps({"error": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
