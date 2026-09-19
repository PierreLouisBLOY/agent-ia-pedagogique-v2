"""Explicit private-copy selection through M03, then the existing M04/AG02/AG03 path."""
from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

from backend.adapters.outbound.document_content.sqlite import DocumentContentAccessAdapter
from backend.adapters.outbound.evidence.local_reference import (
    LocalReferenceContentAdapter,
    LocalReferenceRejected,
    SelectedLocalEvidenceSearch,
)
from backend.adapters.outbound.evidence.sqlite import SQLiteEvidenceDocumentContentAdapter
from backend.adapters.outbound.generation.conversation import (
    ConversationGenerationAdapter,
    NoGenerationDispatch,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.search.local import SQLiteLocalSearchAdapter
from backend.agent_runtime.agents.evidence import (
    EvidenceAgent,
    EvidenceMaterializationPolicy,
    RetrievalChannel,
    RetrievalCoordinationPolicy,
    RetrievalCoordinator,
)
from backend.infrastructure.composition.factories.conversation import ConversationEvidenceClock
from backend.infrastructure.composition.factories.local_browser import (
    Read15RuntimeTarget,
    _application_searcher,
)
from backend.modules.pedagogical_design.application.commands.create_conversation_draft import (
    CreateConversationDraft,
)
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    LOCAL_REFERENCE_LABEL,
    REFERENCE_PROVENANCE_CONTRACT,
    ConversationDraftRequest,
)
from backend.shared_kernel.time import Instant


@contextmanager
def selected_local_evidence(target: Read15RuntimeTarget, selections: tuple[Mapping[str, object], ...]) -> Iterator[EvidenceAgent]:
    target.validate()
    with closing(connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)) as connection:
        search = SelectedLocalEvidenceSearch(connection, selections)
        channels = (RetrievalChannel.STRUCTURED, RetrievalChannel.LEXICAL)
        coordinator = RetrievalCoordinator(search, RetrievalCoordinationPolicy(channels, channels, 3, 3, 60), search)
        content = SQLiteEvidenceDocumentContentAdapter(DocumentContentAccessAdapter(connection), ConversationEvidenceClock())
        with SQLiteLocalSearchAdapter(connection).read_snapshot():
            yield EvidenceAgent(coordinator, content, EvidenceMaterializationPolicy(1000))
    target.validate()


def prepare_local_references(target: Read15RuntimeTarget, *, request: ConversationDraftRequest,
        queries: tuple[str, ...], selection: Sequence[Mapping[str, str]] | None = None) -> dict[str, object]:
    if (type(request) is not ConversationDraftRequest or type(queries) is not tuple
            or not 1 <= len(queries) <= 3 or len(set(queries)) != len(queries)):
        raise LocalReferenceRejected()
    if selection is not None and (len(selection) != len(queries) or any(
        set(value) != {"query", "passage_ref", "version_or_checksum"}
        or value["query"] != query for query, value in zip(queries, selection, strict=True)
    )):
        raise LocalReferenceRejected("REFERENCE_SELECTION_INVALID")
    target.validate()
    endpoint = _application_searcher(target)
    searches: list[dict[str, object]] = []
    chosen: list[Mapping[str, object]] = []
    provenance: list[dict[str, object]] = []
    for index, query in enumerate(queries):
        response = endpoint.get(query, 20, "r5-reference-" + str(index + 1))
        if response.status != 200:
            raise LocalReferenceRejected("REFERENCE_SEARCH_FAILED")
        data = cast(dict[str, object], response.payload["data"])
        results = cast(list[dict[str, object]], data["items"])
        searches.append({"query": query, **data})
        eligible = results
        if selection is not None:
            wanted = selection[index]
            eligible = [item for item in results if item["passage_ref"] == wanted["passage_ref"]
                        and item["version_or_checksum"] == wanted["version_or_checksum"]]
            if len(eligible) != 1:
                raise LocalReferenceRejected("REFERENCE_SELECTION_MISSING_OR_AMBIGUOUS")
        else:
            eligible = [item for item in results if item["object_kind"] != "NOTION"
                        and len(str(item["excerpt"])) >= 40
                        and item["passage_ref"] not in {entry["passage_ref"] for entry in chosen}]
        target.validate()
        materialized = None
        with closing(connect_sqlite(target.runtime_path, readonly=True, allowed_root=target.data_root)) as connection:
            connection.execute("BEGIN")
            adapter = LocalReferenceContentAdapter(connection)
            for item in eligible:
                try:
                    materialized = adapter.materialize(item, evidence_id=f"r2.evidence.{index + 1}")
                    chosen.append(item)
                    break
                except LocalReferenceRejected as error:
                    if selection is not None or str(error) != "REFERENCE_TOO_LARGE":
                        raise
            connection.rollback()
        if materialized is None:
            raise LocalReferenceRejected("REFERENCE_NO_USABLE_PASSAGE")
        provenance.append({"query": query, **materialized})
    if len({item["passage_ref"] for item in chosen}) != len(chosen):
        raise LocalReferenceRejected("REFERENCE_DUPLICATE_SELECTION")
    bridge = ConversationGenerationAdapter(
        evidence=lambda: selected_local_evidence(target, tuple(chosen)), generation=NoGenerationDispatch(),
        clock=lambda: Instant(datetime.now(UTC)), new_id=lambda prefix: prefix + ":" + uuid4().hex,
        reserved_cost=Decimal("0"), provenance_label=LOCAL_REFERENCE_LABEL)
    prepared = CreateConversationDraft(bridge).prepare(request=request)
    target.validate()
    projection = cast(Mapping[str, object], prepared["projection"])
    inputs = cast(Mapping[str, object], projection["resolved_inputs"])
    projected = cast(Sequence[Mapping[str, object]], inputs["evidence"])
    by_locator = {str(item["locator"]): item for item in provenance}
    if len(projected) != len(chosen):
        raise LocalReferenceRejected("REFERENCE_PROJECTION_MISMATCH")
    for projected_item in projected:
        metadata = by_locator[str(projected_item["locator"])]
        if projected_item["text"] != metadata["excerpt"] or projected_item["version_or_checksum"] != metadata["version_or_checksum"]:
            raise LocalReferenceRejected("REFERENCE_PROJECTION_MISMATCH")
        metadata["evidence_id"] = projected_item["evidence_id"]
    return {**prepared, "provenance_contract": REFERENCE_PROVENANCE_CONTRACT,
        "selection_mode": "EXPLICIT" if selection is not None else "TECHNICAL_PROPOSAL",
        "searches": searches, "provenance": provenance, "runtime_sha256": target.expected_sha256,
        "provider_calls": 0, "count_calls": 0, "provider_credential_resolved": 0,
        "production_created": False, "limitations": [
            "Sélection technique : adéquation pédagogique à apprécier avant transfert.",
            "Un lien documentaire ne prouve pas la présence d'un document complet.",
            "Aucun fichier externe ouvert ; aucun profil, budget ou transfert autorisé."]}
