"""Exact offline locator successor; immutable historical tables remain authoritative."""
from __future__ import annotations

import ast
import hashlib
import subprocess
from functools import lru_cache
from pathlib import Path

BASELINE = "8b341b76b32c37a2232c053190b04b89cb5f6983"
SELF = "tests/support/r3_locator_materialization_guard.py"
PRE = {
    "backend/adapters/outbound/generation/openai/prepare_contract.py": "0fe9530ef117f8000341a1f37caef20b2f9a4b00a88f33ef4eb12cd315b9f1f6",
    "backend/adapters/outbound/generation/openai/adapter.py": "33be83bbbe85b79f3d6a2ef127a5ab467b8e80d33f49ded2cce3ad2d6b8862ea",
    "backend/adapters/outbound/generation/openai/mapping.py": "719627c198db268c2f503e9a8084c13b4992cd4957fb040858dc678b6c9f5e2a",
    "backend/adapters/outbound/generation/parse_diagnostic.py": "89663dc7e83907463197ad319d23ca2dca7206912017e5bbd8810cd3eaa6771b",
    "tests/support/r3_cap_a01_guard.py": "bf8bdfacf0e0f35d754833f4543968401b6d64cd43d103e6c698786273e2ba4d",
    "tests/support/r3_serializer_8192_guard.py": "cf17f30b5e73ee41f521c88780a35d0c7a2b39fafde8ec001a39d398c13c05d4",
    "tests/support/r3_prepare_contract_alignment_guard.py": "6a89a35ff7d5f8049e4680c44f4b29fa5096f6df6a8d72040b3bacca70824604",
    "tests/support/r3_parse_observability_guard.py": "09df9ef040ce94c70898bf6a265f00623f287813621d24f61caffb00cb9fdef2",
    "tests/support/r3_guard_oracle.py": "533b0663474ea04eaa16caf8312db7273839258dddc8bed145a1ea2a6e8a82cc",
    "tests/unit/test_r3_prepare_contract_alignment.py": "303e17b9f1dc7450b16ac09b29dfde9c39deb07869afe631d48bd101c6b84987",
    "tests/integration/test_r3_prepare_contract_alignment.py": "969d162cc397efb0aba7a1da92629cac9dc758cccdbab63039971246ef986de3",
    "tests/unit/test_r3_cap_a01_targeted.py": "459fefb78f54c19c47158a7ff8568bf32e3617f58062dd0ca6eff9502f4028d7",
    "tests/integration/test_r3_cap_a01_targeted.py": "057810a4a48a89504eb028d402ee126c9506e65ed47a194e8516c4cbc9d5f302",
    "tests/unit/test_r3_parse_observability.py": "7f35025693565498d7faf1f29fcc513f3aaf8a0b757df768ce7c7a3fbbbda2d8",
    "tests/integration/test_r3_parse_observability.py": "bede7031c1145ec7af44eba1f933faefbdd8c011c70d50de1fdabd2ed0c3a931",
    "tests/unit/test_r3_prepare_serialization.py": "179bced6f0ea428c3bf856ecdea985364c9caea2a6c4cc5e6477c8228c8b6031"
}
SYMBOLS = {
    "backend/adapters/outbound/generation/openai/prepare_contract.py": [
        "INSTRUCTIONS",
        "prepare_output_schema"
    ],
    "backend/adapters/outbound/generation/openai/adapter.py": [
        "_map_response_body"
    ],
    "backend/adapters/outbound/generation/openai/mapping.py": [
        "build_openai_request"
    ],
    "backend/adapters/outbound/generation/parse_diagnostic.py": [
        "ParseCode"
    ],
    "tests/support/r3_cap_a01_guard.py": [
        "source_matches",
        "violations",
        "assert_scope",
        "assert_git_state"
    ],
    "tests/support/r3_serializer_8192_guard.py": [
        "assert_scope",
        "assert_git_state"
    ],
    "tests/support/r3_prepare_contract_alignment_guard.py": [
        "successor_violations",
        "source_matches",
        "assert_successor_scope",
        "assert_successor_git_state"
    ],
    "tests/support/r3_parse_observability_guard.py": [
        "patch_violations",
        "assert_patch_git_state"
    ],
    "tests/support/r3_guard_oracle.py": [
        "active_inventory"
    ],
    "tests/unit/test_r3_prepare_contract_alignment.py": [
        "test_each_missing_root_field_rejected_without_defaults",
        "test_bad_provider_data_is_never_repaired",
        "test_normalization_preserves_every_field_and_internal_parser",
        "test_provider_status_cannot_be_upgraded",
        "copied_sources"
    ],
    "tests/integration/test_r3_prepare_contract_alignment.py": [
        "DirectPreparePort.generate"
    ],
    "tests/unit/test_r3_cap_a01_targeted.py": [
        "observe",
        "test_unit_conversion_and_nominal_warning_preserved",
        "test_each_targeted_successor_identity_is_closed",
        "test_frozen_scope_working_index_history_and_self_authentication"
    ],
    "tests/integration/test_r3_cap_a01_targeted.py": [
        "SyntheticPort.generate",
        "test_actual_pipeline_preserves_fail_closed_publication_and_closed_export"
    ],
    "tests/unit/test_r3_parse_observability.py": [
        "test_closed_schema_first_failure_and_unexpected_exception_privacy",
        "test_every_patch_source_mutation_is_rejected"
    ],
    "tests/integration/test_r3_parse_observability.py": [
        "SyntheticResponsePort.generate"
    ],
    "tests/unit/test_r3_prepare_serialization.py": [
        "test_each_successor_source_mutation_is_rejected"
    ]
}
CREATES = [
    "backend/adapters/outbound/generation/openai/locator_materialization.py",
    "tests/support/r3_locator_fixtures.py",
    "tests/support/r3_locator_materialization_guard.py",
    "tests/unit/test_r3_locator_materialization.py",
    "tests/integration/test_r3_locator_materialization.py",
    "architecture/adr/ADR-r3-deterministic-locator-materialization.md"
]
PATHS = tuple(PRE) + tuple(CREATES)
POST = {
    "backend/adapters/outbound/generation/openai/prepare_contract.py": "a5df681dd26c0205fc644fc18eaf507b83deb29dd899454159e81e42b68c3b5f",
    "backend/adapters/outbound/generation/openai/adapter.py": "409adc317691285eb03bbbba672c5ecaae2a80ca83158d486d3234c6f291c384",
    "backend/adapters/outbound/generation/openai/mapping.py": "86e6e51830cf5ea70fc25507d643fcb63da144a6a0f1dcc42fa65b933d671438",
    "backend/adapters/outbound/generation/parse_diagnostic.py": "4032684e9c609f14d0a8a1e0ecd11c617a9cfd08e291979776587d9db4d0023a",
    "tests/support/r3_cap_a01_guard.py": "e0c2d780828b735072ff3e424118f6592d12a28eb663a41c6c07598aa9a5c374",
    "tests/support/r3_serializer_8192_guard.py": "647fe01272e1e23b4b0d87d5eb0e61ad493c777f0e007ab6b9afe686ddfc5be0",
    "tests/support/r3_prepare_contract_alignment_guard.py": "223719d17d0459ad944c443ecbce7eed39a58d3ffca45c9432f0144538439815",
    "tests/support/r3_parse_observability_guard.py": "7e487477d931ddb8cb316875494449d60f354216a71d11b3455f782aa49e07c3",
    "tests/support/r3_guard_oracle.py": "4114c596686d219d87860d571f55d8fb2d9ba00aa13c2aadda1c8a7417cd1861",
    "tests/unit/test_r3_prepare_contract_alignment.py": "53e3bb00500c133d32a88778f244fdaf1e4077faec986a6b409516c94312b2d3",
    "tests/integration/test_r3_prepare_contract_alignment.py": "1c93f00c56acb69b2d7707152143074755641b9fb31a62f5cd89ffb08436aa36",
    "tests/unit/test_r3_cap_a01_targeted.py": "9b7b61e88d337431166387c8014641803e7b5c366b721cceea1e01b33942bf16",
    "tests/integration/test_r3_cap_a01_targeted.py": "52c8f6c42f5745dc8cfb0d5cebe62b403038bb8fadfcc655c867beaceccade3d",
    "tests/unit/test_r3_parse_observability.py": "398f6ba0e94c84d5bd16e0f502c6c5e4292f19222ee09ad750cb998b46979dd3",
    "tests/integration/test_r3_parse_observability.py": "f79cfe565926433c65c55fd203d04288b7f510e80acde4412378048eb2cb1d83",
    "tests/unit/test_r3_prepare_serialization.py": "48ce1dede8196b8aef6addb2f821633d21b02f50655cf2d0a488f063d37ca563",
    "backend/adapters/outbound/generation/openai/locator_materialization.py": "b30b1311ffccff4451abfd3e222fa27902077f1ac2795f6995b018f31edf2942",
    "tests/support/r3_locator_fixtures.py": "433098c4445f8ba102e5a3f92cf30f339a081af61e9e0f7edfc89fef865b30c5",
    "tests/unit/test_r3_locator_materialization.py": "9ad0c3346276200ac0f5759443bba193be65f34cb7618358d43ac5108c2e25d4",
    "tests/integration/test_r3_locator_materialization.py": "8b0d0172e31416421af13f7e280d8336e5443bfdb9f67812e6c67768a852440e",
    "architecture/adr/ADR-r3-deterministic-locator-materialization.md": "e4eb2b10857f0cbd525113dc83f893466ec9141410baab01f3bb74c42fc78bd1"
}
ORACLE_AST_SHA256 = "9849540e07c0a66a42b14c1a2122159fa0618131cad694dd0966d2281ee2d52f"

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def oracle_digest(raw: bytes) -> str:
    # Full normalized source (including comments), excluding only its self-hash line.
    tree = ast.parse(raw)
    nodes = [n for n in tree.body if (
        isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "ORACLE_AST_SHA256")]
    if len(nodes) != 1:
        raise ValueError("LOCATOR_SELF_HASH_DECLARATION")
    lines = raw.replace(b"\r\n", b"\n").splitlines(keepends=True)
    del lines[nodes[0].lineno - 1:nodes[0].end_lineno]
    return hashlib.sha256(b"".join(lines)).hexdigest()


