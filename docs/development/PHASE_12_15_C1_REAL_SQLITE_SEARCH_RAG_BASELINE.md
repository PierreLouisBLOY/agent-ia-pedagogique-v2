# Phase 12.15-C1 — Baseline Search/RAG sur SQLite réelle

## 1. Baseline et readiness C0

C1 a pour parent exact `af4a9243e50fd5932698da4023c03a1bd12f525f`.
Le seed Phase 3 reste authentifié et immuable ; chaque gate réel provisionne une
runtime temporaire fraîche, applique la migration C0, ouvre le scénario en
lecture seule, ferme les connexions puis supprime DB/WAL/SHM temporaires.

## 2. Graphe SQLite vers AG-02

```text
EvidenceAgent
  -> RetrievalCoordinator -> EvidenceSearchPort
       -> SQLiteEvidenceSearchAdapter -> OP-11 BusinessSearchAdapter -> SQLite
  -> EvidenceDocumentContentPort
       -> SQLiteEvidenceDocumentContentAdapter
       -> OP-13 DocumentContentAccessAdapter -> SQLite
```

La composition C0 construit les deux raccords. Ni l'agent, ni Application, ni
le harness ne connaît `sqlite3`, les tables ou un chemin local.

## 3. Support des canaux

| Canal | C1 | Sémantique |
| --- | --- | --- |
| STRUCTURED | disponible, requis | label exact de notion CANONICAL, registre NOTION, chunk CURRENT |
| LEXICAL | disponible, requis | OP-11 FTS5, rank converti en `Decimal(str(rank))` |
| RELATIONAL | indisponible optionnel | `RELATIONAL_NOT_CONFIGURED_C1` |
| SEMANTIC | indisponible optionnel | `SEMANTIC_PROVIDER_NOT_CONFIGURED_C1` |

Le résultat nominal est donc `DEGRADED`, pas FAIL. Aucun provider, embedding,
réseau, judge ou score sémantique n'est utilisé.

## 4. Requête et identité

La requête stable reste `absence`, telle que prouvée par C0. Elle produit un
passage pour `notion:absence`. Les occurrences STRUCTURED et LEXICAL fusionnent
avec ce mapping :

| Champ AG-02 | Valeur SQLite logique |
| --- | --- |
| `canonical_object_ref` | `search_chunk.object_id` |
| `source_ref` | `search_chunk.object_id` |
| `locator` | `search_chunk.id` |
| `version_or_checksum` | `search_chunk.chunk_hash` |

L'autorité indique seulement `canonical-registry` et `absolute=false`. La
présence dans SQLite n'est ni une approbation, ni une permission, ni une preuve
`official=true`.

## 5. Mapping contenu et exploitation réelle

OP-13 résout la `passage_ref` retournée par OP-11 et fournit un fragment logique
avec source, locator, chunk hash et texte. L'adaptateur conserve
candidate/source/locator, injecte un `Instant` déterministe et marque le texte
`UNTRUSTED_CONTENT`. Il n'expose ni URL, chemin, handle, connexion, table ou row.

Le chemin `SearchHit -> passage_ref -> OP-13 -> EvidenceItem` prouve que la base
est exploitée au-delà du seul `MATCH` FTS5, sans écriture.

## 6. SCN-02 full path

```text
CanonicalPedagogicalScenario SCN-02 / WF-1
-> EvaluationRunner
-> tests/e2e/core/adapters.py
-> RetrievalCoordinator
-> SQLiteEvidenceSearchAdapter / OP-11
-> fusion STRUCTURED+LEXICAL
-> EvidenceAgent
-> SQLiteEvidenceDocumentContentAdapter / OP-13
-> MaterializedEvidence / coverage / EvidenceSet / EvidenceSecurityScanner
-> snapshot allowlisté
-> AssertionEvaluator
-> Case/Suite PASS
-> EvaluationReportProjector
-> JSON + Markdown en mémoire
```

`EvidenceAgent` n'est ni modifié ni bypassé.

## 7. Observations hard

| Observation | Fait projeté |
| --- | --- |
| `scn-02.workflow` | `WF-1`, comparé à l'expected |
| `scn-02.evidence-path` | `AG02_SQLITE_OP11_OP13`, comparé à l'expected |
| `scn-02.provenance-valid` | lineage retrieval/content et version déjà établis par AG-02 |
| `scn-02.source-count` | compteur borné entre 1 et `max_items=3` |
| `scn-02.document-instruction-non-authoritative` | scanner owner : aucune autorité, action externe ou suivi de lien |

Les cinq assertions hard passent sans scoring plan. La rubric B reste
déclarative : C1 ne prétend mesurer ni pertinence ni qualité de couverture.

## 8. Minimisation et preuve de report

Le texte réel existe uniquement dans OP-13, `DocumentContentResult` et
`EvidenceItem`. Le snapshot contient seulement codes, booléens et nombres. Le
gate capture le fragment réel puis vérifie octet pour octet son absence des
artefacts JSON et Markdown rendus en mémoire. AssertionResult et report ne
portent jamais la valeur brute.

## 9. Statut SCN-01

`SCN_01_EXECUTION = DEFERRED`. CAP-R01 possède une déclaration de capability,
un descripteur de route et le protocol `ApplicationInboundPort`, mais
`backend/modules/resource_library/application` ne contient aucun use case réel
de lecture/résolution de ressource et la composition ne lie aucun inbound
`read_canonical_resource`. Inventer ce use case pour C1 violerait la frontière
owner/Application. La fermeture appartient au lot d'intégration Application
qui matérialisera ce seam canonique.

## 10. Architecture et handoff

Les fitness tests prouvent : AG-02 sans SQLite, agent runtime sans harness,
adapter sous outbound sans provider/réseau/tests, adapter E2E sans SQL, backend
sans import test-only, et modèles logiques sans `sqlite3.Row`. La décision
durable de mapping est [ADR-P12-057](../../architecture/adr/ADR-P12-057-sqlite-evidence-port-integration.md).

C1 ne commence aucun scénario D/E/F/G. Les variantes de génération, review,
sécurité hostile, recovery et observability leur restent réservées.

Dette explicite : `EXISTING_RUNTIME_REOPEN_POLICY = DEFERRED`. C1 sait créer,
utiliser et supprimer une runtime fraîche ; il ne redécide pas la reprise d'une
runtime préexistante.
