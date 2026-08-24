# Scheduler deterministe du runtime

## Responsabilite 12.5-C

`DeterministicScheduler` est une fonction de decision pure materialisee par une
dataclass frozen. Elle verifie la coherence entre `Plan` et `RunState`, derive
les transitions techniques `PENDING -> READY` ou `PENDING -> BLOCKED`, calcule
la capacite disponible et retourne des candidats ordonnes. Elle ne lance aucun
step et ne possede ni thread, queue, asyncio, provider ou framework.

`launch_candidate_ids` signifie uniquement « structurellement lancable sous
reserve des controles pre-launch ». Un candidat reste `READY`; C ne produit
jamais la transition `READY -> RUNNING`. En particulier, `READY` ne vaut jamais
autorisation. La revalidation du scope, des gates, de la policy et du budget
remaining appartient a la frontiere pre-launch de 12.5-D.

## Dependances et propagation

Le vocabulaire `DependencyDisposition` est ferme :

| StepRuntimeStatus | Disposition |
| --- | --- |
| `SUCCEEDED` | `SATISFIED` |
| `FAILED`, `CANCELLED`, `BLOCKED` | `BLOCKING` |
| `PENDING`, `READY`, `RUNNING` | `WAITING` |
| `PARTIAL`, `SKIPPED` | `UNRESOLVED` |

Un step PENDING sans dependance, ou dont toutes les dependances sont SATISFIED,
devient READY. Une dependance BLOCKING le fait devenir BLOCKED avec une raison
factuelle. Les autres combinaisons restent PENDING. La propagation BLOCKED est
calculee jusqu'au point fixe dans un meme appel, independamment de l'ordre
topologique du tuple `Plan.steps`. PARTIAL et SKIPPED ne sont ni des succes
implicites ni des blocages inventes.

READY, RUNNING et tous les statuts terminaux restent inchanges. `StepSpec` n'est
jamais mute.

## Selection et suspension

Apres verification de la hard limit, la capacite vaut
`max_parallel_steps - running_count`. Les steps READY non expires sont choisis
strictement dans l'ordre de `Plan.steps`, au plus dans la capacite disponible.
Le parallelisme DAG reel est exploitable meme sans `parallel_group`; celui-ci
reste le signal structurel fan-out/join valide en B.

`max_parallel_steps` est une hard limit. La saturation
`running_count == max_parallel_steps` est un etat valide avec zero slot. Un
overflow `running_count > max_parallel_steps` est une incoherence technique et
leve `SchedulerStateError` de facon fail-closed. Le scheduler ne masque pas le
depassement, ne repare aucun `StepState` et n'invente aucun `stop_reason`.

Les runs PLANNED et RUNNING peuvent produire des candidats. WAITING_GATE,
REPLANNING et les statuts globaux terminaux n'en produisent aucun. Le scheduler
ne change jamais le `WorkflowStatus` global.

## Signaux de deadline

Pour un step RUNNING, `effective_step_deadline` retourne la plus tot des limites
suivantes : deadline absolue du step, `started_at + max_runtime_seconds`, ou
`started_at + step_deadline_default_seconds`. `now >= deadline` ajoute l'id a
`timed_out_running_step_ids` sans transition FAILED/CANCELLED.

Un step READY dont la deadline absolue est atteinte, ou dont
`max_runtime_seconds == 0`, reste READY mais apparait dans
`expired_ready_step_ids` et n'est pas candidat. Une deadline absolue du plan
atteinte positionne `run_deadline_exceeded` et supprime tous les candidats.

La baseline 600 secondes n'est pas calculee en wall-clock lorsque
`gate_wait_pauses_run_deadline=True`, car `RunState` ne porte pas le temps actif
hors attente humaine. Ce decompte actif et `BudgetState` restent 12.11. Les
deadlines de C sont seulement des signaux. Depuis 12.5-D, `PlanExecutor` les
consomme avant tout lancement : READY expire devient FAILED, tandis qu'un
timeout susceptible d'avoir suivi un effet RUNNING exige une reconciliation.

## Joins et limites

Un JOIN utilise exactement la semantique generique de ses dependances. Il ne
fusionne aucun payload et n'appelle aucun handler. La convergence structurelle a
deja ete validee en B.

C n'instancie aucun `AgentInvocation`, `DelegationEnvelope`, use case, tool ou
gate. Il ne consulte ni `CapabilityAuthorizationPolicy`, ni
`PermissionScopeEvaluator`, ni `GateDecision`, ni un budget consomme. Execution,
transitions de lancement et consommation prudente des timeouts sont portees par
12.5-D sans modifier cette responsabilite. Routing tools et gates reelles
restent 12.10 ; accounting/recovery restent 12.11.
