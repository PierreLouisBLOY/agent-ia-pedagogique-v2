# ADR P12-006 - Etat et planification du runtime deterministe

## Statut

Accepte.

## Contexte

La Phase 12.5-B doit materialiser un plan explicite, l'etat technique d'un run et
de ses steps, ainsi qu'une validation statique du DAG avant tout effet. Les
contrats 12.3 et les registries/policies 12.4 existent deja. Le nouveau lot ne
doit ni introduire une seconde autorite metier, ni anticiper l'execution,
l'autorisation pre-launch ou le recovery persiste.

## Decision

`backend/agent_runtime/runtime/` contient exclusivement l'orchestration technique
deterministe. Cette zone peut dependre des contrats runtime, des registries, de la
policy, de `core_contracts`, de `shared_kernel` et de la bibliotheque standard.
Elle ne depend d'aucun module Domain/Application, adaptateur, element
d'infrastructure ou provider. Inversement, Domain, Application et les modules
metier ne dependent jamais du runtime agentique.

`Plan` est immutable. Son DAG est derive uniquement de `StepSpec.depends_on` ; il
n'existe pas de champ `dependencies` concurrent. AG-01 est l'auteur obligatoire
du plan, mais n'est pas ajoute comme executor specialise. `ExecutorKind.RUNTIME`
porte les control nodes `gate`, `join` et `decision`, et n'est associe a aucun
`AgentId`.

`StepState` et `RunState` sont des etats techniques immutables, sans concept
metier. `RunState` reutilise `WorkflowStatus` et expose des proprietes derivees,
dont `current_step_ids` au pluriel. La factory initiale valide le plan puis cree
uniquement des steps `PENDING` et un run `PLANNED` ; elle ne calcule pas `READY`.

La validation statique controle cardinalite, references, cycles, coherence
kind/executor, existence et route des capabilities, owner des agents, presence
d'un `permission_scope_ref` pour les steps executables, conflits de dependance
transitive dans les groupes paralleles, convergence vers un join explicite,
presence structurelle d'une gate exigee par la ceiling matrix et narrowing des
enveloppes de budget. Elle ne charge ni n'evalue `PermissionScope`, ne verifie
aucune `GateDecision` et ne constitue pas une autorisation. Un futur etat `READY`
ne signifiera jamais qu'un lancement est autorise.

Aucun framework ni provider n'est requis. Le scheduler de decision pur arrive en
12.5-C ; l'executor et les transitions de lancement restent reserves a 12.5-D.
Gates d'execution et routing concret restent 12.10 ; snapshots, consommation
budgetaire et recovery complet restent 12.11.

## Consequences

- le plan est inspectable et invalide avant tout effet ;
- l'etat runtime reste distinct de `StepSpec` et des statuts metier ;
- les joins sont explicites par des steps runtime et le DAG reste acyclique ;
- l'ordre des proprietes derivees suit l'ordre d'insertion de `step_states` ;
- les dependances semantiques cachees ne peuvent pas etre detectees statiquement ;
- l'autorisation, les schemas I/O, la disponibilite des adapters, les retries et
  le recovery restent hors de ce lot.

## Correctif apres audit 12.5-B

Les findings P12.5B-F01/F02/F03 ajoutent trois preuves structurelles sans etendre
l'autorite du runtime : un executable reference un scope, chaque
`parallel_group` d'au moins deux branches converge vers un `StepKind.JOIN`
commun, et une capability `REQUEST_GATE` pour AG-01 possede un ancetre
`StepKind.GATE`. Le join ne realise aucune aggregation semantique et la gate ne
prouve aucune decision. Scope, gate et budget seront toujours reevalues juste
avant lancement ; execution des gates et routing concret restent 12.10.

## Extension Phase 12.5-C

`runtime/scheduling` ajoute une decision pure et sans etat interne. Elle derive
READY/BLOCKED, propage les blocages jusqu'au point fixe, borne les candidats par
`max_parallel_steps` et emet seulement des signaux de deadline. L'ordre des
candidats suit `Plan.steps`, jamais l'ordre accidentel d'un mapping de state.

PARTIAL et SKIPPED restent non resolus en l'absence de policy declarative plus
precise. Les JOIN suivent la semantique ordinaire des dependances et n'agregent
aucune donnee. Une deadline atteinte ne mute aucun step. Le calcul exact du temps
actif hors gate est differe a 12.11.

Un candidat reste READY : autorisation, scope, gate et budget remaining seront
reevalues par la frontiere pre-launch de D avant toute transition RUNNING.
