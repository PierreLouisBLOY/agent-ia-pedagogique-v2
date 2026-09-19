import ast
import hashlib
from pathlib import Path

from backend.adapters.inbound.api.routes import ROUTE_SPECS
from backend.adapters.outbound.system.r3_job import UnapprovedR3Job
from tests.architecture.test_local_browser_product_boundary import source_boundary_violations
from tests.support.r3_guard_oracle import (
    BACKEND_CREATES,
    PRE_HASHES,
    R3_BASELINE,
    R3_PATHS,
    R3_ROUTES,
    READ_ONLY,
    active_inventory,
    assert_guard_scope,
    git_bytes,
    hash_variants,
)

ROOT = Path(__file__).resolve().parents[2]


def test_exact_closed_inventory_owners_and_protected_identities():
    from tests.support.r3_parse_observability_guard import active_source_matches
    from tests.support.r3_prepare_contract_alignment_guard import PRODUCERS
    from tests.support.r5_scope_guard import baseline_view as r5_view

    assert len(R3_PATHS) == len(set(R3_PATHS)) == 59
    assert len(PRE_HASHES) == 15 and len(BACKEND_CREATES) == 23
    assert active_inventory(ROOT) == []
    from tests.support.r4_scope_guard import R4_ROUTES
    assert ROUTE_SPECS == R3_ROUTES + R4_ROUTES and len(ROUTE_SPECS) == 22
    for path, digest in PRE_HASHES.items():
        assert digest in hash_variants(git_bytes(ROOT, R3_BASELINE, path))
    for path, digest in READ_ONLY.items():
        assert active_source_matches(ROOT, path, digest)
        if path not in PRODUCERS:
            assert hashlib.sha256(r5_view(ROOT, path)).hexdigest() == digest
    assert_guard_scope(ROOT)


def test_new_business_modules_have_no_provider_storage_or_agent_authority():
    for path in BACKEND_CREATES:
        source = (ROOT / path).read_text("utf-8")
        assert source_boundary_violations(source, path) == []
        if not path.startswith("backend/modules/"):
            continue
        tree = ast.parse(source)
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        for name in names:
            assert not name.startswith(("backend.agent_runtime", "backend.adapters", "backend.infrastructure",
                "openai", "anthropic", "sqlite3", "pathlib", "os", "socket", "http", "subprocess"))
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not calls & {"open", "eval", "exec", "__import__"}
    assert UnapprovedR3Job().poll() is None


def test_no_r3_live_grant_route_export_promotion_or_credential_discovery():
    for path in BACKEND_CREATES:
        source = (ROOT / path).read_text("utf-8")
        assert "getenv(" not in source and "os.environ" not in source
        assert "CAP-A02" not in source and "CAP-A03" not in source
    from tests.support.r4_scope_guard import R4_ROUTES
    assert ROUTE_SPECS == R3_ROUTES + R4_ROUTES
    assert all("export" not in p and "promot" not in p for _, p, _ in ROUTE_SPECS[:16])
