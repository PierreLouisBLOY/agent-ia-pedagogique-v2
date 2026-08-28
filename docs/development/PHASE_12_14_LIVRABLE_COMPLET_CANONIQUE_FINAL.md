# Phase 12.14 — Livrable complet canonique final

## 1. Statut final

La Phase 12.14 livre le harness offline de tests et d'évaluations agentiques,
son intégration test-only avec les owners runtime canoniques et ses projections
de reporting minimisées. La fonctionnalité B→G a été intégrée sur `main` par
fast-forward strict. H3 ferme la phase par ce document uniquement.

```text
POST_MERGE_AUDIT = PASS
CANONICAL_FINAL_DELIVERY = COMPLETE_PENDING_DOCUMENTARY_COMMIT
HANDOFF_TO_12_15 = READY_PENDING_DOCUMENTARY_COMMIT
```

## 2. Entry baseline

```text
ENTRY_BASELINE = 3f8878399071860abf898ca12942d5a5530277f7
FUNCTIONAL_SHA = fae042fd3dee69168e94d71d2267cdafae5471bb
FUNCTIONAL_TREE = b274852caac05520e948f6bbd9448380b0c0a1ac
FUNCTIONAL_PARENT = 85bef9b696b157409520e71c9d2478c40d6b974d
```

La baseline d'entrée est la clôture canonique de la Phase 12.13. G possède F
comme parent unique et conserve le tree fonctionnel audité en H1 et H2.

## 3. Topologie fonctionnelle et documentaire

La Phase 12.14-A est un audit de réutilisation et d'anti-duplication sans commit
propre. Les lots B→G constituent six commits fonctionnels linéaires. H1 est un
audit sans mutation. H2 déplace `main` sur G par fast-forward strict. H3 ajoute
exactement ce livrable dans un commit documentaire ayant G pour parent direct.

```text
12.14-A  audit sans commit
    |
ENTRY_BASELINE
    |
    B -- C -- D -- E -- F -- G  fonctionnel
                              |
                              H1 audit-only
                              |
                              H2 fast-forward de main
                              |
                              H3 commit documentaire unique
```

## 4. Phase 12.14-A — audit reuse et anti-duplication

A a inventorié les contrats, owners, scores, runners, mécanismes de recovery,
surfaces observability, fakes et scaffolds existants. Il a conclu qu'un harness
offline autonome était nécessaire sans réutiliser comme synonymes les résultats
runtime, les scores métier, les métriques ou le futur domaine
`quality_evaluation`.

A n'a pas de commit propre. Sa décision gouverne B→G : réutiliser les owners
canoniques derrière des ports et adapters de test, sans recopier leur politique
et sans créer une nouvelle autorité.

## 5. Phase 12.14-B — contracts

B établit une version de schéma propre au harness et des identités, codes et
références opaques, sûrs et bornés. `EvaluationVerdict` est un vocabulaire fermé
distinct des décisions Tool, Gate et runtime. `EvaluationTargetKind`, les tags,
`EvaluationCase` et `EvaluationSuite` sont des contrats data-only immutables.

La suite fixe explicitement sa politique en cas d'erreur d'infrastructure. Les
résultats d'exécution, de case et de suite sont frozen, bornés et cohérents avec
les IDs et répétitions déclarés. Aucun contrat n'accepte de callable, mapping de
metadata arbitraire, payload opaque ou champ d'autorité.

```text
PASS != ALLOW
PASS != APPROVED
PASS != SUCCEEDED
PASS != COMMITTED
```

Décision : [ADR-P12-049](../../architecture/adr/ADR-P12-049-agentic-evaluation-harness-boundary.md).

## 6. Phase 12.14-C — assertions et invariants

C livre huit kinds fermés : `EXACT`, `STRUCTURAL`, `COUNT`, `SEQUENCE`,
`MEMBERSHIP`, `RANGE`, `FORBIDDEN_CONTENT` et `INVARIANT`. Les observations
forment une algèbre immutable de scalaires, séquences et objets ordonnés. Les
floats, valeurs ambiguës et objets runtime sont refusés.

Les limites canoniques incluent une profondeur de 8, 64 éléments par séquence,
32 champs par objet, 4096 caractères par chaîne et 512 nœuds au total. Les
chaînes adversariales synthétiques restent admissibles comme données de test
bornées mais ne sont jamais copiées dans un `AssertionResult`.

Le catalogue est immutable, ordonné, unique et borné. Les sources d'observation
et évaluateurs d'invariant sont injectés. Chaque référence est résolue exactement
une fois par assertion, les pannes sont contenues derrière des reason codes
fermés et les résultats restent sans valeur brute.