def authenticated(root: Path) -> bool:
    try:
        return oracle_digest((root / SELF).read_bytes()) == ORACLE_AST_SHA256
    except (OSError, SyntaxError, ValueError):
        return False


def source_matches(root: Path, path: str, historical: str) -> bool:
    """Only one exact baseline->post binding, not an inventory exemption."""
    file = root / path
    return (path in PRE and historical == PRE[path] and authenticated(root)
            and file.is_file() and digest(file.read_bytes()) == POST.get(path))


@lru_cache(maxsize=32)
def _baseline_bytes(path: str) -> bytes:
    assert path in PRE
    root = Path(__file__).resolve().parents[2]
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=root,
                         check=True, capture_output=True).stdout
    assert digest(raw) == PRE[path], path
    return raw


def prior_scope_bytes(root: Path, path: str) -> bytes:
    """Historical AST view ONLY after authenticating exact successor bytes."""
    raw = (root / path).read_bytes()
    if path in PRE and source_matches(root, path, PRE[path]):
        return _baseline_bytes(path)
    return raw  # Unknown bytes must fail the historical comparison as well.


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    assert len(PATHS) == len(set(PATHS)) == 22
    assert set(POST) == set(PATHS) - {SELF}
    errors = []
    for path, expected in POST.items():
        file = root / path
        if not file.is_file() or digest(file.read_bytes()) != expected:
            errors.append("LOCATOR_IDENTITY:" + path)
    if not authenticated(root):
        errors.append("LOCATOR_ORACLE_IDENTITY")
    if changed is not None:
        errors += ["LOCATOR_MISSING:" + p for p in sorted(set(PATHS) - changed)]
        errors += ["LOCATOR_UNAPPROVED:" + p for p in sorted(changed - set(PATHS))]
    return errors


