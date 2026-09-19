"""Exact editorial successor oracle; historical identity tables are never rewritten."""
import ast
import hashlib
import subprocess
from functools import lru_cache
from pathlib import Path

BASELINE = "ef0cba51d009cb25443da146285eee5046f06e25"
SOURCE_MANIFEST = "c70fe5ffde64239f363dc190bd386e1444793b6b652cb062ee881e568d7992f8"
SELF = "tests/support/r3_editorial_correction_guard.py"
PRE = {
    "backend/modules/pedagogical_design/contracts/dto/assessment_revision.py": "4e986220366addcdbe301b50560ce63ce87672d9d6f585823257856d030d59d0",
    "backend/modules/pedagogical_design/domain/policies/assessment_revision.py": "08d5a954c6659aad1e5ee564a80bedef07e61a13fa85d5c2d0952697e5dba7b3",
    "backend/modules/work_orchestration/contracts/dto/r3_review_modify.py": "7eb40627317d8390f3a3591cc25a45706cb49b1ea68669adfec571156f307edf",
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": "67dddde182941f2649e312e0dba322188a8bd890b1d499b856af8946b6346664",
    "backend/infrastructure/composition/factories/r3_review_modify.py": "cced82aebc0300dc8399db26a4a60b50b7431ff08f0d62834213d5abab4b724d",
    "backend/modules/validation_control/domain/policies/assessment_checks.py": "aa141e63d04b146d96eb6ecd78ca42c1c03040d24a3aa3a415441ea7fdd4f0bd",
    "backend/modules/validation_control/application/commands/validate_assessment.py": "b81c69fdebbf46561c918e560f3d834e4c855545f42fb429efbe54c89fc59ecd",
    "backend/modules/validation_control/ports/inbound/validate_assessment.py": "77db21b39c509483edbc12b51047c2eab84897c997db4b9486f9fe622c68a3bf",
    "backend/modules/pedagogical_design/application/commands/revise_assessment.py": "034ceebe964db9719d26e02587d84bc2c30da017848ea5858d2265f29f117e2e",
    "backend/modules/pedagogical_design/ports/inbound/revise_assessment.py": "d8667aaf9eff0de5b1a98433750610369ce9fa3e33848f130b95f6bbbee33271",
    "tests/support/r3_guard_oracle.py": "4114c596686d219d87860d571f55d8fb2d9ba00aa13c2aadda1c8a7417cd1861",
    "tests/support/r3_locator_materialization_guard.py": "178cfaaf91defce2aa7fcc9d524ae96d4192450ebf6c2aacfe221274cce4bd4d",
    "tests/support/r3_cap_a01_guard.py": "e0c2d780828b735072ff3e424118f6592d12a28eb663a41c6c07598aa9a5c374",
    "tests/support/r3_serializer_8192_guard.py": "647fe01272e1e23b4b0d87d5eb0e61ad493c777f0e007ab6b9afe686ddfc5be0",
    "tests/support/r3_prepare_contract_alignment_guard.py": "223719d17d0459ad944c443ecbce7eed39a58d3ffca45c9432f0144538439815",
    "tests/support/r3_parse_observability_guard.py": "7e487477d931ddb8cb316875494449d60f354216a71d11b3455f782aa49e07c3",
    "tests/unit/test_r3_cap_a01_targeted.py": "9b7b61e88d337431166387c8014641803e7b5c366b721cceea1e01b33942bf16",
    "tests/unit/test_r3_locator_materialization.py": "9ad0c3346276200ac0f5759443bba193be65f34cb7618358d43ac5108c2e25d4",
    "tests/unit/test_r3_prepare_serialization.py": "48ce1dede8196b8aef6addb2f821633d21b02f50655cf2d0a488f063d37ca563",
    "tests/unit/test_r3_prepare_contract_alignment.py": "53e3bb00500c133d32a88778f244fdaf1e4077faec986a6b409516c94312b2d3",
    "tests/unit/test_r3_parse_observability.py": "398f6ba0e94c84d5bd16e0f502c6c5e4292f19222ee09ad750cb998b46979dd3",
    "backend/adapters/outbound/persistence/conversation_memory.py": "6a6c1dbbe0e29315b38a23087dfeb7885ca64775834de2514fc3acef3b97ae45",
    "backend/modules/work_orchestration/ports/outbound/r3_store.py": "ae02ce57302cfef67486103d3be29db024c5a66758e6312cca50606e84c206c3"
}
CREATES = [
    "tests/unit/test_r3_editorial_corrections.py",
    "tests/unit/test_r3_editorial_validation_scope.py",
    "tests/integration/test_r3_editorial_corrections.py",
    "tests/architecture/test_r3_editorial_correction_boundary.py",
    "tests/support/r3_editorial_correction_guard.py",
    "architecture/adr/ADR-r3-explicit-editorial-corrections.md",
    "docs/development/phase_12_18_h2_r3_editorial_corrections/CONTRACT_PROPOSAL.json",
    "backend/modules/validation_control/contracts/dto/editorial_scope.py"
]
PATHS = tuple(PRE) + tuple(CREATES)
SYMBOLS = {
    "backend/modules/pedagogical_design/contracts/dto/assessment_revision.py": [
        "EditorialCorrectionPlan"
    ],
    "backend/modules/pedagogical_design/domain/policies/assessment_revision.py": [
        "assemble_editorial_corrections"
    ],
    "backend/modules/work_orchestration/contracts/dto/r3_review_modify.py": [
        "R3Command.__post_init__",
        "R3Command.fingerprint"
    ],
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": [
        "R3ReviewModifyService.__init__",
        "R3ReviewModifyService.execute",
        "R3ReviewModifyService._validation",
        "R3ReviewModifyService.close"
    ],
    "backend/infrastructure/composition/factories/r3_review_modify.py": [
        "build_r3"
    ],
    "backend/modules/validation_control/domain/policies/assessment_checks.py": [
        "check_rule",
        "evaluate_checks"
    ],
    "backend/modules/validation_control/application/commands/validate_assessment.py": [
        "ValidateAssessmentCommand.execute"
    ],
    "backend/modules/validation_control/ports/inbound/validate_assessment.py": [
        "ValidateAssessment.execute"
    ],
    "backend/modules/pedagogical_design/application/commands/revise_assessment.py": [
        "ReviseAssessmentCommand.execute_editorial"
    ],
    "backend/modules/pedagogical_design/ports/inbound/revise_assessment.py": [
        "ReviseAssessment.execute_editorial"
    ],
    "backend/adapters/outbound/persistence/conversation_memory.py": [
        "ConversationMemoryStore.__init__",
        "ConversationMemoryStore.r3_complete",
        "ConversationMemoryStore.r3_editorial_scope",
        "ConversationMemoryStore.r3_clear"
    ],
    "backend/modules/work_orchestration/ports/outbound/r3_store.py": [
        "R3Store.r3_complete",
        "R3Store.r3_editorial_scope"
    ],
    "tests/support/r3_guard_oracle.py": [
        "active_inventory"
    ],
    "tests/support/r3_locator_materialization_guard.py": [
        "authenticated",
        "source_matches",
        "prior_scope_bytes",
        "violations",
        "assert_scope",
        "assert_git_state"
    ],
    "tests/support/r3_cap_a01_guard.py": [
        "assert_git_state"
    ],
    "tests/support/r3_serializer_8192_guard.py": [
        "assert_git_state"
    ],
    "tests/support/r3_prepare_contract_alignment_guard.py": [
        "assert_successor_git_state"
    ],
    "tests/support/r3_parse_observability_guard.py": [
        "patch_violations",
        "assert_patch_git_state"
    ],
    "tests/unit/test_r3_cap_a01_targeted.py": [
        "test_no_business_predicate_or_status_is_weakened",
        "test_each_targeted_successor_identity_is_closed"
    ],
    "tests/unit/test_r3_locator_materialization.py": [
        "test_every_successor_file_mutation_is_rejected"
    ],
    "tests/unit/test_r3_prepare_serialization.py": [
        "test_each_successor_source_mutation_is_rejected"
    ],
    "tests/unit/test_r3_prepare_contract_alignment.py": [
        "copied_sources"
    ],
    "tests/unit/test_r3_parse_observability.py": [
        "test_every_patch_source_mutation_is_rejected"
    ]
}
POST = {
    "tests/unit/test_r3_editorial_validation_scope.py": "7a864f3547a4bdd44fac91e02fe4e90f2734999a862cd7863aff271c3685bf6a",
    "tests/support/r3_locator_materialization_guard.py": "8435707018e817f2495a23d9b452c961d97b1f0f91786b05d89c1108dbdd0ea0",
    "backend/modules/validation_control/ports/inbound/validate_assessment.py": "73fdcac5dd767cec5553d98e02c52a5b34cd9aa57832b3d86591704e06e32e37",
    "backend/adapters/outbound/persistence/conversation_memory.py": "9eaae7f7f2b72278014f028cf19cada94b213988c3147be64f96c41909481c08",
    "tests/unit/test_r3_cap_a01_targeted.py": "2581379d2017472bb9ce83e0e9d0dc3dcb0749dc0e27303b596d3a8f03ca5616",
    "tests/architecture/test_r3_editorial_correction_boundary.py": "5b425bdeca7680d5943a853989a582469c134698d60e4675d85696b5fc5becef",
    "tests/unit/test_r3_parse_observability.py": "cb649aee751ed222f2936df814410fa3f6630d00cbab8a8daec3cd8daacc918e",
    "tests/support/r3_guard_oracle.py": "5334562b585d6f3dc15de846a5df55e987052b62f9bd16b401cd583db83947fb",
    "architecture/adr/ADR-r3-explicit-editorial-corrections.md": "b20960c05eee7f48cb04741467169b53b1aa3e8351d859e4355c3026c9f0ed50",
    "backend/modules/pedagogical_design/ports/inbound/revise_assessment.py": "a8ebce04d55b523c80ed914d0c84b034cd4983895c2d49cd2a077e4dc6440271",
    "backend/modules/pedagogical_design/application/commands/revise_assessment.py": "e24640bccc702e771a1fafb87f306b82ea336a7b4e2ac94940dc704e37509a2a",
    "tests/unit/test_r3_editorial_corrections.py": "ac3f3b06927f5110a2b924c133c50d8318f60f8151b6648e6e8246c1bdcfc48b",
    "backend/modules/validation_control/contracts/dto/editorial_scope.py": "4a94db413acfcf4f80a3462423f48a7ce331f8392eb598b106173421c3c93724",
    "tests/unit/test_r3_prepare_serialization.py": "d09cdc1912b8b2e450d0e4256a163d07ccdf3a8fc39247dbd20442008cf0f90a",
    "tests/support/r3_parse_observability_guard.py": "69c182f5b883b795c4dccda58db2d7dd9fd96e447e8612c39324e1984e622287",
    "backend/modules/work_orchestration/ports/outbound/r3_store.py": "856875a8c7813e603d1dec355dd6b27e259816f984c054a2f34331b892dd94c8",
    "tests/support/r3_prepare_contract_alignment_guard.py": "59db841b1ef88f1594e1404ee906ff66ba4ff979901b477e0d1c814120d5f5ad",
    "tests/support/r3_cap_a01_guard.py": "f79025454ea7903043d6f249fc7c884911ca040a412c831f6406e34846ca2ddc",
    "backend/modules/validation_control/application/commands/validate_assessment.py": "421b26f224d9e0c63d51ba345a57ace8d09830c002cb76339548956714abf638",
    "backend/modules/work_orchestration/contracts/dto/r3_review_modify.py": "bb6b39a723da2b765216c3c386c22cb8c1a7a0619417af44c7af5c3dfc41b45c",
    "backend/modules/pedagogical_design/domain/policies/assessment_revision.py": "6eae51b9eed640ce0f51b54eecb99097f89dafb082a1894f0a9c03652d0f33fe",
    "tests/integration/test_r3_editorial_corrections.py": "7ae6025039319e2310ea4ecc36c54f23b487c8a6b5a55389a704c7dfd475ecf9",
    "backend/modules/work_orchestration/application/services/r3_review_modify.py": "98a2368e21617978f3b2be67fdc4d8155c6dac7781dd2b14a98066bd4a776d3e",
    "backend/infrastructure/composition/factories/r3_review_modify.py": "43da66848712973bbae67342d44ebb87685b3c904ef50facb74b3d2565a15ca4",
    "backend/modules/validation_control/domain/policies/assessment_checks.py": "a86263d56df152fc2c94a63f719e8ff9645977d3401edae3f17e8a91cc4dd97b",
    "docs/development/phase_12_18_h2_r3_editorial_corrections/CONTRACT_PROPOSAL.json": "46ef8f0e53bb080eaf04a87e788e1b9558cf0eb58afc886e6965296e98146fe1",
    "backend/modules/pedagogical_design/contracts/dto/assessment_revision.py": "9044270869537cf76415d492a41bb12cb45800a264583474de2f6d191639ba88",
    "tests/unit/test_r3_locator_materialization.py": "f76701b1abf7ceb7112ec36b3f178c6d49b2b0fc36dadffb5db7fb2d109a2396",
    "tests/unit/test_r3_prepare_contract_alignment.py": "35d01d8bdfa6ff9495c868c0d9cb691e7bf67a386e34d0ccab48816abed93a12",
    "tests/support/r3_serializer_8192_guard.py": "0f9419e77c6d771d5e0b6463c90874a32ca61fb3fca1a1e0bdd93f8c24309a34"
}
ORACLE_SHA256 = "99a557c27a9b08afe3918897a28c4ba6273ca1348f6c15fd57fd89a78d9669ec"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def oracle_digest(raw: bytes) -> str:
    lines = raw.replace(b"\r\n", b"\n").splitlines(keepends=True)
    return digest(b"".join(line for line in lines if not line.startswith(b"ORACLE_SHA256 = ")))


