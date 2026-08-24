# Inventaire preparatoire du versioning runtime agentique

Chaque `ContractMeta` porte `schema_version`, `run_id`, `step_id`,
`correlation_id`, `created_at`, `actor` et `status`. C3 inventorie leur placement ;
la validation formelle des versions supportees reste reservee a 12.3-D.

| ID | Contrat | Metadata | Schema / correlation | Statut | Niveau | Gap avant D |
|---|---|---|---|---|---|---|
| C-01 | `AgentInvocation` | DIRECT_META | `meta` | `InvocationStatus` | top-level | policy globale |
| C-02 | `AgentResult` | DIRECT_META | `meta` | `AgentResultStatus` | top-level | policy globale |
| C-03 | `DelegationEnvelope` | NESTED_VALUE | via `AgentInvocation.meta` lorsqu'invoquee | via invocation | valeur composee | compatibilite standalone |
| C-04 | `DelegationResult` | COMPOSED_META | via `agent_result.meta` | `AgentResultStatus` | top-level compose | compatibilite composee |
| C-05 | `EvidenceRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | policy globale |
| C-06 | `EvidenceSet` + `EvidenceItem` | DIRECT_META | `EvidenceSet.meta`; item imbrique | `AgentResultStatus` | set top-level, item nested | version item |
| C-07 | `ProductionRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | policy globale |
| C-08 | `ProductionCandidate` | DIRECT_META | `meta` | `AgentResultStatus` + `candidate` | top-level | policy globale |
| C-09 | `ReviewRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | policy globale |
| C-10 | `ReviewResult` + `Finding` | DIRECT_META | `ReviewResult.meta`; finding imbrique | `ReviewStatus` | result top-level, finding nested | version finding |
| C-11 | `CorrectionRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | policy globale |
| C-12 | `UseCaseRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | policy globale |
| C-13 | `UseCaseResult` | DIRECT_META | `meta`; correlation avec `ApplicationOutcome` | `OutcomeStatus` | top-level compose | compatibilite outcome |
| C-14 | `ToolCallRequest` | DIRECT_META | `meta` | `InvocationStatus` | top-level | policy globale |
| C-15 | `ToolCallResult` | DIRECT_META | `meta` | `AgentResultStatus` | top-level | policy globale |
| C-16 | `GateRequest` | DIRECT_META | `meta` | `GateStatus.pending` | top-level | policy globale |
| C-17 | `GateDecision` | DIRECT_META | `meta`; correlation avec request | `GateStatus` + decision | top-level compose | compatibilite request |
| C-18 | `WorkflowEvent` | DIRECT_META | `meta` | `WorkflowStatus` | top-level | policy globale |
| C-19 | `ErrorEnvelope` | NESTED_VALUE | via contrat parent; `step_id` propre | taxonomie erreur | valeur imbriquee | compatibilite erreur |

Le complement `CorrectionResult`, hors famille C-*, porte directement
`ContractMeta[AgentResultStatus]`. Il correle la `CorrectionRequest`, la version
parente exacte et la nouvelle version candidate exacte. La nouvelle reference
conserve le meme `object_ref` et porte un `version_ref` opaque distinct, sans
supposer d'ordre ni d'arithmetique de version. Elle ne rend pas cette nouvelle
version canonique.

`DelegationEnvelope` ne porte pas de correlation directe exploitable. C3 conserve
donc la correlation de C-04 via `AgentResult.meta` et le `step_id` de la delegation,
sans dupliquer de metadata. La politique de compatibilite de cette composition
est une decision de D.

## CLOSED en C3

- classification DIRECT_META / COMPOSED_META / NESTED_VALUE complete ;
- cibles review et correction epinglees par `ObjectVersionRef` ;
- delta de correction vN vers nouvelle candidate materialise par `CorrectionResult` ;
- lineage local et correlations deterministes verifies ;
- matrice C-01..C-19 couverte par fitness function.

## DEFERRED TO 12.3-D

- registry et policy de versions supportees ;
- refus global d'une version non supportee ;
- migrations, compatibilite backward/forward et negotiation ;
- parser semver ;
- schemas JSON, Pydantic ou autre serialization formelle.
