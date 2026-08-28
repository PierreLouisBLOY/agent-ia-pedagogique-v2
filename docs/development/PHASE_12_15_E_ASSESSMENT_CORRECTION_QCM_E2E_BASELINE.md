# Phase 12.15-E — Baseline assessment, correction et QCM E2E

## 1. Parent, portée et ADR

E a pour parent exact `67503cf62fb176ed445930a4e6893f6aefb99fd2`
(D). Le lot ferme uniquement SCN-06, SCN-07 et SCN-08, soit les 17 hard
assertions restantes du corpus canonique. Il ne commence pas F.

`BACKEND_PRODUCTION_DELTA = 0` et `ADR_REQUIRED = NO`. E compose exclusivement
les owners, contrats, capabilities, workflows et routes déjà canoniques. Aucun
nouveau moteur métier, agent, workflow, capability, stockage ou provider n'est
créé.

## 2. Assertions fermées

| Scénario | Assertions hard |
| --- | --- |
| SCN-06 | workflow, evidence-fanout-count, join-before-generation, validation-review-order, assessment-marking-scheme |
| SCN-07 | workflow, evidence-available, correction-version-increases, review-correction-order, bounded-stop, final-application-path |
| SCN-08 | workflow, variant-count, join-selection-order, independent-review, validation-gate-promotion-order, render-effect-count |

Le total exécuté est `5 + 6 + 6 = 17/17`.

## 3. Matrice des owners

| Responsabilité | Owner réel | Boundary test-only |
| --- | --- | --- |
| sélection/compilation | WorkflowSelector / PlanCompiler | aucune |
| ordonnancement | DeterministicScheduler / PlanExecutor | StepRunner et guard sans effet |
| Evidence | AG-02 EvidenceAgent / RetrievalCoordinator | search/content sur fixtures synthétiques |
| génération/correction | AG-03 GeneratorAgent / GenerationCoordinator / guard / materialization | RecordingGenerationPort |
| revue | AG-04 ReviewerAgent / ReviewCoordinator | RecordingReviewPort |
| validation/read/promotion | UseCaseRouter et registre C-12/C-13 | RecordingApplicationInbound |
| gate | GateEngine | RecordingGateDecisionSource externe |
| sélection QCM | décision runtime opaque | sélection déterministe de la première ref jointe |
| rendu | aucun owner demandé | recording render port non appelé |

Les fakes fournissent uniquement les boundaries techniques déterministes ; ils
ne remplacent jamais les owners.

## 4. Audit Application R02/A01/A02

| Capability | use_case_id | Implémentation Application concrète | Owner module | Usage E |
| --- | --- | --- | --- | --- |
| CAP-R02 | `application.read_production` | non | M08/lecture Production encore shell | UseCaseRouter + inbound enregistré |
| CAP-A01 | `application.run_deterministic_validation` | non | M06 validation_control encore shell | UseCaseRouter + outcome fermé |
| CAP-A02 | `application.request_promotion` | non | M07 lifecycle_promotion encore shell | UseCaseRouter + idempotency + inbound enregistré |

Les descriptors, policies et routes existent réellement. E prouve leur handoff
Application et leur ordre, pas une sémantique métier persistée :

```text
PROMOTION_ROUTE_EXECUTED = TRUE
PERSISTED_BUSINESS_PROMOTION = NOT_CLAIMED
```

## 5. Stratégie provider-neutral

Aucun SDK, provider, modèle, réseau ou SQLite n'est utilisé. Les contenus sont
courts, synthétiques et déterministes. AG-02/03/04, guards, lineage,
materialization, selector/compiler, scheduler/executor, UseCaseRouter et
GateEngine restent les implémentations réelles.

## 6. SCN-06 — WF-8 + WF-6

Le selector reçoit deux branches Evidence indépendantes, production,
validation déterministe et revue indépendante. Le compiler produit :

```text
AG-02 branch 0 / CAP-E01
AG-02 branch 1 / CAP-E01
-> JOIN / CAP-O04
-> AG-03 / CAP-G01
-> Application / CAP-A01
-> AG-04 / CAP-V01
```

Chaque branche construit son propre EvidenceRequest, son propre EvidenceAgent et
son EvidenceSet, à partir d'une source distincte de la fixture. Les requêtes et
sorties sont distinctes, et le join dépend des deux branches. Le witness du vrai
PlanExecutor observe `EVIDENCE_BRANCH_0, EVIDENCE_BRANCH_1, JOIN, GENERATION`.

AG-03 produit une candidate `CANDIDATE`, operation `GENERATE`, lineage CAP-G01,
avec evidence refs bornées et les sections exactes `instructions`, `questions`,
`marking-scheme`. Le corps du barème n'est jamais évalué. La route CAP-A01 est
appelée une fois avant la revue AG-04, `COMPLETED` et `ACCEPTABLE`. SCN-06 passe
`5/5`.