def authenticated(root: Path) -> bool:
    from tests.support.r3_portable_clone_guard import authenticated as portable_authenticated

    successor_sha256 = "2f1b74d19c7c2f1f18e3e700ba9b9a8ec6c848a94b2c741d4d2d3aa3263af115"
    if portable_authenticated(root, expected=successor_sha256):
        return True
    try:
        return oracle_digest((root / SELF).read_bytes()) == ORACLE_SHA256
    except OSError:
        return False


def source_matches(root: Path, path: str, historical: str) -> bool:
    from tests.support.r3_portable_clone_guard import source_matches as portable_matches

    file = root / path
    if portable_matches(root, path, historical):
        return True
    return (path in PRE and historical == PRE[path] and authenticated(root)
            and file.is_file() and (digest(file.read_bytes()) == POST.get(path)
                                   or portable_matches(root, path, POST.get(path, ""))))


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    from tests.support.r3_portable_clone_guard import index_matches as portable_index_matches

    if portable_index_matches(root, path, raw):
        return True
    return (path in PRE and source_matches(root, path, PRE[path])
            and digest(raw) in {PRE[path], POST[path]})


@lru_cache(maxsize=64)
def baseline_bytes(path: str) -> bytes:
    assert path in PRE
    root = Path(__file__).resolve().parents[2]
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=root,
                         check=True, capture_output=True).stdout
    assert digest(raw) == PRE[path], path
    return raw


