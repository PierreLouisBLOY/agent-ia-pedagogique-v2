from __future__ import annotations

# The repository root is inserted before application imports for direct script execution.
# ruff: noqa: E402
import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPOSITORY_ROOT))

from backend.adapters.inbound.application.local_search import (
    SEARCH_USE_CASE_ID,
    LocalSearchUseCaseInbound,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.sqlite import SQLiteResourceStoreAdapter
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
from backend.agent_runtime.agents.generation.generation_coordination_model import (
    GenerationPreparationRequest,
)
from backend.agent_runtime.agents.generation.generation_coordinator import GenerationCoordinator
from backend.agent_runtime.agents.generation.generation_model import (
    GenerationPortRequest,
    GenerationPortResult,
)
from backend.agent_runtime.contracts import (
    AGENT_CONTRACT_SCHEMA_V1_0,
    ActorKind,
    ActorRef,
    AgentId,
    ContractMeta,
    InvocationStatus,
    ProductionRequest,
    UseCaseRequest,
)
from backend.core_contracts.capability import CapabilityId
from backend.core_contracts.invocation import UseCaseContext
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.composition.factories.r6_all_notions import (
    enumerate_canonical_notions,
)
from backend.modules.resource_library.application.queries.get_resource import GetResourceQuery
from backend.modules.resource_library.application.queries.search_local import SearchLocalQuery
from backend.shared_kernel.correlation import CorrelationId
from backend.shared_kernel.time import Instant

SEED_SHA256 = "9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1"
SEED_SIZE = 227_557_376
EXPECTED_HISTORICAL_CANONICAL = 628
EXPECTED_HISTORICAL_MERGED = 9
EXPECTED_HISTORICAL_TOTAL = 637
FORMULA_ROWS_FROM_CP645_MANIFEST = 210


class _NoDispatchPort:
    def __init__(self) -> None:
        self.dispatch_attempts = 0

    def generate(self, *, request: GenerationPortRequest) -> GenerationPortResult:
        self.dispatch_attempts += 1
        raise AssertionError("R6_PROVIDER_DISPATCH_FORBIDDEN")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _use_case_request(index: int, label: str) -> UseCaseRequest:
    correlation = CorrelationId(f"r6-notion-{index:04d}")
    meta = ContractMeta(
        schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
        run_id="r6-all-notions-campaign",
        step_id=f"search-{index:04d}",
        parent_step_id=None,
        correlation_id=correlation,
        created_at=Instant(datetime(2026, 10, 3, tzinfo=UTC)),
        actor=ActorRef(ActorKind.APPLICATION, "r6-all-notions-campaign"),
        status=InvocationStatus.PLANNED,
    )
    return UseCaseRequest(
        meta=meta,
        use_case_id=SEARCH_USE_CASE_ID,
        payload={"q": label, "limit": 20},
        actor_context=UseCaseContext(correlation),
    )


def _prepare_ag03(
    index: int, notion: Any, evidence_refs: tuple[str, ...]
) -> tuple[bool, dict[str, object]]:
    if not evidence_refs:
        return False, {"status": "CONTENT_GAP", "reason": "no admitted evidence references"}
    correlation = CorrelationId(f"r6-ag03-{index:04d}")
    canonical = ProductionRequest(
        meta=ContractMeta(
            schema_version=AGENT_CONTRACT_SCHEMA_V1_0,
            run_id="r6-all-notions-campaign",
            step_id=f"prepare-{index:04d}",
            parent_step_id=None,
            correlation_id=correlation,
            created_at=Instant(datetime(2026, 10, 3, tzinfo=UTC)),
            actor=ActorRef(ActorKind.AGENT, AgentId.AG_03.value),
            status=InvocationStatus.PLANNED,
        ),
        production_kind="course",
        brief=(
            "Prepare a bounded teaching resource for the exact canonical notion, "
            "using only the attached current CP645 evidence; preserve uncertainty."
        ),
        output_format="markdown",
        pedagogical_context={
            "canonical_notion_id": notion.notion_id,
            "canonical_label": notion.canonical_label,
            "level_scope": "UNSCOPED_NEUTRAL",
            "declared_level_applicability": list(notion.level_applicability),
        },
        constraints={"source_only": True, "no_unverified_claims": True},
        evidence_refs=evidence_refs,
        expected_sections=("Objectifs", "Contenu lié aux sources", "Vérification"),
    )
    output_contract = {
        "contract_id": "R6-ALL-NOTIONS-PREPARED-COURSE-1.0",
        "resource_type": "COURSE",
        "notion_id": notion.notion_id,
        "required_evidence": True,
    }
    request = GenerationPreparationRequest(
        capability_id=CapabilityId("CAP-G01"),
        request=canonical,
        resolved_inputs={
            "notion_id": notion.notion_id,
            "canonical_label": notion.canonical_label,
            "evidence_refs": evidence_refs,
        },
        output_contract=output_contract,
    )
    no_dispatch = _NoDispatchPort()
    prepared = GenerationCoordinator(no_dispatch).prepare(request=request)
    valid = (
        prepared.preparation_request == request
        and prepared.canonical_request == canonical
        and prepared.port_request.source_step_id == canonical.meta.step_id
        and prepared.port_request.evidence_refs == evidence_refs
        and dict(prepared.port_request.output_contract) == output_contract
        and no_dispatch.dispatch_attempts == 0
    )
    return valid, {
        "status": "PASS" if valid else "ERROR",
        "capability": "CAP-G01",
        "prepared_call_type": type(prepared).__name__,
        "dispatch_attempts": no_dispatch.dispatch_attempts,
        "output_contract_sha256": hashlib.sha256(_json_bytes(output_contract)).hexdigest(),
    }


def _run_one(
    index: int, notion: Any, inbound: LocalSearchUseCaseInbound, search: SQLiteLocalSearchAdapter
) -> dict[str, object]:
    try:
        with search.read_snapshot():
            response = inbound.invoke(request=_use_case_request(index, notion.canonical_label))
        outcome = response.outcome
        if (
            response.use_case_id != SEARCH_USE_CASE_ID
            or response.meta.correlation_id != outcome.correlation_id
            or not outcome.success
            or outcome.data is None
            or outcome.side_effects
            or outcome.business_errors
            or outcome.application_failure is not None
        ):
            raise ValueError("R6_APPLICATION_SEARCH_OUTCOME_INVALID")
        data = outcome.data
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("R6_APPLICATION_SEARCH_SHAPE_INVALID")
        items = data["items"]
        exact = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("object_ref") == notion.notion_id
            and item.get("object_kind") == "NOTION"
        ]
        related = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("object_ref") != notion.notion_id
            and isinstance(item.get("excerpt"), str)
            and item.get("excerpt")
        ]
        evidence_refs: list[str] = []
        evidence_items: list[dict[str, object]] = []
        valid_provenance = True
        for item in items:
            if not isinstance(item, dict):
                continue
            provenance = item.get("provenance")
            valid = (
                isinstance(provenance, dict)
                and provenance.get("source_kind") == "canonical_search_chunk"
                and provenance.get("freshness") == "CURRENT"
                and provenance.get("authority_absolute") is False
                and provenance.get("content_trust") == "UNTRUSTED_CONTENT"
            )
            valid_provenance = valid_provenance and valid
            if not valid:
                continue
            passage_ref = str(item.get("passage_ref", ""))
            version = str(item.get("version_or_checksum", ""))
            excerpt = str(item.get("excerpt", ""))
            ref_hash = hashlib.sha256(
                f"{notion.notion_id}\n{passage_ref}\n{version}".encode()
            ).hexdigest()[:32]
            evidence_ref = "evidence:" + ref_hash
            evidence_refs.append(evidence_ref)
            evidence_items.append(
                {
                    "evidence_ref": evidence_ref,
                    "source_ref": str(item.get("object_ref", "")),
                    "object_kind": str(item.get("object_kind", "")),
                    "passage_ref": passage_ref,
                    "version_or_checksum": version,
                    "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                    "authority_absolute": False,
                    "content_trust": "UNTRUSTED_CONTENT",
                }
            )
        if len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("R6_DUPLICATE_EVIDENCE_REF")
        ag03_ok, preparation = _prepare_ag03(index, notion, tuple(evidence_refs))
        identity_status = "PASS" if notion.identity_status == "CANONICAL" else "ERROR"
        retrieval_status = "PASS" if exact else "CONTENT_GAP"
        evidence_status = "PASS" if exact and related and valid_provenance else "CONTENT_GAP"
        context_status = "DECLARED_LEVELS" if notion.level_applicability else "UNSCOPED_NEUTRAL"
        ag03_status = str(preparation["status"])
        output_status = "PASS" if ag03_ok else "ERROR" if evidence_refs else "CONTENT_GAP"
        technical_pass = all(
            (
                identity_status == "PASS",
                retrieval_status == "PASS",
                ag03_status == "PASS",
                output_status == "PASS",
            )
        )
        overall = (
            "PASS"
            if technical_pass and evidence_status == "PASS"
            else "CONTENT_GAP"
            if not technical_pass or evidence_status != "PASS"
            else "ERROR"
        )
        if not exact:
            reason = "Exact canonical identity was not returned by Application search."
        elif not related:
            reason = "Only the canonical label was retrieved; supporting current linked content is missing."
        elif not valid_provenance:
            reason = (
                "One or more evidence passages failed the current canonical provenance contract."
            )
        elif not ag03_ok:
            reason = "AG03 preparation did not preserve the request, evidence references, or output contract."
        else:
            reason = "Exact canonical evidence and at least one linked current passage prepared against the AG03 contract."
        return {
            "notion_id": notion.notion_id,
            "canonical_label": notion.canonical_label,
            "identity_status": identity_status,
            "source_or_provenance_status": "PASS" if exact and valid_provenance else "CONTENT_GAP",
            "retrieval_status": retrieval_status,
            "context_resolution_status": context_status,
            "evidence_status": evidence_status,
            "ag03_preparation_status": ag03_status,
            "output_contract_status": output_status,
            "formula_method_applicability": {
                "method_refs": list(notion.method_refs),
                "method_link_status": "METHOD_REFS_PRESENT"
                if notion.method_refs
                else "NO_METHOD_REF_LINKED",
                "formula_rows_in_cp645_manifest": FORMULA_ROWS_FROM_CP645_MANIFEST,
                "notion_specific_formula_link": "NOT_EXPOSED_BY_CURRENT_APPLICATION_CONTRACT",
            },
            "level_applicability": list(notion.level_applicability)
            if notion.level_applicability
            else ["UNSCOPED"],
            "evidence_refs": evidence_items,
            "ag03_preparation": preparation,
            "overall_status": overall,
            "reason": reason,
        }
    except Exception as error:
        safe = str(error)
        if not safe or not safe.replace("_", "").isalnum() or safe.upper() != safe:
            safe = type(error).__name__
        return {
            "notion_id": notion.notion_id,
            "canonical_label": notion.canonical_label,
            "identity_status": "PASS" if notion.identity_status == "CANONICAL" else "ERROR",
            "source_or_provenance_status": "ERROR",
            "retrieval_status": "ERROR",
            "context_resolution_status": "ERROR",
            "evidence_status": "ERROR",
            "ag03_preparation_status": "ERROR",
            "output_contract_status": "ERROR",
            "formula_method_applicability": {
                "method_refs": list(notion.method_refs),
                "formula_rows_in_cp645_manifest": FORMULA_ROWS_FROM_CP645_MANIFEST,
                "notion_specific_formula_link": "NOT_EXPOSED_BY_CURRENT_APPLICATION_CONTRACT",
            },
            "level_applicability": list(notion.level_applicability)
            if notion.level_applicability
            else ["UNSCOPED"],
            "evidence_refs": [],
            "ag03_preparation": {"status": "ERROR"},
            "overall_status": "ERROR",
            "reason": safe,
        }


