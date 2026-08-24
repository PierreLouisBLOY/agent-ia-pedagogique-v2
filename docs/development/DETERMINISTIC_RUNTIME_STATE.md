# Etat technique du runtime deterministe

## Frontiere

`backend/agent_runtime/runtime/` porte uniquement l'orchestration technique
deterministe. Son etat n'est ni un aggregate metier, ni un read model
Application. Il ne lit aucun repository, SQL, secret ou filesystem metier et
n'introduit aucun provider ou framework.

`StepSpec` reste la declaration immutable d'une unite de travail : kind,
executor, capability, inputs, `depends_on`, budget et criteres. `StepState` est
son etat technique d'execution, separe et lui aussi immutable. Aucun statut
runtime n'est ajoute a `StepSpec`.

## StepState

Le vocabulaire ferme 12.5-B est : `pending`, `ready`, `running`, `succeeded`,
`partial`, `failed`, `cancelled`, `blocked`, `skipped`. Il reste distinct des
statuts Workflow, Invocation, AgentResult, Application et Domain.

Les champs sont `step_id`, `status`, `parent_step_id`, `context_slice_ref`,
`started_at`, `ended_at`, `attempt_count`, `result_refs`, `metrics`, `error_ref`
et `block_reason`. Les references et timestamps sont valides a la construction ;
les metrics sont profondement immutables.

`READY` signifie seulement qu'une transition technique pourra etre envisagee.
Il ne signifie jamais « autorise » : depuis 12.5-D, le `PreLaunchGuard` est
obligatoirement consulte immediatement avant lancement.

## RunState

`RunState` reutilise le `WorkflowStatus` existant ; aucun `RunStatus` concurrent
n'est cree. Il contient `run_id`, `correlation_id`, `workflow_kind`, `plan_id`,
`plan_version`, `status`, `step_states`, les references d'artifacts/erreurs et de
snapshot de contexte, les timestamps et une eventuelle `stop_reason`.

Les proprietes read-only `current_step_ids`, `completed_step_ids`,
`pending_step_ids`, `ready_step_ids` et `blocked_step_ids` sont derivees sans
stockage duplique. Le pluriel `current_step_ids` permet plusieurs steps RUNNING.
L'ordre suit l'ordre des cles fourni lors de la construction de `step_states`.

`initialize_run_state` effectue la validation statique, initialise tous les
steps en `PENDING` et le run en `PLANNED`. Elle ne calcule pas `READY`, ne lance
rien, ne resout aucun scope et ne consomme aucun budget.

## Extension scheduler 12.5-C

Le scheduler pur peut maintenant deriver `PENDING -> READY/BLOCKED`, propager un
blocage et retourner des `launch_candidate_ids` bornes. Il ne change ni le
`WorkflowStatus` global, ni READY en RUNNING. PARTIAL/SKIPPED restent non resolus
pour une dependance. Les candidats suivent l'ordre du plan et restent soumis aux
controles pre-launch de D. Les deadlines ne sont que des signaux ; elles ne
produisent aucune annulation ou transition terminale.

## Extension executor 12.5-D

L'executor porte `READY -> RUNNING`, incremente `attempt_count`, applique les
quatre resultats terminaux du runner et consomme les signaux de deadline. Une
attente de gate peut preceder le premier lancement : WAITING_GATE autorise donc
`started_at=None`. De meme, REPLANNING conserve la valeur de `started_at`, y
compris `None` lorsqu'une failure policy s'applique avant toute execution.

Une failure policy produit seulement une directive. Aucun retry, backoff,
replay, nouveau Plan ou succes global implicite n'est execute.

## Limites apres 12.5-D

Le versioning de replan reste 12.5-E. Le moteur concret de gates, le routing et
les policies de tool calls restent 12.10. `BudgetState`, temps actif hors gate,
consommation, snapshots persistants, reconciliation et recovery complet restent
12.11.
