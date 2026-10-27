"""Synthetic authorities and transport at existing ports; real normal composition."""

import copy
import json
from contextlib import contextmanager
from datetime import UTC, datetime

from backend.adapters.outbound.generation.openai.p0_finite_policy import ROLES
from backend.adapters.outbound.generation.openai.p0_normal_policy import canonical, sha
from backend.adapters.outbound.generation.openai.p0_product_ledger import P0ProductLedger
from backend.adapters.outbound.openai.contracts import (
    OpenAIIncompleteReason,
    OpenAIResponsesResponse,
    OpenAIResponseStatus,
    OpenAIResponseUsage,
)
from backend.infrastructure.composition.factories import p0_finite_chain as finite_factory
from backend.infrastructure.composition.factories.p0_local_search import ScopedApplicationSearch
from backend.infrastructure.filesystem import capture_secure_path
from tests import normal_on_323a_fixture as f
from tests.test_codesign_global_324 import Search


def configuration(root, *, adopted=True):
    path, target, saved, receipts = f.configuration(root)
    envelope = json.loads(path.read_bytes())
    permission = json.loads(open(envelope["permission"]["path"], encoding="utf-8").read())
    assert permission["max_calls"] == 1  # Old CREATE right is never expanded.
    ledger = P0ProductLedger(root=receipts, permission=permission)
    with ledger.locked():
        assert ledger.slots() == []
    lock = receipts / (ledger.prefix + "LOCK")
    ident = capture_secure_path(lock, allowed_root=receipts)
    policy = {
        key: permission[key]
        for key in (
            "receipt_root_sha256",
            "package_sha256",
            "runtime_sha256",
            "source_tree_sha256",
            "institutional_catalog_sha256",
            "tariff_sha256",
            "tokenizer_manifest_sha256",
            "allowed_families",
            "allowed_levels",
            "issued_at_utc",
            "expires_at_utc",
        )
    }
    profile = envelope["profile"]
    policy.update(
        schema="P0-FINITE-CHAIN-POLICY-2.0",
        normal_permission_sha256=sha(canonical(permission)),
        normal_envelope_sha256=sha(path.read_bytes()),
        campaign_namespace_sha256=permission["permission_namespace_sha256"],
        root_lock_sha256=sha(lock.read_bytes()),
        root_lock_identity_sha256=sha(canonical({"device": ident.device, "inode": ident.inode})),
        price_evidence_sha256=profile["tariff_evidence"]["sha256"],
        max_chains=1,
        maximum_effects=4,
        roles=list(ROLES),
        per_effect_ceiling_usd="0.140000",
        cumulative_ceiling_usd="1.960000",
        max_output_tokens=4096,
        input_upper_tokens=36000,
        preview_minutes=15,
        authority_minutes=60,
        retry=0,
        fallback="NONE",
        max_campaign_effects=14,
        retained_origins=[],
    )
    owner = {
        "schema": "P0-FINITE-CHAIN-ADOPTION-2.0",
        "status": "ADOPTED" if adopted else "PROPOSED",
        "policy_sha256": sha(canonical(policy)),
        "normal_envelope_sha256": sha(path.read_bytes()),
        "price_evidence_sha256": policy["price_evidence_sha256"],
        "financial_evidence_admitted": adopted,
        "historical_uncertainty_preserved": True,
        "additional_finite_right_accepted": adopted,
    }
    startup = {
        "schema": "P0-FINITE-CHAIN-STARTUP-2.0",
        "historical_application_root": str(f.ROOT),
        "current_source_profile": f.artifact(
            root,
            "SYNTHETIC-current-source-profile.json",
            {
                "schema": "P0-FINITE-CURRENT-SOURCE-1.0",
                **{k: profile[k] for k in ("baseline_commit", "package", "source_manifest")},
            },
        ),
        "normal_envelope_sha256": sha(path.read_bytes()),
        "policy": f.artifact(root, "SYNTHETIC-finite-policy.json", policy),
        "decision": f.artifact(root, "SYNTHETIC-finite-adoption-NOT-OWNER.json", owner),
    }
    desc = f.artifact(root, "SYNTHETIC-finite-startup.json", startup)
    return (path, target, saved, receipts), desc