```text
ASSERTION_RESULT_NEVER_CREATES_AUTHORITY
HARD_ASSERTION_FAILURE_CANNOT_BE_HIDDEN_BY_SCORE
```

Décision : [ADR-P12-050](../../architecture/adr/ADR-P12-050-agentic-evaluation-assertion-semantics.md).

## 7. Phase 12.14-D — scoring, rubrics et aggregation

D introduit `NormalizedScore` comme rationnel exact réduit dans `[0,1]`, sans
float, arrondi ou dépendance au contexte Decimal global. `ScoreStatus`, le port
de scorer injecté, les critères et rubrics ont des vocabulaires et bornes
fermés. Les poids sont strictement positifs et leur somme rationnelle vaut
exactement 1.

L'agrégation conserve tous les critères et applique la priorité
`ERROR > INCONCLUSIVE > SCORED`. Un critère absent, dupliqué, supplémentaire ou
incohérent interdit toute renormalisation partielle. Score et verdict restent
indépendants : un score élevé ne masque pas un hard fail et un score faible ne
transforme pas un PASS en refus d'autorité.

```text
SCORE_IS_MEASUREMENT_NOT_AUTHORITY
```

Décision : [ADR-P12-051](../../architecture/adr/ADR-P12-051-agentic-evaluation-scoring-rubric-semantics.md).

## 8. Phase 12.14-E — runner, répétitions, fixtures et timeouts

E livre un runner offline séquentiel. Chaque répétition obtient une fixture et
un input frais, effectue exactement un appel target puis exécute le cleanup dans
un `finally`. Il n'existe ni retry silencieux, replay recovery, boucle non bornée
ou concurrence implicite.

La deadline est coopérative et déterministe. Un timeout ou une panne de cleanup
devient une erreur d'infrastructure explicite. `RepetitionEvaluationResult`
porte les résultats C/D par répétition et rationalise la compatibilité avec les
résultats plats antérieurs. La précédence de case reste explicite et la suite
applique `CONTINUE` ou `ABORT` uniquement aux erreurs d'infrastructure.

```text
EVALUATION_REPETITION_IS_NOT_RUNTIME_RETRY
EVALUATION_REPETITION_IS_NOT_RECOVERY_REPLAY
```

Décision : [ADR-P12-052](../../architecture/adr/ADR-P12-052-agentic-evaluation-runner-lifecycle.md).

## 9. Phase 12.14-F — reporting, comparaison et artifacts

F projette uniquement la matrice de reportabilité allowlistée. Le schéma de
rapport est `1.0`. JSON et Markdown sont déterministes et partagent la même
surface minimisée. Aucun output, observation, texte métier ou exception brute
n'est reporté. Les scores sont sérialisés sous forme rationnelle, jamais float.

La sortie sérialisée est plafonnée à 2 000 000 octets sans troncature silencieuse.
La comparaison est descriptive, alignée par identités et expose un
`RationalScoreDelta` signé exact, sans winner, acceptance ou release gate. Les
artifacts ont des noms path-safe ; le core n'effectue aucun I/O filesystem. Le
sink est injecté, tenté une seule fois et sa panne est isolée. Le bridge JUnit
reste explicitement différé.

```text
REPORTING_IS_PROJECTION_NOT_AUTHORITY
COMPARISON_RESULT != RELEASE_GATE
```

Décision : [ADR-P12-053](../../architecture/adr/ADR-P12-053-agentic-evaluation-reporting-comparison-artifacts.md).

## 10. Phase 12.14-G — intégration test-only

G ajoute uniquement un ADR, une baseline et des fichiers sous `tests/`. Aucun
fichier production ou core harness n'est modifié par ce lot. Les adapters de
test invoquent les vrais owners AG-01, AG-02, AG-03 et AG-04 ainsi que les owners
Tool, Application, Gate, security, recovery et observability.

Les projections exposent des faits fermés et minimisés. Tous les effets externes
sont fake ou in-memory. Les tests prouvent le chemin complet contracts → runner
→ assertions/scoring → résultats → reporting/comparison, ainsi que plusieurs
répétitions avec état frais, nombre d'appels exact et absence de retry.

```text
TEST_ADAPTERS_MAY_DEPEND_ON_BOTH_SIDES
PRODUCTION_RUNTIME_MUST_NOT_DEPEND_ON_EVALUATION_HARNESS
```

Décision : [ADR-P12-054](../../architecture/adr/ADR-P12-054-agentic-evaluation-runtime-integration-boundary.md).

