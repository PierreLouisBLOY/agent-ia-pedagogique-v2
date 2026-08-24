# Baseline canonique du runtime deterministe Phase 12.5

## Statut

La Phase 12.5 B a F est techniquement cloturee sur la branche
`phase12/12-5-deterministic-runtime`. La baseline couvre planification
declarative, etat technique immutable, scheduling pur, execution par frontieres
injectees et revision versionnee. Elle ne constitue pas une autorisation de
merge ; un audit independant du SHA final F reste requis.

Le runtime est provider-neutral, sans dependance runtime tierce et sans autorite
metier. Il ne lit ni repository, SQL, secret ou filesystem metier.

## Architecture

`backend/agent_runtime/runtime/` comporte quatre sous-zones :

- `planning/` : `Plan`, validation statique, `PlanHistory` et revision ;
- `state/` : `StepState`, `RunState` et invariants de statut ;
- `scheduling/` : derivation READY/BLOCKED, selection et deadlines ;
- `execution/` : guard pre-launch, runner abstrait, directives et executor.

Les objets principaux sont frozen/slots et provider-neutral : `Plan`,
`StepSpec`, `StepState`, `RunState`, `SchedulingDecision`,
`PreLaunchDecision`, `StepExecutionResult`, `ExecutionDirective`,
`ExecutionCycleResult`, `PlanHistory` et `PlanRevisionResult`.

Le cycle operationnel est :

`Plan -> validate -> initialize -> schedule -> prelaunch -> run -> terminal/directive -> replan`

Validation, generation, execution, evaluation du succes et revision restent des
responsabilites distinctes.

## Etats techniques

`StepRuntimeStatus` est ferme : `pending`, `ready`, `running`, `succeeded`,
`partial`, `failed`, `cancelled`, `blocked`, `skipped`. Le statut appartient au
`StepState`, jamais au `StepSpec`.

`RunState` reutilise exclusivement `WorkflowStatus`. Aucun `RunStatus`
concurrent n'existe. La verite courante des steps vient uniquement de
`RunState.step_states`; `current_step_ids` est une propriete derivee plurielle,
et aucun `current_step_id` singulier n'est stocke.

READY signifie structurellement schedulable, jamais autorise. Seul un
`PreLaunchGuard` satisfait peut permettre READY vers RUNNING.

## Plan et validation statique

`Plan` est immutable. Le DAG vient exclusivement de `StepSpec.depends_on` ; il
n'existe aucun second champ de dependances. `PlanValidator` controle notamment :

- cardinalite, references et cycles du DAG ;
- coherence kind/executor/capability et routes ;
- presence d'un `permission_scope_ref` sur les steps executables ;
- dependances incompatibles d'un fan-out et convergence par JOIN explicite ;
- ancetre GATE structurel pour une capability `REQUEST_GATE` ;
- narrowing des budgets de steps dans l'enveloppe du plan.

Ces controles prouvent une forme structurelle, pas une decision de scope, gate,
budget remaining ou autorisation d'effet.

## Scheduler deterministe

`DeterministicScheduler` s'appuie sur un Plan deja valide et sur les etats
existants sans lancer de step. Il derive PENDING vers READY lorsque toutes les
dependances sont SUCCEEDED, ou vers BLOCKED lorsqu'une dependance est FAILED,
CANCELLED ou BLOCKED. La propagation BLOCKED atteint un point fixe dans le meme
appel.

PARTIAL et SKIPPED restent non resolus. L'ordre de selection est toujours celui
de `Plan.steps`. `max_parallel_steps` vient de `AgentRuntimePolicy`; cinq steps
RUNNING avec la baseline quatre constituent une incoherence et produisent
`SchedulerStateError`.

Les deadlines sont seulement signalees par le scheduler. Un READY expire, un
RUNNING timeout ou une deadline globale ne sont jamais interpretes comme preuve
d'absence d'effet.

## Executor deterministe

`PlanExecutor` appelle le scheduler une fois par cycle, puis le
`PreLaunchGuard` avant toute transition RUNNING. `StepRunner` est un Protocol
injecte sans implementation concrete en 12.5. Un lancement increment
`attempt_count` exactement une fois et le runner voit deja le step RUNNING.

Les resultats normaux autorises sont SUCCEEDED, PARTIAL, FAILED et CANCELLED.
Les `FailurePolicy` produisent des directives seulement : RETRY_REQUIRED,
REPLAN_REQUIRED, ESCALATED ou STOPPED. Aucun retry, backoff ou second appel
runner automatique n'est realise.

### Doctrine d'effet inconnu

Un timeout RUNNING, une exception runner ou une `ErrorEnvelope` avec
`EffectState.UNKNOWN` exige RECONCILIATION_REQUIRED. Le step reste RUNNING si
l'effet externe ne peut pas etre determine.

Toute violation de contrat detectee apres invocation du runner suit la meme
doctrine : mauvais type de resultat, `error.step_id` different ou
`error.attempt` different de l'attempt courant. Le resultat n'est pas applique,
la failure policy n'est pas consultee et aucun payload brut n'est expose.

Un run terminal entrant est un no-op strict. Le scheduler valide encore la
coherence, mais le snapshot original est retourne sans refresh PENDING vers
READY.

## Revision versionnee

