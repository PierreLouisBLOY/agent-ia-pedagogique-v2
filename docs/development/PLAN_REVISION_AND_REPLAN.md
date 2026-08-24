# Revision versionnee des plans

## Frontiere 12.5-E

Un replan modifie le chemin d'execution d'un run sans modifier son intention. Il
est distinct d'un retry : le retry poursuit la meme intention locale, tandis
qu'une revision adopte un `Plan` de remplacement explicitement fourni.

`PlanRevisionEngine` ne genere, ne corrige et ne complete jamais un Plan. Il
valide puis applique uniquement un replacement externe. Le planner AG-01 concret
reste 12.6 ; aucun LLM, provider, RAG ou routing concret n'est introduit ici.

## Historique et versions

`PlanHistory` est une sequence immutable de Plans frozen appartenant au meme
run, plan et workflow. Elle commence en version 1, exige des versions strictement
contigues et expose `latest`. Son `append` retourne une nouvelle histoire et ne
mute jamais l'ancienne.

Un replacement doit avoir exactement `current.plan_version + 1`. La hard limit
provient de `AgentRuntimePolicy.max_plan_versions`, soit 6 dans la baseline. Une
proposition de version 7 est refusee ; aucun wrap, nouveau run ou contournement
n'est cree. L'histoire reste purement en memoire technique et ne stocke aucun
ancien `RunState`.

## Preconditions et protection contre le goal drift

La revision exige un `RunState` coherent avec le dernier Plan, au statut
REPLANNING et sans step RUNNING. Elle ne tente ni annulation ni reconciliation
d'un effet actif.

Le replacement conserve exactement `run_id`, `plan_id`, `workflow_kind`,
`objective`, `success_criteria` et `stop_conditions`. Une revision change le
chemin, pas le but ou la definition du succes. Le replacement est ensuite passe
au `PlanValidator` canonique ; E ne duplique aucune validation statique du DAG.

## Identite d'execution et lineage

L'identite d'execution d'un step comprend `kind`, `capability_id`, `executor`,
`objective`, `input_refs`, `depends_on`, `success_criteria`, `output_contract`
et `parallel_group`. Un `step_id` present dans deux versions ne peut changer
aucun de ces champs : une semantique differente exige un nouvel identifiant.

`permission_scope_ref`, `budget` et `failure_policy` sont des controles
d'execution et sont exclus de cette identite. Ils ne changent pas
retroactivement le resultat produit par un step SUCCEEDED.

La reconstruction applique quatre cas :

- un step SUCCEEDED d'identite stable reutilise son `StepState` complet ;
- tout autre statut existant est reset en PENDING en conservant uniquement son
  `attempt_count`, qui represente le lineage ;
- un nouveau step commence PENDING avec attempt 0 ;
- un ancien step absent est liste comme removed et quitte le snapshot courant.

PARTIAL et SKIPPED ne sont jamais reutilises automatiquement. Aucun READY n'est
calcule pendant la revision : le scheduler suivant recalculera READY/BLOCKED.

## No-progress et cycles

La signature structurelle conserve l'ordre des steps, leur `step_id` et leur
identite d'execution. Elle ignore version, budget, scope, failure policy,
risk profile et assumptions. Modifier seulement ces controles constitue donc
`NO_STRUCTURAL_PROGRESS`, pas un nouveau chemin.

Le retour a la signature d'une version anterieure produit
`STRUCTURAL_CYCLE_DETECTED`. Cette detection est pure, deterministe et bornee par
l'histoire en memoire ; aucun juge semantique ou heuristique ne fabrique un plan
alternatif.

## Etat adopte et limites

Une revision acceptee conserve correlation, artifacts, erreurs et snapshot de
contexte, remplace `plan_version` et reconstruit les steps dans l'ordre du
replacement. Un run jamais commence revient PLANNED sans timestamp ; un run deja
commence revient RUNNING en conservant son `started_at`. Aucun step n'est lance.

E ne fournit ni `BudgetState`, remaining accounting, retry/backoff, recovery,
effect reconciliation, persistence ou `StateSnapshotStore`. Le refus retourne
des issues et ne terminalise pas lui-meme le run. L'audit cumulatif,
rationalisation et merge sont reserves a 12.5-F.