def baseline_view(root: Path, path: str) -> bytes:
    from tests.support.r3_portable_clone_guard import baseline_view as portable_view

    raw = portable_view(root, path)
    return baseline_bytes(path) if path in PRE and source_matches(root, path, PRE[path]) else raw


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_d3_scope_guard import violations as d3_violations
    from tests.support.r4_scope_guard import PATHS as R4_PATHS

    assert len(PRE) == 23 and len(CREATES) == 8 and len(set(PATHS)) == 31
    assert set(POST) == set(PATHS) - {SELF}
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS
    from tests.support.r3_portable_clone_guard import source_matches as portable_matches
    from tests.support.r3_portable_clone_guard import violations as portable_violations

    errors = d3_violations(root) + portable_violations(root)
    for path, expected in POST.items():
        file = root / path
        if (not file.is_file() or digest(file.read_bytes()) != expected) and not portable_matches(root, path, expected):
            errors.append("EDITORIAL_IDENTITY:" + path)
    if not authenticated(root):
        errors.append("EDITORIAL_ORACLE_IDENTITY")
    if changed is not None:
        errors += ["EDITORIAL_MISSING:" + p for p in sorted(set(PATHS) - changed)]
        from tests.support.r5_scope_guard import PATHS as R5_PATHS
        from tests.support.r5_scope_guard import violations as r5_violations
        errors += r5_violations(root)
        errors += ["EDITORIAL_UNAPPROVED:" + p for p in sorted(changed - set(D3_PATHS) - set(PATHS) - set(PORTABLE_PATHS) - set(R4_PATHS) - set(R5_PATHS))]
    return errors


