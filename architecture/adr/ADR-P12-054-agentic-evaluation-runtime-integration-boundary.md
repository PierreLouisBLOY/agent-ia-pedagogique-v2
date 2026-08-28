# ADR-P12-054 — Frontière d'intégration runtime du harness

## Statut

Accepté pour la Phase 12.14-G.

## Contexte

Les lots B–F fournissent contrats, assertions, scoring, runner et reporting
offline. G doit prouver leur intégration avec les vrais owners agent/runtime
sans inverser les dépendances ni créer des adapters de production.

```text
TEST_ADAPTERS_MAY_DEPEND_ON_BOTH_SIDES
PRODUCTION_RUNTIME_MUST_NOT_DEPEND_ON_EVALUATION_HARNESS
```

## Audit des seams réutilisés

| Intégration existante | Owner canonique | Seam appelé | Facts sûrs projetés | Adapter/helper réutilisé |
| --- | --- | --- | --- | --- |
| workflow selection/plan | `WorkflowSelector`, `PlanCompiler` | `select`, `compile` | workflow code, ordre/count, relation executor | helpers `test_workflow_selection_to_plan` |
| AG-02 Search/RAG | `EvidenceAgent`, `RetrievalCoordinator` | search/materialize/build/security assess | mode, coverage, channels/counts, instruction non-authoritative | `evidence_retrieval_fakes` + helpers pipeline AG-02 |
| AG-03 generation | `GeneratorAgent`, `GenerationCoordinator`, guard | prepare/generate/guard/materialize | status, guard disposition, candidate flag, lineage bool, call count | `RecordingGenerationPort` + helpers pipeline AG-03 |
| AG-04 review | `ReviewerAgent`, `ReviewCoordinator` | review/materialize | review status/assessment, correction bool, findings/count | review security helpers/fake port |
| Gate/Application | `GateEngine`, use-case router | evaluate puis route | disposition, inbound count, route relation | `gate_fakes`, `use_case_routing_fakes` |
| Tool runtime | `PlanExecutor`, security prelaunch, tool router | execute cycle | completion/effect count | `runtime_routing_fakes` |
| Security runtime | security guard via `PlanExecutor` | forged technical request | directive codes, event/effect counts | hostile fixture pattern 12.12 |
| Recovery | `EffectReconciliationPolicy`, `ReplayGuard` | reconcile/evaluate | dispositions NONE/UNKNOWN/PARTIAL/COMMITTED | reconciliation/retry fakes |
| Observability | instrumented `RecoveryRuntimeController` | disabled/failing executions | equivalence bool, effect counts, mode codes | observability/recovery in-memory fakes |

Les pipelines et policies restent chez leurs owners. G réutilise leurs seams et
helpers statiques ; il ne recopie aucun algorithme de sélection, retrieval,
generation, review, routing, security, recovery ou observability.

## Décision

### Emplacement et graphe

Tous les adapters sont dans
`tests/support/evaluation_runtime_adapters.py`; les preuves sont dans
`tests/integration` et `tests/architecture`.

```text
tests/support adapter -> evaluation_harness
tests/support adapter -> backend canonical owners
backend               -X-> evaluation_harness
evaluation_harness    -X-> backend.agent_runtime/infrastructure
```

Aucun fichier production n'est modifié. L'unique import backend du core harness
reste `backend.shared_kernel._value_safety`.

### Ownership des adapters

`TechnicalRuntimeTargetExecutor` implémente la boundary E et possède un dispatch
fermé explicite vers neuf familles techniques. Ce n'est ni un registry global,
ni un dispatcher de callables/import paths. Chaque branche appelle un owner ou
seam réel identifié dans la matrice.

`TechnicalRuntimeInputFactory` construit un input opaque neuf contenant
uniquement un profile code et l'index. `TechnicalRuntimeFixtureFactory` crée un
handle mutable neuf par répétition puis vérifie son cleanup. Les stores et ports
réels utilisés par chaque branche sont reconstruits par les fakes existants.

