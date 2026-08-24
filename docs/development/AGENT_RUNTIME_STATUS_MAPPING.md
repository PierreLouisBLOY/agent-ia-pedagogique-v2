# Mapping des statuts runtime agentiques

Ce document clot en C3 l'inventaire des vocabulaires de statut. Il ne definit
aucune transition, policy, machine a etats, recovery ou autorite supplementaire.

| Famille | Vocabulaire exact | Autorite semantique |
|---|---|---|
| Invocation / delegation | `planned`, `running`, `succeeded`, `partial`, `failed`, `cancelled`, `escalated` | Runtime agentique |
| AgentResult | `succeeded`, `partial`, `failed`, `cancelled`, `escalated` | Runtime agentique |
| Workflow | `planned`, `running`, `waiting_gate`, `replanning`, `succeeded`, `partial`, `failed`, `cancelled`, `escalated` | Runtime agentique |
| Step runtime | `pending`, `ready`, `running`, `succeeded`, `partial`, `failed`, `cancelled`, `blocked`, `skipped` | Etat technique du runtime deterministe |
| Production | `candidate` uniquement | Runtime agentique, non canonique |
| Review | `completed`, `incomplete`, `failed` | Execution de la review |
| Gate | `pending`, `approved`, `rejected`, `deferred`, `expired` | Autorite externe attendue |
| Application | `OutcomeStatus` | Application, distinct du runtime agentique |

Les etats de production `validated`, `rejected`, `promoted` et `superseded`
restent sous autorite Application/Domain. Ils ne sont ni ajoutes a
`ProductionValidationState`, ni derives d'un `ReviewResult`, d'un
`CorrectionResult` ou d'une sortie agentique.

`OverallAssessment` qualifie une review et ne remplace aucun statut de validation.
Une review `incomplete` ne peut pas porter l'evaluation `acceptable` ; les autres
coherences restent exprimees par les invariants propres a `ReviewResult`.
`GateDecisionValue` enregistre une decision de l'autorite requise et ne constitue
pas une policy de transition du workflow.

La Phase 12.5-B reutilise `WorkflowStatus` dans `RunState` et ne cree aucun
`RunStatus` concurrent. `StepRuntimeStatus` est local a l'etat technique des
steps. Il ne contient pas `waiting_gate` : la suspension gate reste globale. Un
step `READY` n'est pas implicitement autorise ; les controles policy et scope
restent obligatoires juste avant un futur lancement.

## CLOSED en C3

- vocabulaires exacts inventories et couverts par fitness function AST ;
- `ProductionCandidate` limite a `candidate` ;
- absence de champs `validated` ou `promoted` sur `ReviewResult` ;
- garde d'auteur AG-01 conservee sur `GateDecision` ;
- distinction explicite entre runtime, review, gate et `OutcomeStatus`.

## DEFERRED TO 12.3-D

- policy de compatibilite et de versions supportees ;
- migrations et negotiation de versions ;
- schemas de serialization ;
- toute policy de transition entre statuts.
