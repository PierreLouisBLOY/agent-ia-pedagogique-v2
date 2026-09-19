"""Exact R5 worker successor; immutable predecessor views, no global guard bypass."""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from functools import lru_cache
from pathlib import Path

BASELINE = "20200dd895e072db618cf8478b403f9fe1866e7d"
ROOT = Path(__file__).resolve().parents[2]
SELF = "tests/support/r5_worker_guard.py"
PRE = {"backend/infrastructure/composition/bootstrap/conversation_worker.py":"13015550bd5f902184bb013a2bf6c35cc01f0afe06f2b5708ff77abb4041613a","backend/adapters/inbound/cli/local_browser.py":"078851614b0c40f1647d14555f1b0928caa9e4ff84155ac2a42f760c8bcbf17a","backend/adapters/outbound/generation/openai/mapping.py":"3d48f9538a6c7fe39b8992342c33350431946a2870bed085615c8f54365da3ed","tests/support/r5_scope_guard.py":"f1025b106ee7d852ff3e0fd5d657c028377ebf8af6afb6b193d3e188117018f3","tests/architecture/test_r5_product_boundary.py":"a85f08547221f848078d4253129765a46e05bb7444e99d83a96dbf02d5029104","backend/adapters/outbound/evidence/local_reference.py":"5e842d5a010e9a927bb0acaef16f7306d9bfac71c96efa33e04978e88e9489a0"}
SYMBOLS = {"backend/infrastructure/composition/bootstrap/conversation_worker.py":["read_private_packet","run_authorized_generation"],"backend/adapters/inbound/cli/local_browser.py":["main"],"backend/adapters/outbound/generation/openai/mapping.py":["build_openai_request"],"tests/support/r5_scope_guard.py":["source","exact","baseline_view","source_matches","index_matches","violations","PATHS","HISTORICAL_PATHS"],"tests/architecture/test_r5_product_boundary.py":["test_new_entry_has_no_network_credentials_provider_or_http_route"],"backend/adapters/outbound/evidence/local_reference.py":["SelectedLocalEvidenceSearch.search"]}
PATHS = ["backend/infrastructure/composition/bootstrap/conversation_worker.py","backend/adapters/inbound/cli/local_browser.py","backend/adapters/outbound/generation/openai/mapping.py","tests/support/r5_scope_guard.py","tests/architecture/test_r5_product_boundary.py","backend/adapters/outbound/generation/openai/r5_contract.py","backend/infrastructure/composition/factories/r5_generation.py","tests/support/r5_worker_guard.py","tests/support/r5_worker_synthetic.py","tests/unit/test_r5_worker_guard.py","tests/integration/test_r5_worker.py","architecture/adr/ADR-r5-exact-selection-worker.md","docs/development/R5_EXACT_SELECTION_WORKER.md","backend/adapters/outbound/evidence/local_reference.py"]
POST = {"backend/infrastructure/composition/bootstrap/conversation_worker.py":"0caa06ce7099b8571f2136cc42d2204ebf4e0bfa0f913923409ac80705c42554","backend/adapters/inbound/cli/local_browser.py":"e46d81e3d7e1530243a28d519044e0afc67c7604c4da7595176a4ba0e75975bf","backend/adapters/outbound/generation/openai/mapping.py":"c76176325a814aeac97924eb26caa6391f738ace86e890071757d9be554079eb","tests/support/r5_scope_guard.py":"7af7f75f4e3429d3bf1634f82fd011f4195ebfd3efc7aba5da71da713115589c","tests/architecture/test_r5_product_boundary.py":"547da760e2d09c2ad1d831a443bd2361a0cd0c8dc56df2b55de031e752b376b6","backend/adapters/outbound/generation/openai/r5_contract.py":"7f356578700542b553e13c811b386e63821b451e3e48433e3ba47dd30d966bac","backend/infrastructure/composition/factories/r5_generation.py":"be89418a37965749a7ca1ad2fe363f0647280ed3da9730c4c26c280c07fbbdfd","tests/support/r5_worker_synthetic.py":"d083f8a54f5431bc9416087f8a04002df2ec317989a0c5faf3161befc5c876ab","tests/unit/test_r5_worker_guard.py":"4d3202c92ceead28c39160e02393f3850af11b366c7c18f8c71d8be3e5cc3c03","tests/integration/test_r5_worker.py":"c35709e25060fd22070dfd517b20aed11afb1b43d9b15f506bd21bae168db12b","architecture/adr/ADR-r5-exact-selection-worker.md":"aa51b96cc9a1085cfd0c68efb8633d9e68ae6d18071ca7f676fa92903357fbb0","docs/development/R5_EXACT_SELECTION_WORKER.md":"4694b0d8fe60aace7fa35e48a9c80496efd09cd09941b5be09bf9358f0c1d3c6","backend/adapters/outbound/evidence/local_reference.py":"036c878a459fd2415a4663cbad89b275d4381089559f117491d66d7c2e76c835"}
SELF_SHA256 = "88c9a0838924b80ef325fdd62c9e356aa976c028c1922201ae73e8f3f2d57be4"


def source(root: Path, path: str) -> bytes:
    from tests.support.r3_portable_clone_guard import source_bytes
    return source_bytes(root, path)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical(path: str, raw: bytes) -> bytes:
    raw = raw.replace(b"\r\n", b"\n")
    if path == SELF:
        raw = re.sub(rb'^SELF_SHA256 = "[^"\n]+"\n', b"", raw, flags=re.M)
    if path == "tests/support/r5_scope_guard.py":
        raw = re.sub(rb'^(    worker_successor_sha256 = ")[^"\n]+("\n)', rb'\g<1>PIN\g<2>', raw, flags=re.M)
    return raw


@lru_cache(maxsize=32)
def baseline(path: str) -> bytes:
    assert path in PRE
    raw = subprocess.run(["git", "show", BASELINE + ":" + path], cwd=ROOT,
        capture_output=True, check=True).stdout
    assert hashlib.sha256(raw).hexdigest() == PRE[path] or digest(raw) == PRE[path]
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
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and name in allowed:
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
        return (expected == SELF_SHA256 and expected != "0" * 64
                and digest(canonical(SELF, source(ROOT, SELF))) == expected)
    except (OSError, ValueError):
        return False


def exact(root: Path, path: str) -> bool:
    try:
        raw = source(root, path)
        if path == SELF:
            return digest(canonical(path, raw)) == SELF_SHA256
        return (path in PATHS and digest(canonical(path, raw)) == POST.get(path)
                and (path not in PRE or outside_scope(path, raw) == outside_scope(path, baseline(path))))
    except (OSError, ValueError, SyntaxError, AssertionError):
        return False


def baseline_view(root: Path, path: str, *, expected: str = SELF_SHA256) -> bytes:
    if path in PRE and authenticated(expected=expected) and exact(root, path):
        return baseline(path)
    return source(root, path)


def index_matches(root: Path, path: str, raw: bytes) -> bool:
    return (path in PATHS and authenticated() and exact(root, path)
            and digest(raw) in {digest(source(root, path)), PRE.get(path)})


def violations(root: Path) -> list[str]:
    errors = [] if authenticated() else ["R5_WORKER_ORACLE_IDENTITY"]
    if set(POST) != set(PATHS) - {SELF}:
        errors.append("R5_WORKER_INVENTORY_IDENTITY")
    errors += ["R5_WORKER_IDENTITY:" + p for p in PATHS if not exact(root, p)]
    return errors
