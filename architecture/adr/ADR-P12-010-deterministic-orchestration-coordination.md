# ADR P12-010 - Coordination déterministe de l'orchestration

## Statut

Accepté.

## Contexte

Le runtime 12.5 produit un `ExecutionCycleResult` borné et sans boucle. Il ne
déclare volontairement aucune réussite globale à partir des seuls états
techniques des steps. En parallèle, `PlanRevisionEngine` est déjà l'unique
mécanisme d'adoption d'un replacement fourni de l'extérieur. Il manque la
frontière AG-01 qui transforme ces observations en une décision explicite R9 :
continue, retry, replan, escalate ou finish, sans acquérir de capacité
d'exécution supplémentaire.

`Plan.success_criteria` reste un mapping déclaratif. Aucun évaluateur canonique
de ces critères, aucun parser générique et aucun juge LLM ne sont définis à ce
stade.

## Décision

`backend/agent_runtime/orchestration/coordination/` contient une couche pure et
immutable au-dessus d'un cycle déjà terminé. `OrchestrationCoordinator` reçoit
seulement un `Plan`, un `ExecutionCycleResult` et un `Instant`. Il vérifie
l'identité complète Plan/RunState, y compris l'ordre des steps, conserve toutes
les observations sûres et refuse les directives décisives incohérentes.

Un snapshot terminal a priorité absolue et reste inchangé : `SUCCEEDED` et
`PARTIAL` donnent `COMPLETE`, `FAILED` et `CANCELLED` donnent `STOP`, et
`ESCALATED` donne `ESCALATE`. Aucun evaluator de completion n'est alors appelé.

Pour un run non terminal, l'ordre fail-closed est : reconciliation, attente de
gate, replan, retry, revue partial, attente de condition. Les signaux de
pré-launch et de deadline restent observationnels lorsqu'une décision plus
forte existe. Une reconciliation domine afin qu'un effet inconnu ne soit jamais
rejoué. Les combinaisons décisives incompatibles sont rejetées ; aucune voie
irréversible n'est choisie arbitrairement.

Sans signal bloquant, un travail `RUNNING`, `READY` ou `PENDING` produit
`CONTINUE` sans exécution. La completion globale n'est évaluée qu'à quiescence,
quand ces trois ensembles sont vides. La frontière est un
`WorkflowCompletionEvaluator` runtime-checkable, sans implémentation concrète en
production. Son résultat typé peut terminer le run en succès, partial, échec ou
escalade, ou le placer en replanning. Son reason code stable est conservé.

`RETRY_REQUIRED` n'effectue aucun retry, ne modifie aucun `StepState`, n'incrémente
aucun attempt et n'applique aucun backoff. `WAIT_GATE` ne construit ni ne consomme
de `GateDecision`. `REPLAN_REQUIRED` ne construit aucun replacement.

`apply_replan` délègue exactement une fois à `PlanRevisionEngine.revise` et
retourne son résultat sans transformation. Le moteur conserve seul les règles de
version `current+1`, la limite de six versions, l'absence de goal drift, la
validation statique, la réutilisation des steps réussis, le no-progress et la
détection de cycle. Un `PlanHistory` garde nécessairement un seul
`workflow_kind`; aucun reselect automatique n'est permis dans le même run.

## Conséquences

- la coordination explique une prochaine action, mais ne lance aucun effet ;
- la réussite globale exige toujours une décision explicite d'un evaluator
  injecté ;
- les reason codes remplacent toute rationale libre ou payload brut ;
- les tests de scénarios 12.6-F pourront injecter des fakes sans ajouter de
  runtime concret ;
- les agents réels restent différés à 12.7-12.9 ;
- le routing et la consommation des gates restent différés à 12.10 ;
- la mécanique réelle de retry et recovery reste différée à 12.11.