def outside_scope(raw: bytes, path: str) -> str:
    tree = ast.parse(raw)
    guard = path.startswith("tests/support/")
    def strip(nodes, prefix=""):
        kept = []
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)) and not guard:
                continue
            name = prefix + getattr(node, "name", "")
            if name in SYMBOLS[path]:
                if guard:
                    node.body = [ast.Pass()]  # Keep every historical guard signature.
                else:
                    continue
            elif isinstance(node, ast.ClassDef):
                node.body = strip(node.body, name + ".")
            kept.append(node)
        return kept
    tree.body = strip(tree.body)
    return ast.dump(tree)


def assert_predicates(root: Path) -> None:
    path = "backend/modules/validation_control/domain/policies/assessment_checks.py"
    before = ast.parse(baseline_bytes(path))
    after = ast.parse((root / path).read_bytes())
    old = {n.name: n for n in before.body if isinstance(n, ast.FunctionDef)}
    new = {n.name: n for n in after.body if isinstance(n, ast.FunctionDef)}
    rule = new["check_rule"]
    assert rule.args.kwonlyargs[-1].arg == "editorial_scope"
    assert ast.dump(rule.args.kw_defaults[-1]) == ast.dump(ast.Constant(None))
    rule.args.kwonlyargs.pop()
    rule.args.kw_defaults.pop()
    branch = next(n for n in rule.body if isinstance(n, ast.If)
                  and ast.unparse(n.test) == "index == 14")
    expected = ast.parse(
        'if editorial_scope is not None or object_data(data["lineage"]).get("source_capability") is None:\n'
        '    return verify_editorial_scope(editorial_scope, parent=parent, candidate=data)'
    ).body[0]
    assert ast.dump(branch.body[0]) == ast.dump(expected)
    branch.body.pop(0)
    assert ast.dump(old["check_rule"]) == ast.dump(rule)
    # The only evaluate_checks change is parameter addition and forwarding.
    forward = new["evaluate_checks"]
    assert forward.args.kwonlyargs[-1].arg == "editorial_scope"
    assert ast.dump(forward.args.kw_defaults[-1]) == ast.dump(ast.Constant(None))
    forward.args.kwonlyargs.pop()
    forward.args.kw_defaults.pop()
    calls = [n for n in ast.walk(forward) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "check_rule"]
    assert len(calls) == 1
    kw = calls[0].keywords.pop()
    assert kw.arg == "editorial_scope" and ast.unparse(kw.value) == "editorial_scope"
    assert ast.dump(old["evaluate_checks"]) == ast.dump(forward)
    for name in old.keys() - {"check_rule", "evaluate_checks"}:
        assert ast.dump(old[name]) == ast.dump(new[name]), name