## 7. SCN-07 — WF-1 + WF-7 + WF-0

La fixture apporte la production v1 déjà revue, le finding majeur et la
contrainte à préserver. AG-02 matérialise d'abord un EvidenceSet synthétique non
vide, sans en faire une autorité.

Le vrai CAP-G03 reçoit une CorrectionRequest fermée : target v1, prior review,
finding majeur, evidence refs et preserve constraint. Le RecordingGenerationPort
retourne `CORRECT`, puis le vrai guard et la vraie correction materialization
créent la candidate v2. L'identité logique est conservée, la version change de
v1 à v2, le finding est entièrement adressé et la candidate reste `CANDIDATE`.

Le witness distingue explicitement :

```text
PRIOR_REVIEW_FINDING_AVAILABLE
-> CORRECTION
-> RE_REVIEW
-> FINAL_APPLICATION_READ
-> STOP
```

Le re-review AG-04 est acceptable. Une seule correction est exécutée. La
régression d'une deuxième correction exige une nouvelle version de Plan
(`plan_version 2`) avec le même DAG, jamais une boucle locale implicite. Le chemin
final appelle réellement CAP-R02 / `application.read_production` via le routeur,
sans claim de lecture persistée. SCN-07 passe `6/6`.

## 8. SCN-08 — WF-9 + WF-3 + WF-11

Le compiler produit deux branches AG-03/CAP-G01, un join CAP-O04, une décision
runtime, une revue AG-04, une validation CAP-A01, une gate CAP-O05 et une route
de promotion CAP-A02.

Les deux candidates QCM ont des identités distinctes et les sections exactes
`question`, `options`, `answer-key`, `feedback`. Le PlanExecutor observe :

```text
VARIANT_0 -> VARIANT_1 -> JOIN -> SELECTION
```

La sélection est `opaque_deterministic_first_joined_ref` : elle choisit une ref
jointe sans score, comparaison qualitative ni vérité pédagogique. La candidate
sélectionnée est revue une fois par AG-04 avec une target/version exacte et sans
payload mutable partagé.

La validation route CAP-A01 précède le GateEngine réel. La décision APPROVED est
liée au même request/run/step/correlation et produit
`matrix_gate_satisfied=true`. CAP-A02 est ensuite routée une seule fois avec la
clé d'idempotence `promotion:scn-08:0`. La régression REJECTED n'appelle jamais
la route de promotion.

Le recording render port n'est jamais invoqué : actual `0`, maximum de policy
du scénario `0`. CAP-A02 n'est pas comptée comme un effet de rendu. SCN-08 passe
`6/6`.

## 9. Minimisation, rubrics et tags transverses

Les snapshots contiennent uniquement codes, comptes, ordres, sections, booléens,
versions logiques, routes, disposition de gate et compte d'effet. Les fixtures,
textes générés, extraits Evidence, corps du barème, QCM/options/feedback et marker
hostile sont vérifiés absents octet pour octet des reports JSON et Markdown.

Aucun scoring plan n'est fourni. Assessment clarity, marking-scheme coherence,
correction quality, remediation clarity, distractor quality et feedback quality
restent déclaratifs jusqu'à 12.16.

Les tags `security.exfiltration`, `recovery.effectful-promotion` et
`observability.equivalence` ne sont pas clos par E. Le nominal préserve le marker
comme DATA, n'effectue ni réseau, ni retry/replay, ni reconciliation UNKNOWN et
n'émet que les events minimaux. Ces programmes appartiennent à F.

## 10. Validations exécutées

Le gate E ciblé a exécuté `12 passed`, dont le full harness à `17/17` hard
assertions. La sélection de régressions D/C/corpus/owners/Application/Gate/
scheduler/compiler/harness a exécuté `430 passed` et `19 skipped` conditionnels
SQLite ; E n'utilise pas SQLite et n'exige pas leur réexécution réelle.

La globale finale a exécuté `3830 passed` et `20 skipped` conditionnels en
173,21 s. Python 3.12.13, Ruff global, mypy sur les `638` sources backend et les
`30` sources du harness, compileall backend/harness/tests et `git diff --check`
passent. Les dépendances projet restent `[]`.

## 11. Handoff F

À fermeture et push de E :

```text
ALL_8_CANONICAL_SCENARIOS_FUNCTIONALLY_CLOSED = TRUE
NEXT_GATE = 12.15-F_READY
```

F devra traiter les variants adversariaux security/recovery/observability sans
modifier rétrospectivement les chemins fonctionnels de SCN-01 à SCN-08.