`PlanRevisionEngine` recoit un replacement externe ; il ne genere aucun Plan.
`PlanHistory` conserve une suite immutable et contigue depuis la version 1. Une
revision exige current+1 et `AgentRuntimePolicy.max_plan_versions`; la baseline
admet les versions 1 a 6 et refuse la version 7.

Le replacement preserve exactement run, plan, workflow, objectif, criteres de
succes et conditions d'arret. Il repasse par le `PlanValidator` canonique.

L'identite d'execution d'un step comprend kind, capability, executor, objectif,
inputs, dependances, criteres de succes, contrat de sortie et groupe parallele.
Un meme `step_id` ne peut changer cette identite. Scope, budget et failure policy
sont des controles exclus de l'identite retrospective.

Seul un ancien StepState SUCCEEDED compatible est reutilise completement. Tout
autre lineage compatible est reset PENDING en conservant `attempt_count`; un
nouveau step commence PENDING a zero et un step retire quitte le snapshot
courant. L'engine ne calcule jamais READY : le scheduler suivant reste requis.

La signature structurelle detecte `NO_STRUCTURAL_PROGRESS` lorsque seuls
version, budget, scope ou policy changent. Le retour a une structure anterieure
produit `STRUCTURAL_CYCLE_DETECTED`.

## Hard limits de baseline

Les limites techniques proviennent uniquement de `AgentRuntimePolicy` :

- 24 steps par run ;
- 6 versions de Plan ;
- 4 steps paralleles ;
- profondeur de delegation 2 ;
- 8 tool calls par step ;
- declarations maximales de 2 retries et 2 review cycles ;
- 3 evidence rounds ;
- seuils contexte 0,70 et 0,80 ;
- deadlines par defaut run/step de 600/120 secondes.

Les limites retry, tool calls et budgets restent declaratives tant que les
composants d'accounting 12.11 n'existent pas.

## Decisions de rationalisation F

Le meme ensemble terminal de `WorkflowStatus` etait duplique dans `RunState` et
`PlanExecutor`. Il est consolide dans le module interne cible
`state/_workflow_statuses.py` afin que validation temporelle, no-op terminal et
refresh partagent une source unique.

Les ensembles suivants ne sont pas fusionnes : statuts terminaux de StepState,
resultats normaux du runner, statuts launchable du scheduler et directives qui
arretent un cycle. Ils expriment des responsabilites differentes et n'ont pas la
meme extension future.

Les coherences Plan/RunState du scheduler et de la revision restent separees.
Le scheduler exige les memes ids sans dependre de l'ordre du mapping ; la
revision exige l'ordre strict du Plan pour reconstruire lineage et audit. Une
abstraction commune masquerait cette difference. `_step_execution_identity`
reste locale a revision car elle n'a pas de second usage reel.

Les petits helpers de refus et invariants `allowed/code` des policies 12.4
restent locaux a leurs enums fermes (`ScopeEvaluation`, delegation et
capability policy). Leur forme se ressemble, mais leurs contrats et payloads
different ; les generaliser creerait precisement le `PolicyFramework` interdit.

L'audit n'a trouve ni import circulaire actif, dead code runtime, vocabulaire
concurrent ou logique metier migree dans le runtime. Aucun meta-framework,
registry generique, event bus, plugin system ou framework DI n'est ajoute.

## Findings historiques

| Finding | Preuve de fermeture | Statut |
| --- | --- | --- |
| P12.5B-F01 MISSING_PERMISSION_SCOPE | `PlanValidator` et test executable sans scope | CLOSED |
| P12.5B-F02 MISSING_JOIN_STRATEGY | validation fan-out sans JOIN | CLOSED |
| P12.5B-F03 REQUIRED_GATE_MISSING | validation REQUEST_GATE sans ancetre GATE | CLOSED |
| P12.5C-F01 parallel overflow | hard limit scheduler 5 RUNNING > 4 | CLOSED |
| P12.5D-F01 contrat runner post-invocation | mauvais resultat conserve RUNNING et reconcilie | CLOSED |
| P12.5D-F02 binding attempt | mismatch `error.attempt` reconcilie | CLOSED |
| Correctif terminal 1b34ecb | run terminal avec step PENDING strictement inchange | CLOSED |

Chaque ligne est couverte par les suites unitaires historiques et par la fitness
cumulative `test_phase_12_5_runtime_closure.py`.

## Frontieres apres 12.5

- 12.6 : planner AG-01 concret et catalogue WF-* ;
- 12.10 : routing agents/tools/use cases, policies pre-launch concretes et gates ;
- 12.11 : recovery, accounting, retries et snapshots persistants.

Aucun provider, framework, client HTTP, ORM, SQL, filesystem metier, asyncio,
threading ou multiprocessing n'est une dependance du runtime 12.5.

## Dette explicitement differee

- accounting du temps actif lorsque l'attente gate suspend la deadline ;
- `BudgetState` et remaining budget ;
- retries, backoff et circuit breakers ;
- reconciliation reelle et snapshots ;
- resolver concret des policies pre-launch ;
- `GateEngine` et consommation de `GateDecision` ;
- runners agents, tools et use cases ;
- evaluateur canonique des success criteria workflow ;
- planner AG-01 et workflows WF-*.