def assert_scope(root: Path) -> None:
    from tests.support.r3_portable_clone_guard import assert_scope as assert_portable_scope
    from tests.support.r3_portable_clone_guard import baseline_view as portable_view

    assert_portable_scope(root)
    assert violations(root) == []
    for path in PRE:
        before, after = baseline_bytes(path), portable_view(root, path)
        assert outside_scope(before, path) == outside_scope(after, path), path
        if not path.startswith("tests/support/"):
            old_imports = {ast.dump(n) for n in ast.parse(before).body
                           if isinstance(n, (ast.Import, ast.ImportFrom))}
            # Splitting an import to add a symbol is legitimate, removing old names is not.
            def imports(raw):
                return {(getattr(n, "module", None), a.name, a.asname)
                        for n in ast.parse(raw).body if isinstance(n, (ast.Import, ast.ImportFrom))
                        for a in n.names}
            assert imports(before) <= imports(after), (path, old_imports)
    assert_predicates(root)


def assert_git_state(root: Path) -> None:
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_d3_scope_guard import violations as d3_violations

    assert len(D3_PATHS) == 46
    assert d3_violations(root) == []
    from tests.support.r3_guard_oracle import PREPARATION
    from tests.support.r3_portable_clone_guard import assert_git_state as assert_portable_git_state

    assert_portable_git_state(root)
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
        elif index_matches(root, path, staged.stdout):
            continue
        elif path == SELF:
            assert oracle_digest(staged.stdout) == ORACLE_SHA256
            assert digest(staged.stdout) == digest((root / path).read_bytes())
        else:
            allowed = {POST[path]}
            if path in PRE:
                allowed.add(PRE[path])
            assert digest(staged.stdout) in allowed, path
