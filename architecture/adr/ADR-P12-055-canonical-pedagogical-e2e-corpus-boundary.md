# ADR-P12-055 — Frontière du corpus pédagogique E2E canonique

## Statut

Accepté pour la Phase 12.15-B.

## Contexte

La Phase 12.14 a livré le harness offline d'évaluation, ses assertions, ses
rubrics, son runner et son reporting, ainsi que des adapters test-only vers les
owners runtime. Elle n'a créé aucun scénario pédagogique STMG ou BTS CG.

La Phase 12.15 doit matérialiser un corpus golden pédagogique sans dupliquer le
harness, sans créer une nouvelle autorité runtime et sans dépendre d'un provider,
d'une base ou d'une source live. Le lot B organise uniquement les déclarations ;
les exécutions end-to-end appartiennent aux lots C à G.

## Décision

1. Le corpus golden pédagogique appartient exclusivement à la Phase 12.15.
2. Le package `evaluation_harness` de 12.14 est réutilisé sans modification et
   reste l'unique harness d'évaluation.
3. Le corpus réside exclusivement sous `tests/e2e/core` et n'est jamais importé
   par `backend` ou `evaluation_harness`.
4. `PedagogicalLevelCode` constitue une métadonnée de test. Il ne représente ni
   un enum métier runtime, ni une nomenclature officielle de programme.
5. `PedagogicalIntentCode` classe les scénarios et rapports de test. Il n'est ni
   une capability, ni un use case, ni une permission.
6. Le corpus contient exactement huit scénarios, choisis par set-cover pour
   éviter le produit cartésien niveau × workflow × discipline.
7. L'union ordonnée des parcours couvre exactement `WorkflowKind.WF_0` à
   `WorkflowKind.WF_11`. L'enum et le catalogue runtime sont réutilisés ; aucun
   clone de workflow n'est créé.
8. Les déclarations et fixtures utilisent des types Python frozen/slotted et la
   stdlib. Aucun YAML, fichier golden texte ou stockage DB n'est introduit.
9. Les fixtures sont courtes, synthétiques, offline, sans personne réelle,
   secret, URL live, chemin local ou prétention d'extrait officiel.
10. Les invariants bloquants sont des assertions 12.14 ; les qualités graduées
    sont des rubrics rationnelles 12.14.
11. Une déclaration de rubric ne constitue pas une vérité de qualité, un juge,
    un verdict ou un seuil d'acceptation.
12. Aucun provider, modèle, juge, pricing ou calibration n'appartient à 12.15-B.
13. Les goldens portent des codes de structure et des refs opaques. Les snapshots
    de texte de sortie complets sont exclus par défaut.
14. B ne câble aucun scorer sémantique, target executor, runner ou owner runtime
    et n'exécute aucun scénario complet.
15. C possède Search/RAG, D génération/transformation, E review/correction et
    productions évaluatives, F les dimensions security/recovery/observability,
    et G la fermeture cumulative WF/report.

## Catalogue minimal

| Scénario | Niveau test-only | Intent test-only | Parcours WF |
| --- | --- | --- | --- |
| SCN-01 | PREMIERE_STMG | RESOURCE_ORGANIZATION | WF-0 |
| SCN-02 | TERMINALE_STMG | RESOURCE_SEARCH | WF-1 |
| SCN-03 | PREMIERE_STMG | COURSE_CREATION | WF-2 |
| SCN-04 | BTS_CG_1 | RESOURCE_TRANSFORMATION | WF-4 |
| SCN-05 | TERMINALE_STMG | EXERCISE_CREATION | WF-5, WF-10 |
| SCN-06 | BTS_CG_1 | ASSESSMENT_CREATION | WF-8, WF-6 |
| SCN-07 | BTS_CG_2 | CORRECTION_REMEDIATION | WF-1, WF-7, WF-0 |
| SCN-08 | BTS_CG_2 | QCM_QUIZ_CREATION | WF-9, WF-3, WF-11 |

L'ordre de chaque tuple WF représente le parcours et non un ensemble de tags.
WF-10 reste un overlay et WF-11 conserve sa gate policy propre.

## Fixtures et sources

`SyntheticPedagogicalFixture` compose :

- une `EvaluationFixtureRef` 12.14 ;
- un niveau test-only ;
- un scope code explicitement synthétique ;
- une à quatre sources courtes à refs opaques et version caller-supplied ;
- au plus une ref de marqueur adversarial résolue dans la fixture.

Chaque texte source est limité à 512 caractères. Cette limite permet les stimuli
nécessaires tout en empêchant l'installation silencieuse de documents, manuels
ou snapshots de sortie dans le corpus.

## Assertions et rubrics

Les observations futures suivent le namespace `scn-NN.*`. Les références
`scn-NN.expected.*` désignent les valeurs attendues qui seront fournies par les
adapters C à F. Les hard expectations utilisent uniquement les kinds fermés de
12.14.

Chaque scénario porte une `EvaluationRubric` de deux critères de poids exact
`1/2`. Le scorer-ref générique est une coordonnée déclarative non résolue en B ;
aucune implémentation sémantique ou acceptation n'en découle.

```text
PEDAGOGICAL_MARKING_SCHEME != EVALUATION_RUBRIC
RUBRIC_DECLARATION != QUALITY_TRUTH
```

Le marking scheme est une section de production pédagogique. La rubric mesure
ultérieurement une qualité offline ; elle ne devient jamais le barème de l'élève.

## Conséquences

- le corpus est diffable, déterministe, typé et reproductible offline ;
- le runtime ne reçoit aucun niveau, intent ou concept métier nouveau ;
- les owners AG-01 à AG-04, Gate, Application et Tool conservent leur autorité ;
- 12.16 reste propriétaire des providers et de la calibration ;
- les exécutions C à G devront résoudre les refs déclarées sans élargir cette
  frontière ni reporter de contenu brut.
