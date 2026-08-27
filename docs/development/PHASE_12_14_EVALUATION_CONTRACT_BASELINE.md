# Phase 12.14-B — Baseline des contrats du harness d'évaluations

## 1. Objet

Ce lot établit :

```text
OFFLINE_EVALUATION_BOUNDARY
+ CORE_EVALUATION_CONTRACTS
+ STRUCTURAL_VALIDATION
```

Il ne contient aucun runner, scoring, reporting, fournisseur ou scénario
pédagogique canonique.

## 2. Frontière offline

Le core canonique vit sous `evaluation_harness/`. Il est importable sans pytest
et n'est jamais importé par `backend/`. Les futurs adapters pytest et les fakes
restent sous `tests/`.

## 3. Matrice des owners

| Concept | Owner | Rôle du harness |
| --- | --- | --- |
| collecte/exécution de tests | pytest | réutilisation future |
| fakes et fixtures | `tests/support` | réutilisation future |
| Tool/Application authority | policies et routers existants | observation seulement |
| délégation | AG-01 | observation seulement |
| Gate | `GateEngine` | observation seulement |
| runtime | executor/orchestration | target, jamais remplacé |
| recovery | coordinator/replay guard | invariants observés |
| security | owners 12.12 | décisions observées |
| observability | owners 12.13 | facts utilisables comme inputs |
| qualité métier | `backend/modules/quality_evaluation` | aucune relation |
| verdict offline | `evaluation_harness` | constat non autoritaire |

## 4. Décision de package

Le package top-level évite toute dépendance du runtime de production vers le
harness. `backend/agent_runtime/evaluation`, le scaffold métier
`quality_evaluation` et un core sous `tests/support` sont explicitement exclus.

Décision canonique :
[ADR-P12-049](../../architecture/adr/ADR-P12-049-agentic-evaluation-harness-boundary.md).

## 5. Dépendances

```text
evaluation_harness -> stdlib
evaluation_harness -> shared value-safety classifier
tests              -> evaluation_harness + tests/support
backend            -X-> evaluation_harness
```

La réutilisation du classificateur 12.12 évite un scanner de secrets dupliqué.
Le harness n'importe aucun contrat d'autorité, pytest, infrastructure ou SDK.

## 6. Sémantique des verdicts

`EvaluationVerdict` contient exactement :

| Verdict | Sémantique |
| --- | --- |
| PASS | tous les critères applicables sont satisfaits |
| FAIL | un critère normatif est violé |
| INCONCLUSIVE | observations insuffisantes |
| ERROR | évaluation inexécutable ou ininterprétable |
| SKIPPED | non-exécution explicitement configurée |

L'enum n'est pas string-compatible afin d'empêcher toute égalité accidentelle
avec `ALLOW`, `APPROVED`, `SUCCEEDED`, `COMMITTED` ou un statut sécurité.

## 7. Target et tags

Target kinds : `SYSTEM`, `WORKFLOW`, `AGENT`, `PIPELINE`, `BOUNDARY`,
`COMPONENT`. Un target associe seulement kind et code opaque, sans registry,
lookup, import dynamique ou route.

Les tags sont minuscules, normalisés, bornés, uniques et limités à 16. Ils
n'accordent aucune autorité. Aucun fournisseur, modèle, filière ou diplôme n'est
hardcodé.

## 8. EvaluationCase

```text
case_id
schema_version
code
title
target
input_factory_ref
assertion_refs
fixture_ref?
repeat_count
tags
timeout_seconds?
```

Les refs sont opaques. `assertion_refs` n'implémente aucune taxonomie C.
`repeat_count` et timeout sont seulement déclaratifs ; aucun runner n'existe.

## 9. EvaluationSuite

La suite embarque des cases dans l'ordre du caller, sans tri implicite ni suite
imbriquée. Les case IDs sont uniques. La policy d'erreur d'infrastructure est
`CONTINUE` par défaut ou `ABORT_SUITE` explicitement.

## 10. Modèle de résultat

- `CaseExecutionResult` : faits d'une exécution offline ;
- `CaseEvaluationResult` : verdict d'un case et exécutions ordonnées ;
- `SuiteEvaluationResult` : agrégation structurelle de résultats de cases.

`AssertionResult` est différé à C et `ScoreResult` à D. Aucun placeholder opaque
ne prédit leurs modèles.

## 11. Policy d'erreur d'infrastructure

```text
CONTINUE
ABORT_SUITE
CASE_FAIL_IS_NOT_INFRASTRUCTURE_ERROR
```

Le runner E interprétera cette policy. B valide uniquement le vocabulaire et la
cohérence structurelle des résultats.

## 12. Séparation d'autorité

```text
EvaluationResult != DomainValidation
EvaluationResult != GateApproval
EvaluationResult != SecurityDecision
EvaluationResult != RecoveryDecision
EvaluationResult != ObservabilityFact
```

Une suite `PASS` ne contient que des cases `PASS`. Cette règle ne lui confère
aucune autorité sur les owners observés.

## 13. Sécurité et confidentialité

Les contrats n'exposent aucun champ metadata/config/payload/prompt/output,
exception brute, Evidence content ou reasoning. Identités, refs, titres et
reason codes sont bornés. Les identités refusent URLs, chemins et valeurs
classifiées sensibles.

## 14. Immutabilité et déterminisme

Tous les contrats sont des dataclasses frozen/slotted. Les collections sont des
tuples, l'ordre du caller est conservé et les doublons structurants sont
refusés. Il n'existe aucune clock, UUID, random, environnement, filesystem,
concurrence ou I/O dans le package.

Limites B : identités 128, titres 256, tags 16, assertions 64, cases 256,
répétitions 100, timeout 86 400 secondes, observations 64 et reason codes 32.

## 15. Scopes différés

- C : taxonomie et exécution des assertions/invariants ;
- D : scores, rubrics, pondération et agrégation ;
- E : runner, fixtures, répétitions, timeouts et isolation d'état ;
- F : JSON/Markdown/JUnit, comparison et artifacts ;
- G : intégration aux frontières agent/runtime ;
- 12.15 : scénarios pédagogiques E2E ;
- 12.16 : provider/model et calibration.

Réservation :

```text
HARD_INVARIANT_FAILURE_CANNOT_BE_HIDDEN_BY_WEIGHTED_SCORE
```

## 16. Registre de réutilisation des phases futures

| Primitive | Décision |
| --- | --- |
| pytest | REUSE |
| `tests/support` fakes | REUSE |
| `tests/e2e/core` | 12.15 |
| `tests/providers` | 12.16 |
| `BudgetState` | 12.16 CALIBRATE ONLY |
| `BudgetAccountingPolicy` | 12.16 REUSE |
| `AgentRuntimePolicy` | 12.16 CALIBRATE ONLY |
| context guardrails | 12.16 CALIBRATE ONLY |
| local rationalizations | 12.17 AGGREGATE |
| H1/H2/H3 pattern | 12.18 REUSE |

## 17. Statut de rationalisation

```text
RATIONALIZATION = NO_DUPLICATE_TEST_RUNTIME_CREATED
```
