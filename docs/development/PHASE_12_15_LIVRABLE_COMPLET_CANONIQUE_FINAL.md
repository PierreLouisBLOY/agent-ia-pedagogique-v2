# PROJET V2 — PHASE 12.15
## LIVRABLE COMPLET CANONIQUE FINAL
### Intégration end-to-end sur scénarios pédagogiques canoniques

STATUT : CLOSED / MERGED / CANONICAL

```text
FUNCTIONAL_SHA =
00d07c0a2c7ad8d949390b0900af53e188c277af

FUNCTIONAL_TREE_SHA =
0a516f95e7bd8896b8ff9c467ee69b3d6985dc2f

MERGE_MODE =
FAST_FORWARD_ONLY

DOCUMENTARY_SHA =
TO_BE_FILLED_BY_COMMIT
```

Ce livrable clôt la Phase 12.15 après audit cumulatif et fast-forward strict sur
`main`. Il décrit les preuves réelles, les frontières test-only et les dettes
différées sans revendiquer de persistance métier ou de calibration provider
absente.

## 1. Scope canonique

```text
12.14 =
generic evaluation harness

12.15 =
canonical pedagogical end-to-end scenarios
+ real SQLite data paths where required
+ real Application/agent/runtime owners
+ provider-neutral deterministic technical ports
+ cross-cutting security/recovery/observability validation
+ full canonical suite/report

12.16 =
providers/models/budgets/timeouts/context calibration
+ pedagogical quality rubric calibration

12.17 =
rationalization/debt

12.18 =
final Phase 12 gate
```

La Phase 12.15 n'est pas une phase de calibration et ne commence pas la Phase
13. Les ports déterministes utilisés par les scénarios remplacent seulement des
boundaries techniques ; ils ne remplacent jamais les owners canoniques.

## 2. Chronologie A à H3

| Étape | Objet | SHA |
|---|---|---|
| 12.15-A | Audit E2E et golden design, audit-only | aucun commit |
| 12.15-B | Golden corpus | `37aeffdc43bce34e356660d83f44ec42fbb11cdc` |
| 12.15-C0 | SQLite runtime integration et promotion Phase 7 | `af4a9243e50fd5932698da4023c03a1bd12f525f` |
| 12.15-C1 | Search/RAG SQLite, SCN-02 | `3fb936c92037cc707065677aaaa4f4ad111b743e` |
| 12.15-C2 | Application Resource, SCN-01 | `512a595ee11eafdfa9a9ff13e6aa3228fd43cd35` |
| 12.15-D | Génération, transformation et exercice, SCN-03/04/05 | `67503cf62fb176ed445930a4e6893f6aefb99fd2` |
| 12.15-E | Assessment, correction et QCM, SCN-06/07/08 | `01f879255473653b1168449b25ada816ba7190a7` |
| 12.15-F | Security, recovery et observability transverses | `87569bfb257c18da89d2e9a54e4d01d5dd6def47` |
| 12.15-G | Suite canonique complète et rapports | `00d07c0a2c7ad8d949390b0900af53e188c277af` |
| 12.15-H1 | Audit cumulatif pré-merge | aucun commit |
| 12.15-H2 | Fast-forward strict | aucun commit |
| 12.15-H3 | Clôture documentaire canonique | présent livrable |

H1 et H2 n'ont créé aucun commit. H2 a conservé G comme identité fonctionnelle.

## 3. Golden corpus pédagogique

Le corpus est synthétique, versionné, déterministe et sans donnée de production
ou donnée privée utilisateur.

| Code | Niveau | Intent | Workflow(s) | Sections canoniques |
|---|---|---|---|---|
| SCN-01 | Première STMG | Resource organization | WF-0 | context, summary |
| SCN-02 | Terminale STMG | Resource search | WF-1 | concept, summary |
| SCN-03 | Première STMG | Course creation | WF-2 | objective, concept, example, summary |
| SCN-04 | BTS CG 1 | Resource transformation | WF-4 | context, concept, example, summary |
| SCN-05 | Terminale STMG | Exercise creation | WF-5 + WF-10 | context, questions, correction-link |
| SCN-06 | BTS CG 1 | Assessment creation | WF-8 + WF-6 | instructions, questions, marking-scheme |
| SCN-07 | BTS CG 2 | Correction/remediation | WF-1 + WF-7 + WF-0 | context, correction-link, summary |
| SCN-08 | BTS CG 2 | QCM/quiz variants | WF-9 + WF-3 + WF-11 | question, options, answer-key, feedback |