```text
EACH_REPETITION_STARTS_FROM_FRESH_TEST_STATE
G_EXTERNAL_EFFECTS = FAKE_OR_IN_MEMORY
```

### Projection sûre

`ClosedFactSnapshotProjector` reçoit `ClosedTechnicalFacts` : un booléen
principal, une séquence de checks techniques, des codes fermés et des counts.
Il produit quatre observations canoniques bornées.

```text
PROJECT_CLOSED_FACTS_NOT_RAW_CONTENT
```

Allowlist : enum/status/reason codes, booléens, counts, ordre de codes fermé et
relations de lineage déjà calculées. Sont exclus : prompt, Evidence text,
generated/review text, payload/output Tool/Application, metadata SecurityEvent,
exception, secret, path, provider response et reasoning.

Les IDs runtime ne sont pas projetés. Une relation booléenne est préférée pour
lineage et effet unique.

### Invariant et scorer

`TechnicalOwnerInvariantEvaluator` vérifie seulement qu'un fact booléen déjà
produit par l'owner est vrai. Il ne recompile aucune policy.

```text
INVARIANT_ADAPTER_CHECKS_OWNER_FACTS
INVARIANT_ADAPTER_DOES_NOT_REIMPLEMENT_OWNER_POLICY
```

`TechnicalFactScorer` calcule le ratio rationnel exact des checks booléens déjà
projetés. Ce score est structurel et technique. Il n'alias ni confidence review,
ni retrieval score, metric, qualité pédagogique ou modèle.

### Cas techniques

- AG-01 : WF-6 sélectionné puis plan exact AG-02/AG-03/Application/AG-04 ;
- AG-02 : retrieval FULL, couverture COMPLETE, trois items, sécurité passive ;
- AG-03 : appel unique, guard ALLOW, candidate et lineage CAP-G01 ;
- AG-04 : review matérialisée, status/assessment fermés, un finding ;
- autorité : Gate APPROVED, route Application unique et Tool effect unique ;
- sécurité : authority smuggling synthétique refusé, un event, zéro effet ;
- recovery : NONE éligible, UNKNOWN reconcile-first, PARTIAL/COMMITTED bloqués ;
- observability : résultat runtime identique disabled/failing ;
- comparaison : selector AG-01 sous deux configurations contrôlées, delta 1/3.

Aucun cas ne constitue un cours, exercice, QCM ou évaluation scolaire canonique.

### Chemin complet et répétitions

La suite traverse B→E, les adapters G et owners réels, puis C/D et F jusqu'aux
bytes JSON/Markdown. AG-01 utilise deux répétitions : deux inputs, fixtures,
owner calls et cleanups distincts, mêmes facts déterministes. Aucun replay ou
retry runtime n'est utilisé pour piloter les répétitions.

La comparaison F reste descriptive : reports baseline/candidate, transition et
delta exact, sans winner, acceptance ou release gate.

### Effets, sécurité et confidentialité

Tous les ports externes sont fake/in-memory. Aucun réseau, provider, service ou
DB externe n'est appelé. Gate, security guard, reconciliation et ReplayGuard
conservent seuls leur autorité.

Les valeurs techniques internes utilisées par generation/review et le marqueur
hostile `gateDecision` ne sont jamais projetés ni reportés.

## Frontières

- 12.15 reste le propriétaire des scénarios pédagogiques canoniques ;
- 12.16 reste le propriétaire providers/modèles/coûts/calibration ;
- H1/H2/H3 peuvent auditer respectivement architecture, sécurité/fitness et
  clôture 12.14 sur cette baseline intégrée.

`tests/e2e/core` reste limité à `.gitkeep`.

## Conséquences

L'intégration complète est prouvée sans nouvelle seam production et sans
dépendance inverse.

```text
RATIONALIZATION = TEST_ONLY_ADAPTERS_REUSE_CANONICAL_RUNTIME_OWNERS
```
