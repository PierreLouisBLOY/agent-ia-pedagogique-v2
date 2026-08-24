# Validation statique des plans

## Modele

`Plan` est un modele immutable cree par AG-01. `workflow_kind` est un identifiant
opaque : le catalogue WF-0..WF-11 n'est pas anticipe en 12.5-B. Les dependances
du DAG sont derivees exclusivement de `StepSpec.depends_on`; le plan ne duplique
pas les edges dans un champ separe.

`ExecutorKind.RUNTIME` designe l'execution technique des control nodes `gate`,
`join` et `decision`. Il ne correspond a aucun `AgentId`. AG-01 planifie, mais ne
devient pas un executor specialise. Les autres correspondances sont : agent vers
AG-02/03/04, use case vers Application et tool vers Utility.

## Controles avant effet

`PlanValidator.validate` retourne un resultat deterministe et des issues au lieu
de lever pour une invalidite semantique. Les codes fermes sont :

- `DUPLICATE_STEP_ID`, `STEP_LIMIT_EXCEEDED`, `UNKNOWN_DEPENDENCY`,
  `DEPENDENCY_CYCLE` ;
- `UNKNOWN_CAPABILITY`, `KIND_EXECUTOR_MISMATCH`,
  `CAPABILITY_ROUTE_MISMATCH`, `AGENT_OWNER_MISMATCH` ;
- `PARALLEL_DEPENDENCY_CONFLICT`, `STEP_BUDGET_OUT_OF_ENVELOPE`.

La validation controle la limite de steps, les references et cycles transitifs,
la coherence kind/executor, l'existence et la route registry d'une capability et
l'owner des capabilities agent. Les capabilities sont obligatoires pour agent,
use case et tool, optionnelles pour les control nodes.

Deux steps d'un meme `parallel_group` ne peuvent avoir de relation de dependance
directe ou transitive. Ce controle structurel ne pretend pas detecter des
dependances semantiques cachees dans les donnees. Les budgets sont compares par
`budget_is_narrower_or_equal` : chaque step conserve ou reduit l'enveloppe bornee
du plan. Ils ne sont ni sommes, ni reserves, ni consommes.

## Validations reportees

La validation statique n'est pas une authorization policy et ne consulte pas
`PermissionScope`. Les schemas I/O detailles, gates reelles, scope resolution,
`CapabilityAuthorizationPolicy.evaluate`, disponibilite adapter/provider et
idempotence sont des controles pre-launch de 12.5-C/D ou 12.10. Consommation,
remaining budget, staleness, snapshots et restore restent 12.11.

Aucun contenu agent ou document ne peut modifier policy, permission ou autorite.