```text
PEDAGOGICAL_GOLDEN_CORPUS != PRODUCTION_DATA
PEDAGOGICAL_GOLDEN_CORPUS != USER_PRIVATE_DATA
```

## 4. Assertions hard et couverture workflow

| Scénario | Assertions hard | Statut |
|---|---:|---|
| SCN-01 | 4 | PASS |
| SCN-02 | 5 | PASS |
| SCN-03 | 4 | PASS |
| SCN-04 | 3 | PASS |
| SCN-05 | 4 | PASS |
| SCN-06 | 5 | PASS |
| SCN-07 | 6 | PASS |
| SCN-08 | 6 | PASS |
| **Total** | **37** | **PASS** |

```text
8/8 scenarios PASS
37/37 hard assertions PASS
0 scoring result
0 rubric result
```

Les rubrics de qualité restent déclaratives jusqu'à la Phase 12.16.

| Workflow | Scénarios |
|---|---|
| WF-0 | SCN-01, SCN-07 |
| WF-1 | SCN-02, SCN-07 |
| WF-2 | SCN-03 |
| WF-3 | SCN-08 |
| WF-4 | SCN-04 |
| WF-5 | SCN-05 |
| WF-6 | SCN-06 |
| WF-7 | SCN-07 |
| WF-8 | SCN-06 |
| WF-9 | SCN-08 |
| WF-10 | SCN-05 |
| WF-11 | SCN-08 |

```text
WF0_TO_WF11_COVERAGE = COMPLETE
```

## 5. Phase 7 et intégration SQLite

```text
PHASE7_SPECIFICATION = V2
PHASE7_IMPLEMENTATION_HISTORICALLY_EXISTS = TRUE
PHASE7_HISTORICAL_REPOSITORY = agent-ia-pedagogique
PHASE7_CURRENT_V2_INTEGRATION = PRESENT_AFTER_C0
PHASE7_REIMPLEMENTED_FROM_SCRATCH = FALSE
```

C0 est une promotion, adaptation et intégration de l'implémentation historique
dans les packages et boundaries V2 actuels. Le runtime V2 ne dépend pas du dépôt
historique.

### Seed Phase 3

```text
name = base_pedagogique_v2.sqlite
size = 105553920
sha256 =
38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134

tables = 98
indexes = 20
triggers = 7
views = 2
integrity_check = ok
quick_check = ok
foreign_key_violations = 0

PHASE3_CANONICAL_SEED = IMMUTABLE
RUNTIME_DB = COPY + PHASE7_MIGRATIONS
```

### Migration 001

```text
file = 001_document_sha256_check.sql
historical_commit =
98d8464232f3cea21f7ac911c268b1ad8e675e0d
git_blob =
38b369d73be55f8c90dca62544a64b1277190c14
sha256 =
5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
```

La copie runtime reçoit les migrations versionnées et leur ledger. Son hash
peut différer de celui du seed sans modifier l'identité canonique Phase 3.

## 6. Opérations de persistance OP-01 à OP-13

| Opération | Owner |
|---|---|
| OP-01 | KnowledgeStore |
| OP-02 | DocumentStore |
| OP-03 | ResourceStore |
| OP-04 | ContextStore |
| OP-05 | WorkStore |
| OP-06 | ValidationStore |
| OP-07 | QualityStore |
| OP-08 | LifecycleDecisionStore |
| OP-09 | AuditTraceabilityStore |
| OP-10 | UnitOfWork |
| OP-11 | BusinessSearch |
| OP-12 | ReadModels |
| OP-13 | DocumentContentAccess |

Les invariants de persistance sont fermés : SQL paramétré, Data Mapper, aucun
GenericRepository, `sqlite3` confiné aux adapters/infrastructure, UoW
`BEGIN IMMEDIATE`, commit/rollback explicites, marqueur `operation_ref`, aucune
row SQLite hors boundary et aucune mutation du seed.

## 7. SCN-01 — organisation d'une ressource

```text
WF-0
-> CAP-R01
-> application.read_canonical_resource
-> ResourceLibraryUseCaseInbound
-> GetResourceQuery
-> OP-03
-> SQLite runtime
```

