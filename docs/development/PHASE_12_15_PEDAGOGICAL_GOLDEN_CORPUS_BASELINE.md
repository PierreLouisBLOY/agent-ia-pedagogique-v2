# Phase 12.15-B — Baseline du corpus pédagogique golden

## 1. Parent et statut

Le lot B part de la clôture documentaire canonique 12.14 :

```text
PARENT = 718804cba2500bec7350d3f37f976949fc5d3735
GOLDEN_CORPUS_OWNER = 12.15
REOPEN_12_14 = NO
```

La décision d'architecture est
[ADR-P12-055](../../architecture/adr/ADR-P12-055-canonical-pedagogical-e2e-corpus-boundary.md).

## 2. Frontière

12.15-B ajoute uniquement des déclarations et preuves sous `tests/`, un ADR et
ce document. `backend/` et `evaluation_harness/` restent inchangés. Le corpus
compose les contrats 12.14 et n'en recopie aucune validation.

```text
tests/e2e/core -> evaluation_harness
tests/e2e/core -> WorkflowKind / BASELINE_WORKFLOW_CATALOG
backend -X-> tests/e2e
evaluation_harness -X-> tests/e2e
```

## 3. Architecture du corpus

| Fichier | Responsabilité |
| --- | --- |
| `tests/e2e/core/catalog.py` | wrapper, intents, huit scénarios, suite et couverture WF |
| `tests/e2e/core/fixtures.py` | niveaux, sections et fixtures synthétiques sûres |
| `tests/e2e/core/expectations.py` | assertion catalog et rubrics déclaratives |
| `tests/unit/test_pedagogical_e2e_catalog.py` | cohérence data-only |
| `tests/architecture/test_pedagogical_e2e_catalog_fitness.py` | frontières et interdictions |

Aucun `__init__.py` ou `adapters.py` n'est nécessaire en B.

## 4. Huit scénarios et couverture WF

| ID | Niveau | Intent | WF |
| --- | --- | --- | --- |
| SCN-01 | PREMIERE_STMG | RESOURCE_ORGANIZATION | WF-0 |
| SCN-02 | TERMINALE_STMG | RESOURCE_SEARCH | WF-1 |
| SCN-03 | PREMIERE_STMG | COURSE_CREATION | WF-2 |
| SCN-04 | BTS_CG_1 | RESOURCE_TRANSFORMATION | WF-4 |
| SCN-05 | TERMINALE_STMG | EXERCISE_CREATION | WF-5 → overlay WF-10 |
| SCN-06 | BTS_CG_1 | ASSESSMENT_CREATION | WF-8 → WF-6 |
| SCN-07 | BTS_CG_2 | CORRECTION_REMEDIATION | WF-1 → WF-7 → WF-0 |
| SCN-08 | BTS_CG_2 | QCM_QUIZ_CREATION | WF-9 → WF-3 → WF-11 |

Traçabilité inverse :

```text
WF-0  -> SCN-01, SCN-07
WF-1  -> SCN-02, SCN-07
WF-2  -> SCN-03
WF-3  -> SCN-08
WF-4  -> SCN-04
WF-5  -> SCN-05
WF-6  -> SCN-06
WF-7  -> SCN-07
WF-8  -> SCN-06
WF-9  -> SCN-08
WF-10 -> SCN-05
WF-11 -> SCN-08
```

La fonction pure `workflow_coverage()` projette ce registre dans l'ordre du
catalogue runtime. Chaque `WorkflowKind` apparaît au moins une fois.

## 5. Niveaux et intents

Les quatre niveaux sont des `PedagogicalLevelCode` test-only : Première STMG,
Terminale STMG, BTS CG 1 et BTS CG 2. Ils n'affirment aucun programme officiel
et ne créent aucun enum métier.

Les huit intents classent exactement les huit scénarios. Ils ne sont ni des
capabilities, ni des routes Application, ni des permissions.

## 6. EvaluationCase et target policy

Chaque wrapper compose un véritable `EvaluationCase`. La target utilise
`EvaluationTargetKind.WORKFLOW` comme coordonnée opaque parce que les scénarios
déclarent un parcours complet ; cette target ne possède aucune lookup policy ou
autorité d'exécution.

Les case IDs, codes, targets, fixture refs, input factory refs et assertion refs
sont caller-supplied, déterministes et bornés. L'input factory ref commune est
déclarée mais non implémentée en B.

## 7. Politique de fixtures et sources

Les fixtures sont frozen/slotted, sans `Mapping`, payload ou callable. Chaque
source possède une ref `synthetic:*`, une version `v1` caller-supplied et un
texte français court.

Limites et interdictions :

- 512 caractères maximum par source ;
- une à quatre sources par fixture ;
- aucun contrôle caractère ;
- aucune URL live, adresse email ou chemin local ;
- aucun secret-like token ;
- aucune donnée d'élève, personne, entreprise réelle ou document utilisateur ;
- aucune affirmation d'extrait officiel.

