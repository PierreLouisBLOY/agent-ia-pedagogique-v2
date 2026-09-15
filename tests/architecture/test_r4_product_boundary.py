import ast
import subprocess
from pathlib import Path

from backend.adapters.inbound.api.routes import ROUTE_SPECS
from tests.support import r4_scope_guard as guard
from tests.support.r3_guard_oracle import PREPARATION, R3_ROUTES

ROOT = Path(__file__).resolve().parents[2]


def test_exact_r4_scope_routes_and_historical_preservation():
    assert guard.violations(ROOT) == []
    assert ROUTE_SPECS == R3_ROUTES + guard.R4_ROUTES
    changed = set()
    for args in (["diff", "--name-only", guard.BASELINE, "--"],
                 ["diff", "--cached", "--name-only", guard.BASELINE, "--"],
                 ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
        changed.update(result.stdout.splitlines())
    assert guard.violations(ROOT, changed=changed - set(PREPARATION)) == []


def test_r4_business_and_http_boundaries_no_provider_or_direct_storage():
    from tests.architecture.test_local_browser_product_boundary import source_boundary_violations
    for path in guard.PATHS:
        if not path.startswith("backend/") or not path.endswith(".py"):
            continue
        source = (ROOT / path).read_text("utf-8")
        assert source_boundary_violations(source, path) == []
        if path in guard.PRE:
            continue
        tree = ast.parse(source)
        modules = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        modules |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not any(m.startswith(("openai", "anthropic", "requests", "httpx")) for m in modules)
        assert "os.environ" not in source and "getenv(" not in source
        if path.startswith("backend/modules/"):
            assert not any(m.startswith(("backend.adapters", "backend.infrastructure", "backend.agent_runtime",
                "os", "pathlib", "sqlite3", "socket", "http", "subprocess")) for m in modules)


def test_registry_no_implicit_promotion_export_and_old_capabilities_unchanged():
    for path in ("backend/agent_runtime/registry/capabilities.py", "backend/agent_runtime/registry/access_matrix.py",
                 "backend/modules/validation_control/domain/policies/assessment_checks.py",
                 "backend/agent_runtime/gates/engine.py"):
        old = subprocess.run(["git", "show", f"{guard.BASELINE}:{path}"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        assert guard.digest(old) == guard.digest((ROOT / path).read_bytes())