Le chemin réutilise Phase 5 `READ-15/getResource`, Phase 6 M03/IP-03/OP-03 et
l'operationId Phase 8 `getResource`. Le compteur de route vaut 1, la référence
de ressource est préservée et les 4 assertions passent.

```text
version_ref = DEFERRED
include = DEFERRED
```

## 8. SCN-02 — recherche de ressources

AG-02 traverse les ports Evidence puis OP-11/OP-13 sur SQLite réelle. La requête
`absence` résout `notion:absence`. Les canaux STRUCTURED et LEXICAL sont réels ;
RELATIONAL et SEMANTIC sont explicitement indisponibles. Le mode DEGRADED est
légitime, le contenu reste non autoritatif et les 5 assertions passent.

## 9. SCN-03 à SCN-05 — génération, transformation et exercice

### SCN-03

WF-2 appelle AG-03/CAP-G01. La production reste `CANDIDATE`, sans promotion, et
les 4 assertions passent.

### SCN-04

WF-4 obtient une Evidence SQLite réelle `notion:tva`, puis exécute
AG-02 → AG-03/CAP-G02. Target et lineage sont préservées ; les 3 assertions
passent.

### SCN-05

WF-5 avec overlay WF-10 exécute AG-03 → AG-04 → GateEngine. Seule une
GateDecision externe peut autoriser la continuation ; REJECTED bloque tout
downstream. Les 4 assertions passent.

Les ports techniques sont provider-neutral et test-only. Aucun provider réel
n'est appelé ou prétendu calibré.

## 10. SCN-06 à SCN-08 — assessment, correction et QCM

### SCN-06

WF-8 + WF-6 exécutent deux branches Evidence, un JOIN, AG-03, une route CAP-A01
et AG-04. Les 5 assertions passent.

### SCN-07

WF-1 + WF-7 + WF-0 exécutent Evidence, correction CAP-G03 v1→v2, re-review,
arrêt borné et route finale CAP-R02. Les 6 assertions passent.

### SCN-08

WF-9 + WF-3 + WF-11 produisent deux variantes, les joignent, appliquent une
sélection opaque, puis AG-04, CAP-A01, GateEngine et la route CAP-A02. Les 6
assertions passent.

```text
PROMOTION_ROUTE_EXECUTED = TRUE
PERSISTED_BUSINESS_PROMOTION = NOT_CLAIMED
```

## 11. Security, Recovery et Observability

### Security

```text
hostile content remains DATA
authority/capability smuggling blocked
textual gate approval cannot approve
bad Gate lineage fails closed
secret sentinel rejected
structural key smuggling rejected
multi-agent authority escalation rejected
```

### Recovery

```text
UNKNOWN -> reconciliation first
COMMITTED -> never replay
PARTIAL -> never automatic retry
NONE -> retry only through canonical policy/budget/idempotency
mismatch -> fail closed

REAL_BUSINESS_PROMOTION_PERSISTENCE =
NOT_IMPLEMENTED_IN_E_OR_F
```

### Observability

```text
OBSERVABILITY != AUTHORITY

disabled/enabled/failing sink
=> same functional projection

SCN-06 equivalent
SCN-08 equivalent
```

Les logs, traces, métriques et reports ne transportent aucun contenu brut.

## 12. Suite canonique complète G

La façade de G réutilise les owners fermés sans duplication :

```text
SCN-01 -> C2
SCN-02 -> C1
SCN-03/04/05 -> D
SCN-06/07/08 -> E
```

Un unique `EvaluationRunner.run_suite()` exécute les huit cas. Deux runtimes
fraîches et isolées produisent :

```text
run A = PASS / 37/37
run B = PASS / 37/37
JSON A == JSON B byte-for-byte
Markdown A == Markdown B byte-for-byte
generated == committed
seed unchanged
runtime/WAL/SHM cleanup complete
```

## 13. Rapports canoniques

```text
docs/development/PHASE_12_15_G_CANONICAL_SUITE_REPORT.json
size = 7015
sha256 =
7244dc1c362d6e0d9c9d0ee8f29522b8273479067f6353e0fda27d63ad21e1d8
```

```text
docs/development/PHASE_12_15_G_CANONICAL_SUITE_REPORT.md
size = 5061
sha256 =
0dc93478bd7f32284fb802876f7fcaed3b3b18f158ecaecbd871ec6615651c6d
```

Les rapports utilisent le schema 1.0, portent 8 cas et 37 assertions, excluent
le contenu brut et restent des artefacts d'évaluation, jamais une autorité.