## 11. Phase 12.14-H1 — audit cumulatif pré-merge

H1 a vérifié les refs, la chaîne B→G, le diff cumulé, les ADR, les dépendances,
les contrats, l'autorité, la privacy, security, recovery, observability et les
frontières 12.15/12.16. Le delta fonctionnel comptait 55 fichiers et 11 895
insertions cumulées, sans changement `backend/`.

```text
targeted = 335 PASS
global = 3757 PASS
Python = 3.12.13
Ruff = PASS
mypy backend = PASS / 618 files
mypy harness = PASS / 30 files
compileall backend/harness/tests = PASS
dependencies = []
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_READY = TRUE
```

H1 n'a modifié aucun fichier et n'a créé aucun commit.

## 12. Phase 12.14-H2 — fast-forward strict

H2 a exécuté uniquement :

```text
git merge --ff-only phase12/12-14-agentic-evaluation-harness
```

Le déplacement de `main` de l'entry baseline vers G n'a créé aucun merge commit,
rebase, squash, cherry-pick ou changement artificiel de tree. Après push,
`main`, `origin/main` et les refs locale/distante de la branche fonctionnelle
pointaient sur G ; la relation était `0/0`.

```text
MERGE_MODE = FAST_FORWARD_ONLY
```

## 13. Phase 12.14-H3 — clôture documentaire post-merge

Le préflight H3 a confirmé `main`, `origin/main` et les deux refs fonctionnelles
sur G, le merge-base G, le parent F, le tree attendu et un worktree propre. H3 a
réexécuté la gate normative sans corriger le code. Son delta est exactement ce
fichier Markdown ; il ne modifie ni code, test, ADR, baseline, configuration,
dépendance ou scaffold.

Le statut enregistré dans ce document reste pending jusqu'à la création du
commit documentaire unique. Le SHA de ce commit est rapporté par le rapport H3
et le fichier n'est pas réécrit uniquement pour s'auto-référencer.

## 14. Index des ADR 049→054

| ADR | Décision canonique | Lot |
| --- | --- | --- |
| [ADR-P12-049](../../architecture/adr/ADR-P12-049-agentic-evaluation-harness-boundary.md) | frontière offline du harness | B |
| [ADR-P12-050](../../architecture/adr/ADR-P12-050-agentic-evaluation-assertion-semantics.md) | sémantique assertions/invariants | C |
| [ADR-P12-051](../../architecture/adr/ADR-P12-051-agentic-evaluation-scoring-rubric-semantics.md) | scoring et rubrics rationnels | D |
| [ADR-P12-052](../../architecture/adr/ADR-P12-052-agentic-evaluation-runner-lifecycle.md) | cycle de vie runner/répétitions | E |
| [ADR-P12-053](../../architecture/adr/ADR-P12-053-agentic-evaluation-reporting-comparison-artifacts.md) | reporting/comparison/artifacts sûrs | F |
| [ADR-P12-054](../../architecture/adr/ADR-P12-054-agentic-evaluation-runtime-integration-boundary.md) | intégration runtime test-only | G |

Ces décisions forment une progression monotone. Aucune phase ultérieure ne
réattribue l'autorité ou ne renverse une dépendance établie plus tôt.

## 15. Architecture finale

```text
EvaluationCase / EvaluationSuite
        |
        v
EvaluationRunner
        |
        +--> test-only target adapters
        |       |
        |       v
        |   canonical runtime owners
        |
        +--> safe observation snapshots
                |
                +--> AssertionEvaluator
                |
                +--> ScoreEvaluator / RubricAggregator
        |
        v
SuiteEvaluationResult
        |
        v
EvaluationReportProjector
        |
        +--> JSON / Markdown
        |
        +--> descriptive comparison
        |
        +--> safe artifact boundary
```

Graphe de dépendances autorisé :

```text
evaluation_harness -> stdlib
evaluation_harness -> backend.shared_kernel._value_safety
tests              -> evaluation_harness
tests              -> backend owners

backend             -X-> evaluation_harness
evaluation_harness  -X-> backend.agent_runtime
evaluation_harness  -X-> backend.infrastructure
```

Le futur domaine `backend/modules/quality_evaluation` reste inchangé et non
importé par le harness.

## 16. Authority matrix

| Couche | Autorité canonique |
| --- | --- |
| Tool | `ALLOW` |
| Application | `REQUEST` |
| Agent | `DELEGATE` |
| Gate | `APPROVED` |
| Runtime | orchestration/execution |
| Recovery | technical admissibility |
| Security | restriction-only |
| Observability | observation-only |
| Evaluation | offline assertion/measurement only |

