"""Pinned R5 successor; preserves prior identities and rejects all unlisted changes."""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "1eca5e3c3a1029c4d72c3955871c8aa1c44169d3"
SELF = "tests/support/r5_scope_guard.py"
PRE = {"backend/modules/pedagogical_design/contracts/dto/conversation_draft.py":"367232b6f91e1b07ddff2a58a5300c69067b66ed98838d28eef193045c1c89ee","backend/modules/pedagogical_design/ports/outbound/conversation_generation.py":"4eb3c65a03138052bea74baf90a1d5d114663da0cf1610dc837d4b351707cb6e","backend/modules/pedagogical_design/application/commands/create_conversation_draft.py":"2b4e682fc9e44b88c16f77b8c9cd0b8cec1ce91d235d8c89423abc70112b10eb","backend/adapters/outbound/generation/conversation.py":"7a82ee159121a707d39586c73ec62d4729630a063c246af1d2be89484f264919","backend/infrastructure/composition/bindings/conversation_agents.py":"1ee5cf1f27fdb9554350be8f9486856fdd84b86ae57d471e589cfa952e2281b3","backend/infrastructure/composition/bindings/conversation_routing.py":"722ed3051b7fbd06cd1649dddf8681d812de66a18c0add7e50cb7ad8e5540c90","tests/support/r4_scope_guard.py":"3d0b6ae7a77a83659598c3df9f2a40c17b078c2ef24d0c3409ab8e8b8ea57f90","tests/support/r3_guard_oracle.py":"9a190ac8acbf2d4a6dbfb2995cb6ab030a6814c43312656a6e8961cf90ea8924","tests/support/r3_parse_observability_guard.py":"50fc58dc1b1065572e410ae04dc823f305d1b7839be31d7bdd1266fc266696b1","tests/support/r3_prepare_contract_alignment_guard.py":"1b697453ac24082947f443518ebe15e17ae7d34a2d63a426eb450985b75f6e3e","tests/support/r3_d3_scope_guard.py":"c61de3e278ce5865cbd775b0352541c2c509f39a3d417f6529e92d7b7220083f","tests/support/r3_portable_clone_guard.py":"7be3f790ab9c83308cee6d0128c8bb726e5638bd6aa2be68863c986490adfab5","tests/support/r3_editorial_correction_guard.py":"8ee1609f594a9ba3a217589d160c4a3d121c76bc8773a535c141ba362af58c3e","tests/architecture/test_r3_product_boundary.py":"eb87c89427cca05cc320a61c5fe73d0e8ff978566670c3bb8976415ec5a93bbb","tests/unit/test_r4_scope_guard.py":"75beb67839ff2f5fc19b38b41ea33c6f30408d854be1445fbb8538cf3fce4347","tests/support/conversation_fakes.py":"02fe2b724a0eafb06e3b4d8148ee272584810984636c27eb7127e97b7774ba17","tests/integration/test_conversation_job_lifecycle.py":"81e15845dd1d78f6214a54c084a3914cc308cae7199904ffd52bb849ec20f178"}
POST = {"backend/modules/pedagogical_design/contracts/dto/conversation_draft.py":"74b20e758e6f75b620d895d8a40b658364727adafcf306d5e2a4b4786898e9d0","backend/modules/pedagogical_design/ports/outbound/conversation_generation.py":"757b43e5f586d93ac22363e0b40f8637ffc2b6b66704d2075515cb3cb061ea00","backend/modules/pedagogical_design/application/commands/create_conversation_draft.py":"9389e67f692fcca9377920ab42af15e62b2f76e7814a5f2deb394a3b818e364d","backend/adapters/outbound/generation/conversation.py":"adce06b89d14e967121622174a35fdd2c43aa2879e04efd8eb12ba4a1d212170","backend/infrastructure/composition/bindings/conversation_agents.py":"faed74af8fe9b07898531310b44d2c0fe082906cc8d12859fc1799e8c02d280b","backend/infrastructure/composition/bindings/conversation_routing.py":"3425b7951bf18ecc2ec682f3922134932940bc02ef14cbee8c9db04a3d4f9534","tests/support/r4_scope_guard.py":"0c7333b32a32d063e5fc0b9874acb5a383ab82a8dee838b6c110fe83852e8dce","tests/support/r3_guard_oracle.py":"4dafa9dccd63d8a30a518fb5757bfbd1ab70361935bd9a80b3edb20bc01f5930","tests/support/r3_parse_observability_guard.py":"6cfd9afb207b7938a47ef173bb80881172c92668e8bde0955f777c5a417afcbf","backend/adapters/outbound/evidence/local_reference.py":"5e842d5a010e9a927bb0acaef16f7306d9bfac71c96efa33e04978e88e9489a0","backend/infrastructure/composition/factories/local_reference.py":"2da29c8a6215ca3196b3097369d192b545d5d831835f0db28f51d438b3f17880","backend/adapters/inbound/cli/local_references.py":"078da24f5f1071497cfe8d8608431daae387482289d4934201823c99192ae1a0","tests/integration/test_r5_local_reference.py":"e2e98b3ea232fb524f420b07d53b38bab1f23d8ef523ecb49620c7a5caf4aefc","tests/unit/test_r5_scope_guard.py":"ab631dc88672193187a4cd676cc3050ddedb9562bc431df4dd7d848967f59ca8","tests/architecture/test_r5_product_boundary.py":"a85f08547221f848078d4253129765a46e05bb7444e99d83a96dbf02d5029104","architecture/adr/ADR-r5-local-reference-provenance.md":"3f2ddfbaa87977154601750eb0a51ae7f31c83cc74de878789ed24231c22b12c","docs/development/R5_REAL_REFERENCES.md":"c0c125b40a99b3d08a1543524a606acd9cb11af04dc889503f289cddb9d70f34","tests/support/r3_prepare_contract_alignment_guard.py":"894ffb34e71160bda89e10ae6c685b8a3e098e9868749633752bbc9b766216f1","tests/support/r3_d3_scope_guard.py":"27f686fcd19d98241a135ecd09227f9ea679fcf322cd2c4508dd4c6c930e8db2","tests/support/r3_portable_clone_guard.py":"c49d29577b361da3fd8fe6758c851c82f5dd2d8f857d2acef41bdaf0ff70884c","tests/support/r3_editorial_correction_guard.py":"cc98afaed47e6d45736d953a0494b13d43f1d4c32019492ffe0ef62c616c8b77","tests/architecture/test_r3_product_boundary.py":"7c0691bc458ece633f5ae851c9214e7fe5681f588eb8c0e1311575c4dac3c7d8","tests/unit/test_r4_scope_guard.py":"a8d318eddb2f109ef517cb3a68ccb11ca3526f1ba824f2b7ef1531b7128256f0","tests/support/conversation_fakes.py":"596a52914dbdb7de36a1af4e407b3ff0aa18fefd97131b1eb27f608424758eac","tests/unit/test_conversation_wait.py":"757004dc00a448c7421fa16a120e50a1339dca6f1d6c1cc079b18ed75d38349a","tests/integration/test_conversation_job_lifecycle.py":"7bae1ac064fa05405404e44676f29019833337addae42298858de2118d8c906d"}
SYMBOLS = {"backend/modules/pedagogical_design/contracts/dto/conversation_draft.py":["ConversationDraft.__post_init__","REFERENCE_PROVENANCE_CONTRACT","SYNTHETIC_REFERENCE_LABEL","LOCAL_REFERENCE_LABEL"],"backend/modules/pedagogical_design/ports/outbound/conversation_generation.py":["ConversationPreparationPort"],"backend/modules/pedagogical_design/application/commands/create_conversation_draft.py":["CreateConversationDraft.prepare"],"backend/adapters/outbound/generation/conversation.py":["ConversationGenerationAdapter.__init__","ConversationGenerationAdapter.generate","ConversationGenerationAdapter.prepare","NoGenerationDispatch"],"backend/infrastructure/composition/bindings/conversation_agents.py":["ConversationAgentBindings.__init__","ConversationAgentBindings.execute"],"backend/infrastructure/composition/bindings/conversation_routing.py":["ConversationCompletion.evaluate","execute_conversation_plan"],"tests/support/r4_scope_guard.py":["read","index_matches","violations"],"tests/support/r3_guard_oracle.py":["active_inventory"],"tests/support/r3_parse_observability_guard.py":["active_source_matches","patch_violations"],"tests/support/r3_prepare_contract_alignment_guard.py":["successor_violations"],"tests/support/r3_d3_scope_guard.py":["violations"],"tests/support/r3_portable_clone_guard.py":["violations"],"tests/support/r3_editorial_correction_guard.py":["violations"],"tests/architecture/test_r3_product_boundary.py":["test_exact_closed_inventory_owners_and_protected_identities"],"tests/unit/test_r4_scope_guard.py":["test_each_r4_source_mutation_is_rejected"],"tests/support/conversation_fakes.py":["http_call","wait_terminal"],"tests/integration/test_conversation_job_lifecycle.py":["collect","test_corrective_private_channel_preserves_preparse_usage_and_no_replay"]}
PATHS = tuple(["backend/modules/pedagogical_design/contracts/dto/conversation_draft.py","backend/modules/pedagogical_design/ports/outbound/conversation_generation.py","backend/modules/pedagogical_design/application/commands/create_conversation_draft.py","backend/adapters/outbound/generation/conversation.py","backend/infrastructure/composition/bindings/conversation_agents.py","backend/infrastructure/composition/bindings/conversation_routing.py","tests/support/r4_scope_guard.py","tests/support/r3_guard_oracle.py","tests/support/r3_parse_observability_guard.py","backend/adapters/outbound/evidence/local_reference.py","backend/infrastructure/composition/factories/local_reference.py","backend/adapters/inbound/cli/local_references.py","tests/integration/test_r5_local_reference.py","tests/unit/test_r5_scope_guard.py","tests/architecture/test_r5_product_boundary.py","tests/support/r5_scope_guard.py","architecture/adr/ADR-r5-local-reference-provenance.md","docs/development/R5_REAL_REFERENCES.md","tests/support/r3_prepare_contract_alignment_guard.py","tests/support/r3_d3_scope_guard.py","tests/support/r3_portable_clone_guard.py","tests/support/r3_editorial_correction_guard.py","tests/architecture/test_r3_product_boundary.py","tests/unit/test_r4_scope_guard.py","tests/support/conversation_fakes.py","tests/unit/test_conversation_wait.py","tests/integration/test_conversation_job_lifecycle.py"])
SELF_SHA256 = "aee6c0dc70529120635149acf0dd053eac832f1c74db5278307fcab650c04e68"