class Control(f.Control):
    def __init__(self, *, correction=False, scenario="complete"):
        super().__init__(scenario)
        self.correction = correction
        self.chain_calls = []
        self.binding = None
        self.service = None
        self.review_calls = 0
        self.clock = None

    def create(self, *, request):
        if request.schema_name not in {"p0_codesign_content", "technical_pedagogical_review"}:
            return super().create(request=request)
        self.calls += 1
        self.chain_calls.append(request)
        self.entered.set()
        assert self.release.wait(self.transport_wait_seconds)
        if self.scenario == "timeout":
            raise TimeoutError("SYNTHETIC_TIMEOUT")
        if self.scenario == "crash":
            raise SystemExit("SYNTHETIC_PROCESS_INTERRUPTION")
        payload = json.loads(request.input_json)
        if request.schema_name == "technical_pedagogical_review":
            self.review_calls += 1
            needs = self.correction and self.review_calls == 1
            confidence = {"level": "high", "basis": "TEST_SYNTHETIC_ONLY"}
            content = {
                "outcome": "OUTPUT",
                "structured_payload": {
                    "overall_assessment": "correction_required" if needs else "acceptable",
                    "correction_required": needs,
                    "coverage": payload["review_dimensions"],
                    "confidence": confidence,
                },
                "technical_findings": [
                    {
                        "finding_id": "finding-1",
                        "dimension": "REV-PED",
                        "severity": "minor",
                        "description": "Préciser le titre",
                        "target_locator": {"kind": "json_path", "path": ["title"]},
                        "rationale": "Clarification synthétique",
                        "correction_required": True,
                        "evidence_refs": [],
                        "confidence": confidence,
                        "suggested_action": {"code": "CLARIFY", "message": "Préciser le titre"},
                    }
                ]
                if needs
                else [],
                "limitations": [],
                "warnings": [],
                "uncertainties": [],
                "evidence_refs_used": payload["evidence_refs"],
            }
        else:
            content = copy.deepcopy(f.CONTENT)
            content["title"] = (
                "Perception : titre clarifié"
                if payload["operation"] == "CORRECT"
                else "Perception : faits et interprétations"
            )
            if payload["operation"] == "CORRECT":
                content = {
                    "content": content,
                    "addressed_findings": ["finding-1"],
                    "unresolved_findings": [],
                    "change_summary": "Titre clarifié, autres contenus identiques.",
                }
        status = (
            OpenAIResponseStatus.INCOMPLETE
            if self.scenario == "partial"
            else OpenAIResponseStatus.COMPLETED
        )
        if self.scenario == "late":
            self.binding.broker.clock = lambda: datetime.now(UTC).replace(year=2099)
        raw = canonical(content).decode() if self.scenario != "malformed" else '{"bad":true}'
        return OpenAIResponsesResponse(
            status,
            raw,
            OpenAIResponseUsage(1000, 0, 100, 1100, reasoning_tokens=0),
            service_tier="default",
            incomplete_reason=OpenAIIncompleteReason.MAX_OUTPUT_TOKENS
            if status is OpenAIResponseStatus.INCOMPLETE
            else OpenAIIncompleteReason.NONE,
        )


@contextmanager
def running(root, monkeypatch, control, *, existing=None, adopted=True, enabled=True):
    config, desc = existing or configuration(root, adopted=adopted)
    f.install_boundaries(monkeypatch, control)
    monkeypatch.setattr(
        finite_factory, "LocalTokenizerHelper", f.profile_factory.LocalTokenizerHelper
    )
    monkeypatch.setenv("OPENAI_API_KEY", f.FAKE_KEY)
    if not hasattr(control, "seed"):
        seed_parent(config, control)
    monkeypatch.setattr(finite_factory, "OpenAISDKResponsesTransportFactory", lambda **_: control)
    monkeypatch.setattr(
        ScopedApplicationSearch, "search_local", lambda self, **kw: Search().search_local(**kw)
    )
    original = finite_factory.FiniteChainComposition.bind

    def observe(owner, service, endpoint):
        result = original(owner, service, endpoint)
        control.binding, control.service = owner, service
        control.diagnostics = []
        actual = owner.broker._finalize

        def observed_final(**kw):
            try:
                return actual(**kw)
            except Exception as error:
                control.diagnostics.append((type(error).__name__, str(error)))
                raise

        owner.broker._finalize = observed_final
        return result

    monkeypatch.setattr(finite_factory.FiniteChainComposition, "bind", observe)
    args = [
        "--p0-codesign-profile",
        desc["path"],
        "--p0-codesign-profile-sha256",
        desc["sha256"],
        "--p0-codesign-mode",
        "enabled" if enabled else "disabled",
    ]
    with f.running(root, monkeypatch, control, existing=config, extra_args=args) as (
        port,
        configuration_,
    ):
        yield port, (configuration_, desc)


def seed_parent(config, control):
    from secrets import token_hex

    from backend.infrastructure.composition.factories.local_browser import (
        bind_confirmed_p0_publication,
        build_saved_application,
    )
    from backend.infrastructure.composition.factories.p0_creation import build_p0_creation
    from backend.infrastructure.composition.factories.p0_normal_profile import (
        P0NormalProductComposition,
    )

    path, target, saved, _ = config
    normal = P0NormalProductComposition(
        path=path, target=target, saved_root=saved, credential_source="OPENAI_API_KEY"
    )
    try:
        service, endpoint = build_p0_creation(target, "SYNTHETIC-NONCE", normal.generation)
        normal.bind(service, endpoint)
        application = build_saved_application(
            saved, source=service.saved_source, word_profile="product-v7"
        )
        service.saved_reader = application.read_local_p0
        bind_confirmed_p0_publication(service, application, normal.generation)
        prepared = service.execute(
            "prepare",
            {
                "command_id": token_hex(16),
                "context": f.context(),
                "reference": {"notion_id": "notion:shared", "passage_ref": f.SOURCE["passage_ref"]},
            },
        )
        command = {
            "command_id": token_hex(16),
            "preparation_ref": prepared["preparation_ref"],
            "preparation_sha256": prepared["preparation_sha256"],
        }
        shown = endpoint.consent_execute("consent_preview", command)
        result = endpoint.consent_execute(
            "consent_generate",
            {
                **command,
                "command_id": token_hex(16),
                "preview_sha256": shown["preview_sha256"],
                "transfer_accepted": True,
                "cost_bound_accepted": True,
            },
        )
        assert result["state"] == "CANDIDATE", result
        control.seed = result["view"]
    finally:
        normal.close()
