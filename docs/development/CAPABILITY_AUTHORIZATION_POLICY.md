# CapabilityAuthorizationPolicy

La Phase 12.4-D produit la decision logique finale par intersection de trois
sources immuables : `AccessMatrix` fixe la ceiling statique, `CapabilityRegistry`
decrit route et owner, et `PermissionScopeEvaluator` verifie le grant dynamique.
Cette combinaison n'est jamais une union de permissions. Un `DENY` matrix ou
scope reste terminal et ne propose aucun fallback.

## Dispositions

- `DENY` refuse sans reroutage ; la cause scope detaillee reste composee quand le
  scope a ete evalue.
- `ALLOW` autorise seulement l'agent owner ou l'autorite runtime/utility prevue.
- `REQUEST` demande la frontiere logique Application ou l'utilitaire via workflow ;
  ce n'est pas une execution ni un `ALLOW`.
- `DELEGATE` indique qu'AG-01 doit deleguer vers l'owner specialise ; AG-01
  n'execute pas CAP-E/G/V directement.
- `REQUEST_GATE` conserve la gate matrix de CAP-A02 meme si le scope ne porte
  aucune gate. Une gate satisfaite permet seulement `REQUEST` vers Application.
- `CONDITION_REQUIRED` attend une resolution workflow trusted. Les seules
  resolutions sont `ALLOW` et `REQUEST`, jamais un bool ambigu.

`PolicyFacts.matrix_gate_satisfied` est distinct des gates du `ScopeCheck`.
`PolicyFacts.conditional_resolution` resout uniquement la condition canonique
`request_or_allow_by_workflow`. Ces facts sont fournis par une couche
runtime/policy de confiance et ne sont derives d'aucun agent, document ou LLM.

## Routes et autorites

| Classe | Route | Autorite logique |
| --- | --- | --- |
| ORCHESTRATION | RUNTIME | AGENT_RUNTIME |
| EVIDENCE / GENERATE_TRANSFORM / REVIEW | AGENT | AGENT_SPECIALIST |
| READ | APPLICATION | APPLICATION |
| CAP-A01 / CAP-A02 | APPLICATION | APPLICATION_DOMAIN |
| CAP-A03 | APPLICATION | APPLICATION |
| TECHNICAL_UTILITY | UTILITY | TECHNICAL_UTILITY |

Ce mapping ne reference aucun handler, tool ou use case concret. La compatibilite
fine entre operation, payload et boundary aval n'est pas inventee dans D.

## Delegation owner-aware

La decision finale exige une rule AG-01 `DELEGATE`, une route `AGENT`, le target
owner exact et une rule target `ALLOW`. La capability du mandat doit appartenir
au grant parent ET au grant enfant avant de composer `DelegationScopePolicy`.
Ainsi CAP-G01 vers AG-03 peut etre autorise, tandis que CAP-G01 vers AG-02 produit
`OWNER_MISMATCH`, meme si C avait volontairement accepte le narrowing du scope.
Revocation, temporalite, denies, gates, budget et interdiction de redelegation
restent appliques par la policy C composee.

## Configuration fail-closed

`validate_policy_configuration` verifie les cardinalites 4/24/96 et toutes les
formes canoniques E/G/V, Application, Runtime et Utility. Une corruption leve
`PolicyConfigurationError` a la construction d'une policy custom ; elle ne peut
pas devenir une autorisation runtime.

La couche ne contient ni execution Application, routing concret, `ToolRegistry`,
`ToolCallPolicy`, gate engine, scheduler, budget state, provider ou sandbox. Ces
responsabilites restent hors de 12.4-D, notamment a 12.10 pour le routing concret.