Aucun hash runtime implicite n'est nécessaire : les refs et versions stables
suffisent à la reproductibilité.

## 8. Fixtures synthétiques

Le corpus contient des stimuli minimaux d'organisation de ressource, recherche,
cours, transformation TVA fictive, exercice, évaluation multisource, correction
versionnée et QCM à variantes. Les scopes terminés par `synthetic` sont des
codes locaux de test, pas une nomenclature STMG/BTS.

Trois marqueurs adversariaux sont bornés : instruction hostile dans Evidence,
smuggling d'autorité utilisateur et demande d'exfiltration factice. Aucun
marqueur n'est un secret réel.

## 9. Hard expectations

Le catalogue contient les attentes déclaratives suivantes :

- SCN-01 : WF-0, Application path, un route/call, ref préservée ;
- SCN-02 : WF-1, Evidence path, provenance, compte borné, non-autorité ;
- SCN-03 : WF-2, génération, sections requises, autorité interdite ;
- SCN-04 : WF-4, Evidence avant génération, lineage de transformation ;
- SCN-05 : WF-5/WF-10, génération-review, gate, review réalisée ;
- SCN-06 : WF-8/WF-6, fanout, join, validation-review, barème structuré ;
- SCN-07 : WF-1/WF-7/WF-0, Evidence, version, séquence, stop borné, Application ;
- SCN-08 : WF-9/WF-3/WF-11, variantes, sélection, review, gate/promotion,
  rendu au plus une fois.

Les observations `scn-NN.*` seront matérialisées par C à F. Les références
`scn-NN.expected.*` désignent les valeurs attendues déterministes.

## 10. Rubrics souples

Chaque scénario porte deux critères provider-neutral de poids exact `1/2` :
clarté, adaptation au niveau, fidélité, pertinence, difficulté, qualité de
correction ou qualité des distracteurs selon l'intent.

Le scorer-ref `pedagogical-quality-fixture-scorer` est seulement une coordonnée.
B n'en fournit aucune implémentation, aucun juge, seuil ou verdict.

```text
RUBRIC_DECLARATION != QUALITY_TRUTH
HARD_ASSERTION_FAILURE_CANNOT_BE_HIDDEN_BY_SCORE
```

## 11. Barème pédagogique et rubric

`marking-scheme` est un `PedagogicalSectionCode` de SCN-06. Une
`EvaluationRubric` appartient au harness offline. Les types, refs et cycles de
vie sont distincts et un test unitaire protège cette séparation.

```text
PEDAGOGICAL_MARKING_SCHEME != EVALUATION_RUBRIC
```

## 12. Tags transverses

Les seuls tags supplémentaires signalent les dimensions réellement applicables :
evidence injection, authority smuggling, exfiltration, gate humaine, recovery
de promotion effectful et équivalence observability. Ils réutilisent
`EvaluationTagCode` et ne forment pas un second système de policy.

## 13. Data safety et dépendances

Les fitness tests excluent provider/network, DB/YAML, fichiers golden bruts,
runner execution, imports inversés et dépendances runtime. Le projet conserve :

```text
[project].dependencies = []
```

## 14. Absence d'exécution complète en B

Les modules déclaratifs n'importent ni `EvaluationRunner`, ni target executor,
ni AG-02/03/04, ni `PlanExecutor`. L'import construit uniquement des contrats
immutables et des catalogues bornés. Aucun scénario C→G n'est exécuté.

## 15. Frontières suivantes

- 12.15-C résoudra SCN-01/02 et les chemins Search/RAG/resource exploitation ;
- 12.15-D résoudra SCN-03/04 et génération/transformation ;
- 12.15-E résoudra SCN-05/06/07/08 et review/correction/productions évaluatives ;
- 12.15-F ajoutera uniquement les variantes security/recovery/observability ;
- 12.15-G exécutera la suite cumulative et fermera R-WF/report ;
- 12.16 reste propriétaire des providers, modèles, budgets calibrés et seuils.

## 16. Release-gate traceability

| Gate | Contribution B |
| --- | --- |
| R-DET | ordre, IDs, refs et catalogues déterministes |
| R-SEC | marqueurs synthétiques et tags ciblés |
| R-AUTH | aucune authority dans les wrappers/fixtures |
| R-LIN | refs source/version et invariants déclarés |
| R-BUD | cardinalités et textes bornés, pas de calibration |
| R-RES | tag du parcours effectful, exécution différée |
| R-QUAL | rubrics rationnelles sans seuil |
| R-WF | union exacte WF-0 à WF-11 |
| R-OBS | scénarios applicables identifiés |
| R-DOC | corpus et policies versionnés offline |

## 17. Décision B

```text
PEDAGOGICAL_GOLDEN_CORPUS_BOUNDARY = ESTABLISHED
FULL_E2E_EXECUTION = DEFERRED_TO_C_THROUGH_G
NEXT_GATE = 12.15-C
```
