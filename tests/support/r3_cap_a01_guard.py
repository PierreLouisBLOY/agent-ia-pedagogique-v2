"""Independent exact CAP-A01 successor; no historical table or runtime authority."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

BASELINE = "5215f6071ce4f6f1519b3cb3e6be65d1d2e5179c"
SELF = "tests/support/r3_cap_a01_guard.py"
PRE = {
    "backend/adapters/outbound/generation/openai/prepare_contract.py": "f8b5ac687f4655690986f37685d5b0039e6def4b2ada08e2e18309a88c76d0b2",
    "backend/modules/validation_control/domain/policies/assessment_checks.py": "687a1e80e9c2feedbda98734ae940d9e4a9750bd28bd16fb56a7f9290e4c7c75",
    "backend/modules/validation_control/contracts/dto/deterministic_validation.py": "be614777b5315ff5eef93b20f268c2df5dec80d7b53174aa8bc3dc93bb872f12",
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": "589b4edb117b8ed35abd30056f7b3b974bce5b7f79ac3d56d7977d026a51bb11",
    "tests/support/r3_guard_oracle.py": "8f2ad26eac2193746dbfb1c8eb80a1b58746bcd39d5e9132d651c4d2026a29d9",
    "tests/support/r3_parse_observability_guard.py": "9e9596ace319b0d18b9c20fad5a59dca52dd4c7a0fc499b4d6a9e8bf39c2483a",
    "tests/support/r3_prepare_contract_alignment_guard.py": "e5e1fe1c0619261c9c93c9752265953ba6cd2faefef129decba95222c1aceca5",
    "tests/support/r3_serializer_8192_guard.py": "ee6df7c402876b545c9169203afcdbe3f372ad557371c253906be75a4c9dd455",
    "tests/unit/test_r3_parse_observability.py": "0428a7a34364048c402f8ce2e37eded48fd448380d53294ff648cf647a236431",
    "tests/unit/test_r3_prepare_contract_alignment.py": "923976d783a874c007a9cfed03aee87fd1fcbcbdefaa7b34c2d7e3069d2e862c",
    "tests/unit/test_r3_prepare_serialization.py": "3e218115a8202298cc14470dd71ae284fe073a423a075b9dddfeceb80f03f87a",
}
SYMBOLS = {
    "backend/adapters/outbound/generation/openai/prepare_contract.py": ["prepare_output_schema"],
    "backend/modules/validation_control/domain/policies/assessment_checks.py": [
        "_targeted_reason",
        "evaluate_checks",
    ],
    "backend/modules/validation_control/contracts/dto/deterministic_validation.py": [],
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": [],
    "tests/support/r3_guard_oracle.py": ["active_inventory"],
    "tests/support/r3_parse_observability_guard.py": ["patch_violations"],
    "tests/support/r3_prepare_contract_alignment_guard.py": [
        "successor_violations",
        "source_matches",
        "assert_successor_git_state",
    ],
    "tests/support/r3_serializer_8192_guard.py": [
        "source_matches",
        "violations",
        "assert_git_state",
    ],
    "tests/unit/test_r3_parse_observability.py": ["test_every_patch_source_mutation_is_rejected"],
    "tests/unit/test_r3_prepare_contract_alignment.py": ["copied_sources"],
    "tests/unit/test_r3_prepare_serialization.py": [
        "test_each_successor_source_mutation_is_rejected",
        "test_oracle_table_tampering_is_rejected",
    ],
}
CREATES = [
    "tests/unit/test_r3_cap_a01_targeted.py",
    "tests/integration/test_r3_cap_a01_targeted.py",
    "tests/support/r3_cap_a01_guard.py",
    "architecture/adr/ADR-r3-cap-a01-targeted-alignment.md",
]
PATHS = tuple(PRE) + tuple(CREATES)
POST = {
    "backend/adapters/outbound/generation/openai/prepare_contract.py": "0fe9530ef117f8000341a1f37caef20b2f9a4b00a88f33ef4eb12cd315b9f1f6",
    "backend/modules/validation_control/domain/policies/assessment_checks.py": "aa141e63d04b146d96eb6ecd78ca42c1c03040d24a3aa3a415441ea7fdd4f0bd",
    "backend/modules/validation_control/contracts/dto/deterministic_validation.py": "f6dc61deb03938e03be353f6eb65f747b26e47b71fa231227d87062c3d424896",
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": "67dddde182941f2649e312e0dba322188a8bd890b1d499b856af8946b6346664",
    "tests/support/r3_guard_oracle.py": "533b0663474ea04eaa16caf8312db7273839258dddc8bed145a1ea2a6e8a82cc",
    "tests/support/r3_parse_observability_guard.py": "09df9ef040ce94c70898bf6a265f00623f287813621d24f61caffb00cb9fdef2",
    "tests/support/r3_prepare_contract_alignment_guard.py": "6a89a35ff7d5f8049e4680c44f4b29fa5096f6df6a8d72040b3bacca70824604",
    "tests/support/r3_serializer_8192_guard.py": "cf17f30b5e73ee41f521c88780a35d0c7a2b39fafde8ec001a39d398c13c05d4",
    "tests/unit/test_r3_parse_observability.py": "7f35025693565498d7faf1f29fcc513f3aaf8a0b757df768ce7c7a3fbbbda2d8",
    "tests/unit/test_r3_prepare_contract_alignment.py": "303e17b9f1dc7450b16ac09b29dfde9c39deb07869afe631d48bd101c6b84987",
    "tests/unit/test_r3_prepare_serialization.py": "179bced6f0ea428c3bf856ecdea985364c9caea2a6c4cc5e6477c8228c8b6031",
    "tests/unit/test_r3_cap_a01_targeted.py": "459fefb78f54c19c47158a7ff8568bf32e3617f58062dd0ca6eff9502f4028d7",
    "tests/integration/test_r3_cap_a01_targeted.py": "057810a4a48a89504eb028d402ee126c9506e65ed47a194e8516c4cbc9d5f302",
    "architecture/adr/ADR-r3-cap-a01-targeted-alignment.md": "f1ac846535c9f6530f7bcc0485477accd96f205a40011062344a2e1b93d31fa7"
}
ORACLE_AST_SHA256 = "0f010b9d1cfb68a03ca9f0120b178603ddfca4895526607725ca4097acff9297"
R2_SOURCE = "backend/infrastructure/composition/factories/conversation.py"
R2_SHA256 = "d3817b7f4186ea2eecbc01732c903471869e1f9710e11c2dc6a4c0ad8b5ed97e"
SERIALIZER = "backend/infrastructure/composition/factories/r3_prepare_serialization.py"
SERIALIZER_SHA256 = "df8452be7091017d19ac5a4e1abdadd1711f4300542e7c556a52325873660190"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def oracle_digest(raw: bytes) -> str:
    tree = ast.parse(raw)
    tree.body = [
        n
        for n in tree.body
        if not (
            isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "ORACLE_AST_SHA256"
        )
    ]
    return hashlib.sha256(ast.dump(tree).encode()).hexdigest()


def source_matches(root: Path, path: str, historical: str) -> bool:
    from tests.support.r3_locator_materialization_guard import PRE as LOCATOR_PRE
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches

    file = root / path
    return (
        path in PRE
        and historical == PRE[path]
        and (oracle_digest(Path(__file__).read_bytes()) == ORACLE_AST_SHA256
             or locator_matches(Path(__file__).resolve().parents[2], SELF, LOCATOR_PRE[SELF]))
        and file.is_file()
        and (digest(file.read_bytes()) == POST[path] or locator_matches(root, path, POST[path]))
    )


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    from tests.support.r3_locator_materialization_guard import PRE as LOCATOR_PRE
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches

    assert len(PATHS) == len(set(PATHS)) == 15
    assert set(POST) == set(PATHS) - {SELF}
    errors = []
    for path, expected in POST.items():
        file = root / path
        if (not file.is_file() or digest(file.read_bytes()) != expected) and not locator_matches(root, path, expected):
            errors.append("CAP_TARGET_IDENTITY:" + path)
    try:
        if (oracle_digest((root / SELF).read_bytes()) != ORACLE_AST_SHA256
                and not locator_matches(root, SELF, LOCATOR_PRE[SELF])):
            errors.append("CAP_TARGET_ORACLE_IDENTITY")
    except (OSError, SyntaxError, ValueError):
        errors.append("CAP_TARGET_ORACLE_UNREADABLE")
    if changed is not None:
        errors += ["CAP_TARGET_MISSING:" + p for p in sorted(set(PATHS) - changed)]
        errors += ["CAP_TARGET_UNAPPROVED:" + p for p in sorted(changed - set(PATHS))]
    return errors


def outside_scope(raw: bytes, path: str) -> str:
    tree = ast.parse(raw)
    kept = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in SYMBOLS[path]:
            continue
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if (
                path.endswith("prepare_contract.py")
                and name == "INSTRUCTIONS"
                or path.endswith("deterministic_validation.py")
                and name == "TARGETED_CHECK_REASON_CODES"
            ):
                continue
            if name == "_DIAGNOSTIC_REASONS":
                # Only the imported closed vocabulary may augment this literal allowlist.
                call = node.value
                if isinstance(call, ast.Call) and isinstance(call.args[0], ast.Set):
                    call.args[0].elts = [
                        n
                        for n in call.args[0].elts
                        if not (
                            isinstance(n, ast.Starred)
                            and isinstance(n.value, ast.Name)
                            and n.value.id == "TARGETED_CHECK_REASON_CODES"
                        )
                    ]
        if isinstance(node, ast.ImportFrom) and node.module == (
            "backend.modules.validation_control.contracts.dto.deterministic_validation"
        ):
            node.names = [n for n in node.names if n.name != "TARGETED_CHECK_REASON_CODES"]
        kept.append(node)
    tree.body = kept
    return ast.dump(tree)


def assert_scope(root: Path, *, repository: Path | None = None) -> None:
    from tests.support.r3_locator_materialization_guard import prior_scope_bytes

    repository = repository or Path(__file__).resolve().parents[2]
    assert violations(root) == []
    for path, expected in PRE.items():
        raw = subprocess.run(
            ["git", "show", f"{BASELINE}:{path}"], cwd=repository, check=True, capture_output=True
        ).stdout
        assert digest(raw) == expected, path
        assert outside_scope(raw, path) == outside_scope(prior_scope_bytes(root, path), path), path
    for path, expected in ((R2_SOURCE, R2_SHA256), (SERIALIZER, SERIALIZER_SHA256)):
        assert digest((repository / path).read_bytes()) == expected, path


def assert_git_state(root: Path) -> None:
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_editorial_correction_guard import index_matches
    from tests.support.r3_guard_oracle import PREPARATION
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_locator_materialization_guard import PRE as LOCATOR_PRE
    from tests.support.r3_locator_materialization_guard import (
        assert_git_state as assert_locator_git_state,
    )
    from tests.support.r3_locator_materialization_guard import source_matches as locator_matches
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS

    assert_locator_git_state(root)
    observed = set()
    for args in (
        ["diff", "--name-only", BASELINE, "--"],
        ["diff", "--cached", "--name-only", BASELINE, "--"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        result = subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        )
        paths = set(result.stdout.splitlines())
        if "--cached" in args:
            assert not paths & set(PREPARATION)
        observed.update(paths)
    assert violations(root, changed=observed - set(PREPARATION)
                      - (set(LOCATOR_PATHS) - set(PATHS))
                      - (set(EDITORIAL_PATHS) - set(PATHS)) - (set(PORTABLE_PATHS) - set(PATHS))) == []
    assert_scope(root)
    for path in PATHS:
        staged = subprocess.run(["git", "show", ":" + path], cwd=root, capture_output=True)
        if staged.returncode:
            assert path in CREATES, path
        elif path in PRE and digest(staged.stdout) == PRE[path]:
            continue
        elif path in LOCATOR_PRE and digest(staged.stdout) == LOCATOR_PRE[path]:
            continue
        elif index_matches(root, path, staged.stdout):
            continue
        elif path == SELF:
            assert (oracle_digest(staged.stdout) == ORACLE_AST_SHA256
                    or (locator_matches(root, path, LOCATOR_PRE[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes())))
        else:
            assert (digest(staged.stdout) == POST[path]
                    or (locator_matches(root, path, POST[path])
                        and digest(staged.stdout) == digest((root / path).read_bytes()))), path