def run(database: Path, output_dir: Path) -> dict[str, object]:
    if not database.is_absolute() or not output_dir.is_absolute():
        raise ValueError("R6_ABSOLUTE_PATHS_REQUIRED")
    target = Read15RuntimeTarget(database.resolve(), database.resolve().parent, SEED_SHA256)
    target.validate()
    if database.stat().st_size != SEED_SIZE:
        raise ValueError("R6_CP645_SIZE_MISMATCH")
    notions = enumerate_canonical_notions(target)
    universe = [
        {
            "notion_id": item.notion_id,
            "canonical_label": item.canonical_label,
            "identity_status": item.identity_status,
            "level_applicability": list(item.level_applicability)
            if item.level_applicability
            else ["UNSCOPED"],
            "method_refs": list(item.method_refs),
            "formula_applicability": "NOTION_SPECIFIC_FORMULA_LINK_NOT_EXPOSED",
        }
        for item in notions
    ]
    universe_bytes = _json_bytes(universe)
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = connect_sqlite(database, readonly=True, allowed_root=target.data_root)
    search = SQLiteLocalSearchAdapter(connection)
    resources = SQLiteResourceStoreAdapter(connection)
    inbound = LocalSearchUseCaseInbound(SearchLocalQuery(search, GetResourceQuery(resources)))
    results: list[dict[str, object]] = []
    try:
        for index, notion in enumerate(notions, start=1):
            results.append(_run_one(index, notion, inbound, search))
    finally:
        connection.close()
    target.validate()
    result_bytes = b"".join(_json_bytes(result) for result in results)
    universe_path = output_dir / "258_R6_ALL_NOTIONS_UNIVERSE.json"
    result_path = output_dir / "259_R6_ALL_NOTIONS_RESULTS.jsonl"
    universe_path.write_bytes(universe_bytes)
    result_path.write_bytes(result_bytes)
    counts = Counter(str(result["overall_status"]) for result in results)
    executed_ids = [str(result["notion_id"]) for result in results]
    summary = {
        "schema": "R6-ALL-NOTIONS-SUMMARY-1.0",
        "expected_historical": {
            "canonical": EXPECTED_HISTORICAL_CANONICAL,
            "merged": EXPECTED_HISTORICAL_MERGED,
            "total": EXPECTED_HISTORICAL_TOTAL,
        },
        "actual_enumerated": len(notions),
        "actual_executed": len(results),
        "status_counts": dict(sorted(counts.items())),
        "enumerated_equals_executed": executed_ids == [item.notion_id for item in notions],
        "duplicate_ids": len(executed_ids) - len(set(executed_ids)),
        "missing_ids": sorted(set(item.notion_id for item in notions) - set(executed_ids)),
        "unexpected_ids": sorted(set(executed_ids) - set(item.notion_id for item in notions)),
        "universe_sha256": hashlib.sha256(universe_bytes).hexdigest(),
        "results_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "cp645_seed_sha256": SEED_SHA256,
        "provider_calls": 0,
        "count_calls": 0,
        "credential_resolution": 0,
        "external_network": 0,
        "ag03_execute_calls": 0,
        "ag03_prepare_calls": len(results),
        "formula_applicability_limit": "CP645 manifest establishes 210 approved formulas globally; current Application model exposes method-to-notion links but no notion-specific formula relation.",
    }
    summary_path = output_dir / "260_R6_ALL_NOTIONS_SUMMARY.json"
    summary_path.write_bytes(_json_bytes(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path(os.environ["PROJET_V2_CANONICAL_DB"]))
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    summary = run(args.database, args.output_dir)
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return (
        0
        if summary["enumerated_equals_executed"]
        and summary["duplicate_ids"] == 0
        and not summary["missing_ids"]
        and not summary["unexpected_ids"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
