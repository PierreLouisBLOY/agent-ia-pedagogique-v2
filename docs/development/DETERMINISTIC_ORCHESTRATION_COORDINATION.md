# Coordination déterministe de l'orchestration

## Frontière AG-01 et règle R9

La règle R9 demande d'évaluer le résultat et les stop conditions pour produire
une voie explicite : continue, retry, replan, escalate ou finish. La couche
`orchestration/coordination` matérialise cette supervision au-dessus du runtime
12.5. Elle consomme un `ExecutionCycleResult` déjà produit et retourne une
`CoordinationDecision` immutable. Elle ne lance aucun cycle, step, outil, use
case ou agent.

Le runtime reste propriétaire des transitions techniques d'un cycle et des
`ExecutionDirective`. AG-01 est propriétaire du choix déterministe de la
prochaine action de coordination. Les observations du runtime sont conservées
sous forme de codes de directive, de step ids affectés et de reason codes
stables, sans payload brut d'erreur ou de runner.

## Priorité fail-closed

Pour un run non terminal, la priorité est strictement :

1. `RECONCILIATION_REQUIRED` ;
2. `WAITING_GATE` ;
3. `REPLAN_REQUIRED` ;
4. `RETRY_REQUIRED` ;
5. `PARTIAL_REQUIRES_DECISION` ;
6. `CONDITION_REQUIRED` ;
7. continuation ou évaluation de completion.

Une reconciliation domine parce qu'un effet inconnu interdit tout replay. Les
combinaisons décisives contradictoires sont refusées avec
`CONFLICTING_DECISIVE_DIRECTIVES`. Une attente de gate ou un replan doit aussi
être cohérent avec le statut du run. Les signaux `PRELAUNCH_DENIED`,
`READY_DEADLINE_EXPIRED` et `RUN_DEADLINE_EXCEEDED` restent observationnels : ils
ne deviennent jamais, à eux seuls, une autorisation de retry.

## Snapshots terminaux

Un run déjà terminal est prioritaire et son snapshot est retourné sans
modification ni nouvel appel à l'evaluator :

| `WorkflowStatus` | Action |
| --- | --- |
| `SUCCEEDED`, `PARTIAL` | `COMPLETE` |
| `FAILED`, `CANCELLED` | `STOP` |
| `ESCALATED` | `ESCALATE` |

Une directive retry, replan ou wait gate incompatible avec un terminal est
refusée. Une observation informative compatible, comme une deadline avec un run
déjà `FAILED`, reste visible dans la décision.

## Signification des actions bloquantes

`RETRY_REQUIRED` est une demande de coordination, pas une exécution. Aucun état
de step n'est remis à `PENDING`, aucun attempt n'est incrémenté et aucun backoff,
sleep, fallback ou nouvel appel n'est effectué. La mécanique de retry appartient
à 12.11.

`WAIT_GATE` est une attente, pas une `GateDecision`. Le coordinateur n'approuve
aucune gate, ne reprend pas le run et n'appelle pas le runtime. La consommation
des décisions de gate appartient à 12.10.

`REPLAN_REQUIRED` place seulement le run à `REPLANNING` lorsqu'il provient de la
completion. Le coordinateur ne sélectionne, ne compile et ne construit aucun
replacement.

`RECONCILIATION_REQUIRED` ne modifie aucun snapshot. Tant que l'effet est
inconnu, aucune autre action susceptible de le rejouer n'est autorisée.

`REVIEW_PARTIAL` impose une décision explicite sur les résultats partiels. Il ne
produit ni succès global ni promotion implicite. `WAIT_CONDITION` conserve de la
même façon l'attente sans lancer d'effet.

## Quiescence et completion globale

L'evaluation de completion est autorisée uniquement si le run n'est pas
terminal, si aucune directive prioritaire n'existe et si les ensembles
`current_step_ids`, `ready_step_ids` et `pending_step_ids` sont tous vides. Si du
travail `RUNNING`, `READY` ou `PENDING` demeure, l'action est `CONTINUE` et le
caller pourra demander ultérieurement un autre cycle au runtime.

`WorkflowCompletionEvaluator` est un `Protocol` runtime-checkable injecté. Il
n'existe aucune implémentation concrète dans cette phase :

- aucun parser générique de `Plan.success_criteria` ;
- aucun LLM-as-judge ;
- aucun succès déduit des seuls steps terminaux.

L'evaluator est appelé exactement une fois à quiescence. Il retourne une
`WorkflowCompletionDecision` typée :

| Disposition | Nouveau statut | Action |
| --- | --- | --- |
| `SUCCEEDED` | `SUCCEEDED` | `COMPLETE` |
| `PARTIAL` | `PARTIAL` | `COMPLETE` |
| `REPLAN_REQUIRED` | `REPLANNING` | `REPLAN_REQUIRED` |
| `STOP_REQUIRED` | `FAILED` | `STOP` |
| `ESCALATE_REQUIRED` | `ESCALATED` | `ESCALATE` |

Les transitions utilisent un nouveau `RunState` immutable. `started_at` et les
états de steps sont conservés. Les terminaux prennent `ended_at=now`; les issues
stop/escalate utilisent le reason code factuel comme `stop_reason`.

## Adoption d'un replacement fourni

`apply_replan(history, run_state, replacement)` appelle exactement une fois
`PlanRevisionEngine.revise` et retourne le `PlanRevisionResult` tel quel. Ce
moteur reste seul propriétaire de :

- `current+1` et la limite de six versions ;
- la stabilité du run, du plan, de l'objectif, des success criteria et des stop
  conditions ;
- la validation statique ;
- la réutilisation des steps `SUCCEEDED` et le reset des autres états ;
- le no-progress et les cycles structurels.

Un `PlanHistory` impose le même `workflow_kind` sur toutes ses versions. AG-01 ne
contourne pas cette règle par un reselect ou une recompilation automatique dans
le même run.

## Phases différées

12.6-F couvrira les scénarios d'orchestration avec des fakes. Les agents réels
arrivent en 12.7-12.9. Le routing et les gates appartiennent à 12.10. Le retry et
le recovery réels appartiennent à 12.11.