def source(root: Path, path: str) -> bytes:
    from tests.support.r3_portable_clone_guard import source_bytes
    return source_bytes(root, path)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical(path: str, raw: bytes) -> bytes:
    raw = raw.replace(b"\r\n", b"\n")
    if path == SELF:
        raw = re.sub(rb'^SELF_SHA256 = "[^"\n]+"\n', b"", raw, flags=re.M)
    if path == "tests/support/r4_scope_guard.py":
        raw = re.sub(rb'^(    r5_successor_sha256 = ")[^"\n]+("\n)', rb'\g<1>PIN\g<2>', raw, flags=re.M)
    return raw


@lru_cache(maxsize=32)
def baseline(path: str) -> bytes:
    assert path in PRE
    raw = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT,
        capture_output=True, check=True).stdout
    assert digest(raw) == PRE[path]
    return raw


@lru_cache(maxsize=128)
def outside_scope(path: str, raw: bytes) -> str:
    tree = ast.parse(raw)
    allowed = set(SYMBOLS[path])
    def strip(nodes, prefix=""):
        result = []
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            name = prefix + getattr(node, "name", "")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and name in allowed:
                continue
            if isinstance(node, ast.ClassDef):
                node.body = strip(node.body, name + ".")
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
                if all(isinstance(t, ast.Name) and prefix + t.id in allowed for t in targets):
                    continue
            result.append(node)
        return result
    tree.body = strip(tree.body)
    return ast.dump(tree)


