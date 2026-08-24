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
Il ne signifie jamais « autorise » : policy, scope et conditions trusted seront
revalides immediatement avant lancement dans les lots suivants.

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

## Limites de 12.5-B

Scheduler, selection et lancement des steps, transitions, executor, retries et
replanification arrivent en 12.5-C/D. Le moteur de gates et les policies de tool
calls restent 12.10. `BudgetState`, consommation, snapshots persistants,
reconciliation et recovery complet restent 12.11.