def outside_scope(raw: bytes, path: str) -> str:
    tree = ast.parse(raw)
    def strip(nodes, prefix=""):
        kept = []
        for node in nodes:
            name = prefix + getattr(node, "name", "")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if name in SYMBOLS[path]:
                    # Keep the declaration, decorators and signature; allow body changes only.
                    node.body = [ast.Pass()]
                elif isinstance(node, ast.ClassDef):
                    node.body = strip(node.body, name + ".")
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in SYMBOLS[path]:
                    node.value = ast.Constant(None)
            kept.append(node)
        return kept
    tree.body = strip(tree.body)
    return ast.dump(tree)


def assert_scope(root: Path) -> None:
    assert violations(root) == []
    for path in PRE:
        before, after = _baseline_bytes(path), (root / path).read_bytes()
        assert outside_scope(before, path) == outside_scope(after, path), path
        if path.endswith("_guard.py"):
            old, new = ast.parse(before), ast.parse(after)
            def declarations(tree):
                return [ast.dump(n) for n in tree.body if not isinstance(n, ast.FunctionDef)]
            assert declarations(old) == declarations(new), path
    # All canonical predicates and R2/HARDEN/REVIEW boundaries remain exact baseline bytes.
    protected = (
        "backend/modules/pedagogical_design/contracts/dto/assessment_bundle.py",
        "backend/modules/pedagogical_design/domain/policies/assessment_revision.py",
        "backend/modules/validation_control/domain/policies/assessment_checks.py",
        "backend/infrastructure/composition/bindings/r3_agents.py",
        "backend/infrastructure/composition/factories/conversation.py",
        "backend/infrastructure/composition/factories/r3_prepare_serialization.py",
        "backend/adapters/outbound/generation/assessment_revision.py",
        "backend/adapters/outbound/review/assessment_review.py",
    )
    repository = Path(__file__).resolve().parents[2]
    for path in protected:
        before = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=repository,
                                check=True, capture_output=True).stdout
        assert before == (root / path).read_bytes(), path


def assert_git_state(root: Path) -> None:
    from tests.support.r3_guard_oracle import PREPARATION

    observed = set()
    for args in (["diff", "--name-only", BASELINE, "--"],
                 ["diff", "--cached", "--name-only", BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
        paths = set(result.stdout.splitlines())
        if "--cached" in args:
            assert not paths & set(PREPARATION)
        observed.update(paths)
    assert violations(root, changed=observed - set(PREPARATION)) == []
    assert_scope(root)
    for path in PATHS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True)
        if staged.returncode:
            assert path in CREATES, path
        elif path in PRE and digest(staged.stdout) == PRE[path]:
            continue
        elif path == SELF:
            assert oracle_digest(staged.stdout) == ORACLE_AST_SHA256
            assert digest(staged.stdout) == digest((root / path).read_bytes())
        else:
            assert digest(staged.stdout) == POST[path], path
