# Phase 12.14-G — Baseline d'intégration runtime du harness

## 1. Parent F

Parent Git exact : `85bef9b696b157409520e71c9d2478c40d6b974d`.
Décision :
[ADR-P12-054](../../architecture/adr/ADR-P12-054-agentic-evaluation-runtime-integration-boundary.md).

## 2. Frontière adapter

Les adapters G sont exclusivement test-only sous
`tests/support/evaluation_runtime_adapters.py`. Aucun adapter n'est ajouté au
backend ou au core harness.

## 3. Graphe de dépendances

```text
tests/support -> evaluation_harness
tests/support -> backend owners
backend       -X-> evaluation_harness
harness       -X-> runtime/infrastructure
```

## 4. Corpus réutilisé

| Famille | Tests/helpers existants réutilisés |
| --- | --- |
| AG-01 | `test_workflow_selection_to_plan`, orchestration fakes |
| AG-02 | `test_ag02_search_rag_pipeline`, evidence retrieval fakes |
| AG-03 | `test_ag03_generation_pipeline`, generation fakes |
| AG-04 | `test_review_security_pipeline`, review fakes |
| routing/Gate | gate/use-case/runtime routing fakes |
| security | runtime global security pattern et runtime routing fakes |
| recovery | retry-after-reconciliation helpers et stores in-memory |
| observability | runtime observability integration helper et failing/null sinks |

Les pipelines existants sont appelés ; aucune logique owner n'est dupliquée.

## 5. Projection allowlist

Projeté : booléens, counts, status/reason/route/workflow codes fermés et relations
de lineage déjà établies. Exclus : prompts, document/Evidence text, generated ou
review text, payloads/outputs, metadata, exceptions, secrets, paths, provider
responses, reasoning et IDs non nécessaires.

## 6. AG-01

Le selector réel choisit WF-6. Le compiler réel produit quatre étapes ordonnées
AG-02, AG-03, Application et AG-04. Le case est répété deux fois.

## 7. AG-02

Le vrai `EvidenceAgent` exécute les quatre channels sur fakes déterministes,
matérialise trois items, obtient coverage COMPLETE et applique le scanner
sécurité sans rendre le texte Evidence autoritaire.

## 8. AG-03

Le vrai `GeneratorAgent` prépare et exécute un appel fake unique, applique le
guard réel et matérialise un candidate avec lineage CAP-G01. Aucun texte généré
n'est projeté.

## 9. AG-04

Le vrai `ReviewerAgent` matérialise une review structurée depuis le port fake.
Seuls status, assessment, correction bool et counts sont projetés.

## 10. Tool/Application/Gate

Le `GateEngine` APPROVED fournit les policy facts au routeur Application, qui
appelle l'inbound une fois. Un cycle `PlanExecutor` Tool autorisé exécute un seul
effet fake.

## 11. Sécurité

Une injection synthétique d'autorité dans les arguments Tool est refusée par le
guard réel avant effet : un SecurityEvent, zéro appel externe. Le marqueur
hostile n'entre pas dans les observations ou reports.

## 12. Recovery

Les records NONE, UNKNOWN, PARTIAL et COMMITTED passent par les policies
reconciliation/ReplayGuard réelles. Les dispositions sont respectivement
ELIGIBLE, RECONCILE_FIRST, BLOCKED et BLOCKED. G ne déclenche aucun replay.

## 13. Observability

Le même runtime/recovery controller instrumenté est exécuté avec sinks disabled
puis failing. Le résultat et le nombre d'effets restent identiques. Les metrics
ne deviennent jamais des scores.

## 14. Répétitions et fraîcheur

La suite produit exactement neuf exécutions, neuf inputs, neuf fixtures et neuf
cleanups. Les deux répétitions AG-01 ont des instances distinctes et les mêmes
facts/assertions/scores. Une répétition n'est ni retry ni replay.

## 15. Chemin complet

```text
EvaluationSuite -> EvaluationRunner -> adapter G -> owners réels
-> snapshots sûrs -> AssertionEvaluator -> ScoreEvaluator/RubricAggregator
-> SuiteEvaluationResult -> EvaluationReportProjector -> JSON/Markdown
```

## 16. Reporting et comparaison

JSON et Markdown F sont produits uniquement en mémoire. Une comparaison
contrôlée de deux configurations du selector AG-01 conserve PASS des deux côtés
et produit un delta technique exact `1/3`, sans winner ou décision de release.

## 17. Confidentialité

Les fitness tests inspectent les champs du projector G. Les tests vérifient
l'absence des contenus generation/review, du marqueur hostile, d'observation
refs et de données privées dans les modèles/renderers F.

## 18. Effets externes

Tous les outils, inbound ports, stores, probes et sinks sont fake ou in-memory.
Aucun réseau, provider, service externe ou DB externe.

## 19. Frontières 12.15/12.16

`tests/e2e/core` contient uniquement `.gitkeep`. Aucun scénario STMG/BTS,
provider, modèle, judge, coût, token ou calibration n'est introduit.

## 20. Readiness H1

G fournit la baseline intégrée pour les audits H1/H2/H3 : owners réels,
projections minimisées, effet unique, sécurité/recovery préservés et chemin B–F
complet. Aucun travail H n'est commencé dans ce lot.

```text
RATIONALIZATION = TEST_ONLY_ADAPTERS_REUSE_CANONICAL_RUNTIME_OWNERS
```