```text
EVALUATION_NEVER_CREATES_AUTHORITY
```

## 17. Privacy et security

Les contrats et rapports excluent prompt, raw output, Evidence text, contenu
généré ou de review, réponse provider, private reasoning, exception brute,
chemin privé, credential réel et metadata/payload arbitraire. Les reason codes,
IDs opaques, comptes et statuts fermés sont les seules projections nécessaires.

Les fixtures adversariales sont synthétiques, bornées et réservées aux tests.
Elles prouvent les refus et la minimisation sans atteindre les résultats,
rapports ou artifacts.

## 18. Invariants recovery préservés

```text
UNKNOWN -> reconcile before replay
PARTIAL -> never auto retry
COMMITTED -> never replay
NONE -> only potentially retryable
COMMITTED != SUCCEEDED without trusted terminal receipt
no synthetic idempotency identity
no retry loop
recovery technical-only
```

Le harness constate ces faits via les owners canoniques. Il ne possède ni ne
réimplémente ReplayGuard, RetryPolicy, ledger, reconciliation ou recovery.

## 19. Invariants observability préservés

Les échecs d'observability sont failure-neutral et ne modifient pas le résultat
runtime. `MetricPoint` et `EvaluationScore` restent des contrats, owners et
cycles de vie distincts. Telemetry n'accorde aucune autorité ; evaluation et
reporting offline ne deviennent pas de la telemetry production.

```text
OBSERVABILITY_FAILURE_DOES_NOT_CHANGE_RUNTIME_OUTCOME
METRIC_POINT != EVALUATION_SCORE
NO_TELEMETRY_AUTHORITY
```

## 20. Tests et contrôles statiques

Preuves H1 :

| Validation | Résultat |
| --- | --- |
| sélection cumulative | 335 PASS |
| suite globale | 3757 PASS |
| Python | 3.12.13 |
| Ruff | PASS |
| mypy backend | PASS — 618 fichiers |
| mypy evaluation_harness | PASS — 30 fichiers |
| compileall backend/harness/tests | PASS |

Gate normative H3 exécutée avant création de ce document :

| Validation | Résultat |
| --- | --- |
| Python | 3.12.13 |
| suite globale H3 | 3757 PASS en 170,91 s |
| `python -m ruff check .` | PASS |
| `python -m mypy backend` | PASS — 618 fichiers |
| `python -m mypy evaluation_harness` | PASS — 30 fichiers |
| `python -m compileall backend` | PASS |
| `python -m compileall evaluation_harness` | PASS |
| `python -m compileall tests` | PASS |
| `git diff --check` | PASS |

## 21. Dépendances

```text
[project].dependencies = []
```

La Phase 12.14 n'ajoute aucune dépendance runtime, SDK provider, client réseau,
framework, serializer tiers ou moteur de template.

## 22. Rationalisation finale

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

- pytest exécute les tests ; `EvaluationRunner` orchestre les évaluations offline
  et ne doit pas devenir un runner de test générique ;
- les scores domain/review/retrieval expriment leurs domaines, tandis que
  `EvaluationScore` est une mesure offline provider-neutral ;
- les résultats runtime commandent et décrivent l'exécution, tandis que les
  résultats d'évaluation en sont des constats offline ;
- recovery replay agit sous admissibilité technique, tandis qu'une répétition
  d'évaluation est une exécution déclarée et fraîche ;
- les métriques observability décrivent la production, tandis que les scores
  d'évaluation appartiennent aux suites offline ;
- `quality_evaluation` est un futur domaine métier, pas le harness agentique ;
- les production owners gardent leur politique ; les adapters G traduisent
  uniquement des faits dans les tests.

Fusionner ces primitives mélangerait autorité, cycle de vie ou sémantique. Aucune
consolidation sûre n'est donc réalisée dans la clôture documentaire.

## 23. Dettes différées à 12.17

1. Challenger globalement le couplage privé intentionnel
   `evaluation_harness -> backend.shared_kernel._value_safety`.
2. Examiner les imports test-only des adapters G vers des helpers privés de
   tests d'intégration, sans déplacer ces adapters en production.
3. Réévaluer la compatibilité transitoire entre résultats plats B/C/D et modèle
   par répétition E lorsque tous les consommateurs auront migré.

```text
DEFERRED_TO_12_17 = TRUE
BLOCKER_12_14 = FALSE
```

## 24. Frontière 12.15

```text
tests/e2e/core = .gitkeep only
12.15_NOT_STARTED = TRUE
```

