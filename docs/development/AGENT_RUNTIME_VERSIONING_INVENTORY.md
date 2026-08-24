# Inventaire du versioning runtime agentique

Chaque `ContractMeta` porte `schema_version`, `run_id`, `step_id`,
`correlation_id`, `created_at`, `actor` et `status`. D1 fixe `schema_version` au
type `ContractSchemaVersion`, avec `1.0` comme baseline canonique.

| ID | Contrat | Metadata | Schema / correlation | Statut | Niveau | Traitement D1 |
|---|---|---|---|---|---|---|
| C-01 | `AgentInvocation` | DIRECT_META | `meta` | `InvocationStatus` | top-level | baseline `1.0` |
| C-02 | `AgentResult` | DIRECT_META | `meta` | `AgentResultStatus` | top-level | baseline `1.0` |
| C-03 | `DelegationEnvelope` | NESTED_VALUE | via `AgentInvocation.meta` lorsqu'invoquee | via invocation | valeur composee | contexte parent explicite |
| C-04 | `DelegationResult` | COMPOSED_META | via `agent_result.meta` | `AgentResultStatus` | top-level compose | extraction composee |
| C-05 | `EvidenceRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | baseline `1.0` |
| C-06 | `EvidenceSet` + `EvidenceItem` | DIRECT_META | `EvidenceSet.meta`; item imbrique | `AgentResultStatus` | set top-level, item nested | baseline du parent |
| C-07 | `ProductionRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | baseline `1.0` |
| C-08 | `ProductionCandidate` | DIRECT_META | `meta` | `AgentResultStatus` + `candidate` | top-level | baseline `1.0` |
| C-09 | `ReviewRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | baseline `1.0` |
| C-10 | `ReviewResult` + `Finding` | DIRECT_META | `ReviewResult.meta`; finding imbrique | `ReviewStatus` | result top-level, finding nested | baseline du parent |
| C-11 | `CorrectionRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | baseline `1.0` |
| C-12 | `UseCaseRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | baseline `1.0` |
| C-13 | `UseCaseResult` | DIRECT_META | `meta`; correlation avec `ApplicationOutcome` | `OutcomeStatus` | top-level compose | baseline `1.0` |
| C-14 | `ToolCallRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | baseline `1.0` |
| C-15 | `ToolCallResult` | DIRECT_META | `meta` | `AgentResultStatus` | top-level | baseline `1.0` |
| C-16 | `GateRequest` | DIRECT_META | `meta` | `GateStatus.pending` | top-level | baseline `1.0` |
| C-17 | `GateDecision` | DIRECT_META | `meta`; correlation avec request | `GateStatus` + decision | top-level compose | baseline `1.0` |
| C-18 | `WorkflowEvent` | DIRECT_META | `meta` | `WorkflowStatus` | top-level | baseline `1.0` |
| C-19 | `ErrorEnvelope` | NESTED_VALUE | via contrat parent; `step_id` propre | taxonomie erreur | valeur imbriquee | contexte parent explicite |

Le complement `CorrectionResult`, hors famille C-*, porte directement
`ContractMeta[AgentResultStatus]`. Il correle la `CorrectionRequest`, la version
parente exacte et la nouvelle version candidate exacte. La nouvelle reference
conserve le meme `object_ref` et porte un `version_ref` opaque distinct, sans
supposer d'ordre ni d'arithmetique de version. Elle ne rend pas cette nouvelle
version canonique. `SupplementalContractKind.CORRECTION_RESULT` lui fournit une
cle de versioning DIRECT_META distincte de C-11, avec `1.0` comme baseline.

`DelegationEnvelope` ne porte pas de correlation directe exploitable. D1 conserve
donc la correlation de C-04 via `AgentResult.meta` et le `step_id` de la delegation,
sans dupliquer de metadata. C-03 et C-19 exigent le contexte de version de leur
parent ; C-04 lit `agent_result.meta.schema_version`.

## CLOSED en C3

- classification DIRECT_META / COMPOSED_META / NESTED_VALUE complete ;
- cibles review et correction epinglees par `ObjectVersionRef` ;
- delta de correction vN vers nouvelle candidate materialise par `CorrectionResult` ;
- lineage local et correlations deterministes verifies ;
- matrice C-01..C-19 couverte par fitness function.

## CLOSED en D1

- baseline canonique `1.0` au format strict `MAJOR.MINOR` ;
- policy couvrant exactement 19 familles C-* et `CorrectionResult`, soit 20 sujets ;
- aucune C-20 : `CorrectionResult` reste un contrat supplemental de Phase 11.12 ;
- refus propre des majors inconnus et minors hors plage ;
- compatibilite additive par minor et breaking par major ;
- extraction DIRECT_META, COMPOSED_META et contexte NESTED_VALUE ;
- catalogue de migrations explicites, vide en production pour la baseline.

## HORS CORE D1

- schemas JSON, Pydantic ou autre serialisation concrete ;
- `AgentRegistry`, `CapabilityRegistry` et evaluator de permissions de 12.4 ;
- scheduler, routing, recovery, providers et persistance.