def authenticated(*, expected: str = SELF_SHA256) -> bool:
    try:
        return (len(expected) == 64 and expected == SELF_SHA256
                and digest(canonical(SELF, source(ROOT, SELF))) == expected)
    except (OSError, ValueError):
        return False


def exact(root: Path, path: str) -> bool:
    try:
        raw = source(root, path)
        if path == SELF:
            return digest(canonical(path, raw)) == SELF_SHA256
        return (digest(canonical(path, raw)) == POST.get(path) and
            (path not in PRE or outside_scope(path, raw) == outside_scope(path, baseline(path))))
    except (OSError, ValueError, SyntaxError, AssertionError):
        return False


def baseline_view(root: Path, path: str, *, expected: str = SELF_SHA256) -> bytes:
    if path in PRE and authenticated(expected=expected) and exact(root, path):
        return baseline(path)
    return source(root, path)


def source_matches(root: Path, path: str, historical: str) -> bool:
    if path not in PRE or not authenticated() or not exact(root, path):
        return False
    raw = baseline(path)
    return historical in {digest(raw), hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()}


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    return (path in PATHS and authenticated() and exact(root, path)
            and digest(raw) in {digest(source(root, path)), PRE.get(path)})


def violations(root: Path, *, changed: set[str] | None = None) -> list[str]:
    errors = [] if authenticated() else ["R5_ORACLE_IDENTITY"]
    if set(POST) != set(PATHS) - {SELF}:
        errors.append("R5_INVENTORY_IDENTITY")
    errors += ["R5_IDENTITY:" + p for p in PATHS if not exact(root, p)]
    if changed is not None:
        errors += ["R5_UNAPPROVED:" + p for p in sorted(changed - set(PATHS))]
        errors += ["R5_MISSING:" + p for p in sorted(set(PATHS) - changed)]
    return errors