La Phase 12.14 ne crée aucun scénario pédagogique canonique. La Phase 12.15
utilisera le harness désormais canonique pour construire l'intégration
end-to-end sur ces scénarios, sans modifier rétroactivement les responsabilités
du harness.

## 25. Frontière 12.16

```text
tests/providers = .gitkeep only
```

Aucun provider, model name, judge model, pricing ou calibration n'est introduit.
`BudgetState`, `BudgetAccountingPolicy`, les deadlines d'`AgentRuntimePolicy` et
les context guardrails existent déjà. La Phase 12.16 devra les calibrer et non
les réimplémenter.

## 26. Artifacts et fichiers canoniques

Les artifacts canoniques de la phase sont :

- les six ADR [049](../../architecture/adr/ADR-P12-049-agentic-evaluation-harness-boundary.md),
  [050](../../architecture/adr/ADR-P12-050-agentic-evaluation-assertion-semantics.md),
  [051](../../architecture/adr/ADR-P12-051-agentic-evaluation-scoring-rubric-semantics.md),
  [052](../../architecture/adr/ADR-P12-052-agentic-evaluation-runner-lifecycle.md),
  [053](../../architecture/adr/ADR-P12-053-agentic-evaluation-reporting-comparison-artifacts.md)
  et [054](../../architecture/adr/ADR-P12-054-agentic-evaluation-runtime-integration-boundary.md) ;
- les baselines [contracts](PHASE_12_14_EVALUATION_CONTRACT_BASELINE.md),
  [assertions](PHASE_12_14_ASSERTION_BASELINE.md),
  [scoring](PHASE_12_14_SCORING_RUBRIC_BASELINE.md),
  [runner](PHASE_12_14_RUNNER_LIFECYCLE_BASELINE.md),
  [reporting](PHASE_12_14_REPORTING_COMPARISON_BASELINE.md) et
  [intégration runtime](PHASE_12_14_RUNTIME_INTEGRATION_BASELINE.md) ;
- le package `evaluation_harness/` ;
- les tests unit, architecture, support et intégration associés ;
- ce livrable complet canonique final.

Aucune donnée runtime, sortie générée, base binaire ou secret n'appartient à ces
artifacts.

## 27. Chaîne des SHA Git

```text
ENTRY_BASELINE = 3f8878399071860abf898ca12942d5a5530277f7
B = 19ed05555159217ab13cb02291d85b22378b7dd4
C = b3985626f547def824d29bb797ac746b6ef47190
D = ea01fd98db7e2dd41c7f1ab9f397752a6859c774
E = c9daa394d10371648246202ce6a34c9bf357c033
F = 85bef9b696b157409520e71c9d2478c40d6b974d
G / FUNCTIONAL_SHA = fae042fd3dee69168e94d71d2267cdafae5471bb
FUNCTIONAL_TREE = b274852caac05520e948f6bbd9448380b0c0a1ac
```

Les parents sont exactement entry→B→C→D→E→F→G. Aucun merge commit n'existe
dans la chaîne fonctionnelle. Le SHA documentaire H3 est volontairement publié
dans le rapport de clôture après commit, sans second commit auto-référentiel.

## 28. Décision de clôture

Le post-merge audit est PASS. Les frontières de dépendance, d'autorité, privacy,
security, recovery et observability sont préservées. Les tests et contrôles
statiques H3 sont verts. Le delta H3 est documentaire uniquement et ne commence
ni 12.15 ni 12.16.

```text
PHASE 12.14-H3 — PENDING DOCUMENTARY COMMIT
PHASE 12.14 — FUNCTIONALLY MERGED
FUNCTIONAL_SHA = fae042fd3dee69168e94d71d2267cdafae5471bb
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_MODE = FAST_FORWARD_ONLY
NEXT_PHASE = 12.15
PHASE_12_15_SCOPE = INTEGRATION_END_TO_END_SCENARIOS_PEDAGOGIQUES_CANONIQUES
```

## 29. Handoff 12.15

La Phase 12.15 reçoit un harness offline complet, testé et intégré aux owners
canoniques par des adapters exclusivement test-only. Son périmètre est la
création de scénarios pédagogiques canoniques end-to-end sous `tests/e2e/core`,
avec réutilisation des contrats, assertions, scoring, runner et reporting 12.14.

```text
NEXT_PHASE = 12.15
PHASE_12_15_SCOPE = INTEGRATION_END_TO_END_SCENARIOS_PEDAGOGIQUES_CANONIQUES
```

La Phase 12.15 n'est pas commencée par ce lot documentaire.