## 14. Audit cumulatif H1

```text
cumulative diff =
8 commits
76 files
10996 insertions
10 deletions

unexpected files = 0
blocking duplication = 0
unacknowledged blocking debt = 0

real DB gate =
21 PASS / 0 FAIL / 0 SKIP

transverse =
57 PASS / 0 FAIL / 0 SKIP

cumulative targeted =
1002 PASS / 0 FAIL / 0 SKIP

global clean gate =
3915 PASS / 0 FAIL / 0 SKIP

Ruff = PASS
mypy = PASS / 668 files
compileall = PASS
dependencies = []
```

Une première exécution élevée a vu des runtimes locaux préexistants et ignorés
par Git. Cet incident environnemental non fonctionnel a été isolé par une
relance propre sur une copie temporaire authentifiée du seed ; la gate globale
a alors passé intégralement. Aucun runtime n'est suivi dans Git.

## 15. Rationalisation H1

```text
BLOCKING_DUPLICATION = 0
RATIONALIZATION_REQUIRED_BEFORE_MERGE = FALSE
```

Les specialized adapters sont des mappings légitimes derrière des ports
canoniques, pas des duplicate owners. Aucune consolidation bloquante n'était
requise avant merge.

## 16. Merge H2

```text
OLD_MAIN_SHA =
718804cba2500bec7350d3f37f976949fc5d3735

FUNCTIONAL_SHA =
00d07c0a2c7ad8d949390b0900af53e188c277af

MERGE_MODE =
FAST_FORWARD_ONLY

MERGE_COMMIT_CREATED =
FALSE

NEW_COMMIT_CREATED =
FALSE

FUNCTIONAL_TREE =
0a516f95e7bd8896b8ff9c467ee69b3d6985dc2f
```

Après H2, `main`, `origin/main`, la branche fonctionnelle et sa ref distante
pointaient toutes sur G, avec une divergence `0/0`.

## 17. Dettes explicitement différées

Ces dettes sont reconnues, non masquées et non bloquantes pour la Phase 12.15.

### Phase 12.16

```text
provider/model selection
provider/model calibration
budgets
timeouts
context windows
pedagogical quality rubric calibration
```

### Phase 12.17

```text
EXISTING_RUNTIME_REOPEN_POLICY
PHASE7_REPOSITORY_PROVENANCE_MISMATCH
READ-15 version_ref/include
concrete CAP-R02 Application implementation
concrete CAP-A01 Application implementation
concrete CAP-A02 promotion implementation
REAL_BUSINESS_PROMOTION_PERSISTENCE
other rationalization/debt consolidation
```

## 18. Invariants finaux

```text
PEDAGOGICAL_GOLDEN_CORPUS != PRODUCTION_DATA
PEDAGOGICAL_GOLDEN_CORPUS != USER_PRIVATE_DATA

EVALUATION != AUTHORITY
OBSERVABILITY != AUTHORITY

HOSTILE_CONTENT != AUTHORITY

UNKNOWN_EFFECT_REQUIRES_RECONCILIATION_BEFORE_REPLAY
PARTIAL_EFFECT_NEVER_AUTOMATIC_RETRY
COMMITTED_EFFECT_NEVER_REPLAY

PRODUCTION_CANDIDATE != RESOURCE
PROMOTION_ROUTE != PERSISTED_PROMOTION

PROVIDER_NEUTRAL_RUNTIME_TESTABILITY = TRUE
```

## 19. Statut final Phase 12.15

```text
PHASE 12.15 — CLOSED / MERGED / CANONICAL

FUNCTIONAL_SHA =
00d07c0a2c7ad8d949390b0900af53e188c277af

MERGE_MODE =
FAST_FORWARD_ONLY

ALL_8_CANONICAL_SCENARIOS =
PASS

ALL_37_HARD_ASSERTIONS =
PASS

WF0_TO_WF11_COVERAGE =
COMPLETE

SECURITY_TRANSVERSE =
CLOSED

RECOVERY_TRANSVERSE =
CLOSED

OBSERVABILITY_TRANSVERSE =
CLOSED

REPORT_REPRODUCIBLE =
TRUE

BLOCKING_DUPLICATION =
0

RATIONALIZATION_REQUIRED_BEFORE_MERGE =
FALSE

NEXT_PHASE =
12.16
```
