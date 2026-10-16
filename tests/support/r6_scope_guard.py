"""Exact R6 successor inventory pinned to the PRE-R6 candidate baseline."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

BASELINE = "5bdd49be35149a7134e866fa4473926b65a5ee69"
ROOT = Path(__file__).resolve().parents[2]
SELF = "tests/support/r6_scope_guard.py"
MANIFEST = "tests/support/r6_scope_manifest.json"
SELF_SHA256 = "bb813b672cb5ad9f79239735394625721a44b072820c81883b50dd7ee51115d3"
MANIFEST_SHA256 = "9b776a539b54cf58d6e6b941fad847afc0f95fafe767479b06f4823100dba48b"

# Populated by the bounded private-source successor; never an open deletion list.
PRIVATE_PREPARATION_PATHS: frozenset[str] = frozenset((
    'docs/development/phase_12_18_h1_audit_cumulatif/01_BASELINE_ET_PERIMETRE.md',
    'docs/development/phase_12_18_h1_audit_cumulatif/02_MATRICE_CUMULATIVE_12_1_12_17.json',
    'docs/development/phase_12_18_h1_audit_cumulatif/03_ETAT_INTEGRATION_PRODUIT.md',
    'docs/development/phase_12_18_h1_audit_cumulatif/04_ECARTS_ET_PREPARATION_RECETTE.json',
    'docs/development/phase_12_18_h1_audit_cumulatif/LIVRABLE_12_18_H1_AUDIT_CUMULATIF.md',
    'docs/development/phase_12_18_h1_audit_cumulatif/MANIFEST_SHA256.txt',
    'docs/development/phase_12_18_h1a_sources_et_evolution_guard/01_SOURCES_ET_ECARTS_RECONCILIES.json',
    'docs/development/phase_12_18_h1a_sources_et_evolution_guard/02_PROPOSITION_EVOLUTION_GUARD.md',
    'docs/development/phase_12_18_h1a_sources_et_evolution_guard/03_PAQUET_DECISION_ET_PLAN_H2.md',
    'docs/development/phase_12_18_h1a_sources_et_evolution_guard/LIVRABLE_H1A_SOURCES_ET_GUARD.md',
    'docs/development/phase_12_18_h1a_sources_et_evolution_guard/MANIFEST_SHA256.txt',
    'docs/development/phase_12_18_h2_r2_generation_preparation/01_CONTRAT_R2_GENERATION_CONVERSATIONNELLE.md',
    'docs/development/phase_12_18_h2_r2_generation_preparation/02_INVENTAIRE_GUARDS_TESTS_PERMISSIONS_R2.json',
    'docs/development/phase_12_18_h2_r2_generation_preparation/03_DECISION_ET_PLAN_EXECUTION_R2.md',
    'docs/development/phase_12_18_h2_r2_generation_preparation/MANIFEST_SHA256.txt',
    'docs/development/phase_12_18_h2_r3_review_modify_preparation/01_CONTRAT_R3_REVIEW_VALIDATION_MODIFICATION.md',
    'docs/development/phase_12_18_h2_r3_review_modify_preparation/02_INVENTAIRE_FICHIERS_GUARDS_R3.json',
    'docs/development/phase_12_18_h2_r3_review_modify_preparation/03_DECISION_ET_PLAN_EXECUTION_R3.md',
    'docs/development/phase_12_18_h2_r3_review_modify_preparation/04_SCENARIO_ACCEPTATION_R3.md',
    'docs/development/phase_12_18_h2_r3_review_modify_preparation/LIVRABLE_PROPOSITION_R3.md',
    'docs/development/phase_12_18_h2_r3_review_modify_preparation/MANIFEST_SHA256.txt',
    'docs/development/phase_12_18_h2_recherche_locale_preparation/01_BASELINE_ET_REUTILISATION.md',
    'docs/development/phase_12_18_h2_recherche_locale_preparation/02_CONTRAT_RECHERCHE_LOCALE_PROPOSE.md',
    'docs/development/phase_12_18_h2_recherche_locale_preparation/03_INVENTAIRE_FICHIERS_ET_GUARDS.json',
    'docs/development/phase_12_18_h2_recherche_locale_preparation/04_DECISION_ET_PLAN_IMPLEMENTATION.md',
    'docs/development/phase_12_18_h2_recherche_locale_preparation/LIVRABLE_PROPOSITION_RECHERCHE_LOCALE.md',
    'docs/development/phase_12_18_h2_recherche_locale_preparation/MANIFEST_SHA256.txt',
))


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _guard_digest(raw: bytes) -> str:
    self_pattern = rb"^SELF_" + rb"SHA256 = \"[^\"]+\"\r?\n"
    manifest_pattern = rb"^MANIFEST_" + rb"SHA256 = \"[^\"]+\"\r?\n"
    canonical = re.sub(self_pattern, b"", raw, flags=re.M)
    canonical = re.sub(manifest_pattern, b"", canonical, flags=re.M)
    return digest(canonical)


def _manifest(root: Path) -> dict[str, object]:
    path = root / MANIFEST
    raw = path.read_bytes()
    if digest(raw) != MANIFEST_SHA256:
        raise ValueError("R6_MANIFEST_IDENTITY")
    value = json.loads(raw)
    if value.get("schema") != "R6-SCOPE-MANIFEST-1.0" or value.get("baseline") != BASELINE:
        raise ValueError("R6_MANIFEST_SCHEMA")
    return value


def _authenticated(root: Path) -> bool:
    try:
        if _guard_digest((root / SELF).read_bytes()) != SELF_SHA256:
            return False
        _manifest(root)
        return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _paths(root: Path) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, str]]:
    value = _manifest(root)
    cp645 = tuple(value["cp645_paths"])
    r6 = tuple(value["r6_paths"])
    expected = dict(value["sha256"])
    if len(cp645) != len(set(cp645)) or len(r6) != len(set(r6)):
        raise ValueError("R6_PATH_DUPLICATE")
    if set(cp645) & set(r6) or set(expected) != set(cp645) | set(r6):
        raise ValueError("R6_PATH_INVENTORY")
    return cp645, r6, expected


def authenticated(root: Path = ROOT) -> bool:
    return _authenticated(root)


def exact(root: Path, path: str) -> bool:
    try:
        if not _authenticated(root):
            return False
        _, _, expected = _paths(root)
        return path in expected and digest((root / path).read_bytes()) == expected[path]
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    try:
        _, _, expected = _paths(root)
        return _authenticated(root) and path in expected and digest(raw) == expected[path]
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def violations(root: Path = ROOT, *, changed: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if not _authenticated(root):
        return ["R6_GUARD_OR_MANIFEST_IDENTITY"]
    cp645, r6, expected = _paths(root)
    if set(expected) != set(cp645) | set(r6):
        errors.append("R6_INVENTORY_IDENTITY")
    errors.extend("R6_IDENTITY:" + path for path in expected if not exact(root, path))
    if changed is not None:
        allowed = set(cp645) | set(r6)
        errors.extend("R6_UNAPPROVED:" + path for path in sorted(changed - allowed))
        errors.extend("R6_MISSING:" + path for path in sorted(allowed - changed))
    return errors


def private_source_inventory(value: object) -> frozenset[str] | None:
    """Only the exact canonical private preparation list may be withdrawn."""
    if type(value) is not list or any(type(p) is not str for p in value):
        return None
    if len(value) != len(set(value)) or set(value) != PRIVATE_PREPARATION_PATHS:
        return None
    return frozenset(value)


def active_delta_violations(root: Path, changed: set[str]) -> list[str]:
    """Authenticate the declared fabrication delta separately from protected reuse."""
    errors = violations(root)
    if errors:
        return errors
    value = _manifest(root)
    excluded = private_source_inventory(value.get("private_source_exclusions"))
    if excluded is None:
        return ["R6_PRIVATE_SOURCE_EXCLUSION_INVENTORY"]
    try:
        indexed = set(subprocess.run(["git", "ls-files", "-z"], cwd=root,
            check=True, capture_output=True, text=True).stdout.split("\0"))
    except (OSError, subprocess.CalledProcessError):
        return ["R6_PRIVATE_SOURCE_INDEX_UNREADABLE"]
    errors.extend("R6_PRIVATE_SOURCE_INDEXED:" + p for p in sorted(indexed & excluded))
    declared = set(value["active_delta_paths"])
    protected = set(value["sha256"]) | {SELF, MANIFEST} | excluded
    if not declared <= protected:
        return ["R6_ACTIVE_DELTA_NOT_PROTECTED"]
    errors.extend("R6_ACTIVE_UNAPPROVED:" + p for p in sorted(changed - declared))
    errors.extend("R6_ACTIVE_MISSING:" + p for p in sorted(declared - changed))
    return errors


def _load_constants() -> None:
    global CP645_PATHS, CP645_PRE, CP645_POST, R6_PATHS, PATHS
    value = _manifest(ROOT)
    CP645_PATHS = tuple(value["cp645_paths"])
    CP645_PRE = dict(value["cp645_pre_sha256"])
    CP645_POST = {path: value["sha256"][path] for path in CP645_PATHS}
    R6_PATHS = tuple(value["r6_paths"])
    PATHS = tuple((*CP645_PATHS, *R6_PATHS))


_load_constants()
