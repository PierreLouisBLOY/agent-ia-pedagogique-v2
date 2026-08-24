# Contrats runtime agentiques

Les Phases 12.3-C1 et 12.3-C2 materialisent `backend/agent_runtime/contracts/`
comme zone technique provider-neutral pour les contrats runtime agentiques. Cette zone est hors
Domain/Application, hors modules metier, hors adaptateurs et hors infrastructure.

## Matrice C-01..C-19

| ID | Type materialise | Placement | Statut |
|---|---|---|---|
| C-01 | `AgentInvocation` | `contracts/invocation/agent_invocation.py` | IMPLEMENTED C1 |
| C-02 | `AgentResult` | `contracts/invocation/agent_result.py` | IMPLEMENTED C1 |
| C-03 | `DelegationEnvelope` | `contracts/planning/delegation.py` | IMPLEMENTED C1 |
| C-04 | `DelegationResult` | `contracts/delegation/delegation_result.py` | IMPLEMENTED C2 |
| C-05 | `EvidenceRequest` | `contracts/evidence/evidence_request.py` | IMPLEMENTED C2 |
| C-06 | `EvidenceItem`, `EvidenceSet` | `contracts/evidence/` | IMPLEMENTED C2 |
| C-07 | `ProductionRequest` | `contracts/production/production_request.py` | IMPLEMENTED C2 |
| C-08 | `ProductionCandidate` | `contracts/production/production_candidate.py` | IMPLEMENTED C2 |
| C-09 | `ReviewRequest` | `contracts/review/review_request.py` | IMPLEMENTED C2 |
| C-10 | `Finding`, `ReviewResult` | `contracts/review/` | IMPLEMENTED C2 |
| C-11 | `CorrectionRequest` | `contracts/review/correction_request.py` | IMPLEMENTED C2 |
| C-12 | `UseCaseRequest` | `contracts/application/use_case_request.py` | IMPLEMENTED C2 |
| C-13 | `UseCaseResult` | `contracts/application/use_case_result.py` | IMPLEMENTED C2 |
| C-14 | `ToolCallRequest` | `contracts/tools/tool_call_request.py` | IMPLEMENTED C2 |
| C-15 | `ToolCallResult` | `contracts/tools/tool_call_result.py` | IMPLEMENTED C2 |
| C-16 | `GateRequest` | `contracts/gates/gate_request.py` | IMPLEMENTED C2 |
| C-17 | `GateDecision` | `contracts/gates/gate_decision.py` | IMPLEMENTED C2 |
| C-18 | `WorkflowEvent` | `contracts/events/workflow_event.py` | IMPLEMENTED C2 |
| C-19 | `ErrorEnvelope` enrichi Phase 11.13 | `contracts/errors/error_envelope.py` | IMPLEMENTED C1 |

Le label historique C-03 `DelegationRequest` est supersede par le nom final
`DelegationEnvelope`. C-04 etait explicitement hors C1 ; il est inclus dans C2
pour assurer la completude de la serie C-01..C-19.

## Hierarchie contractuelle

`StepSpec` decrit une unite de travail declarative et immutable : kind, executor,
capability optionnelle, objectif, references d'entree, dependances, budget,
criteres de succes et contrat de sortie. Elle ne porte aucun statut runtime,
aucune selection provider/model et aucune logique de scheduler ou DAG.

`DelegationEnvelope` specialise une `StepSpec` agent. Le libelle historique C-03
`DelegationRequest` est remplace par le nom final `DelegationEnvelope`. L'enveloppe
compose la `StepSpec` source et ajoute uniquement les informations propres a la
delegation : cible AG-02/AG-03/AG-04, contexte fige, preuves, contraintes, scope
de permission et contexte de trace.

`AgentInvocation` represente une tentative runtime concrete. Elle compose
`ContractMeta`, la `StepSpec` source, une `DelegationEnvelope` optionnelle,
l'agent cible, l'autonomie, le mode runtime et le numero de tentative. Elle ne
recopie pas objectif, inputs, permissions, budget ou contrat attendu.

`AgentResult` porte le resultat provider-neutral d'une invocation : payload type,
artefacts, preuves, avertissements structures, metriques, erreur eventuelle et
raison d'arret. Les statuts `failed`, `cancelled` et `escalated` appliquent les
contraintes minimales de presence d'erreur ou de raison d'arret.

`DelegationResult` compose `AgentResult` et ne reprend ni son payload, ni ses
artefacts, avertissements, metriques ou erreurs. La composition optionnelle de
`DelegationEnvelope` permet uniquement de verifier localement l'identite de la
delegation, l'agent source et le step correle.

## Contrats specialises C2

Les contrats evidence distinguent l'intention de recherche de son resultat.
`EvidenceItem` exige une provenance minimale et `EvidenceSet` accepte explicitement
un resultat vide. Aucun item fictif n'est fabrique.

`ProductionRequest` decrit une intention de production. `ProductionCandidate`
reste non canonique : son enum `ProductionValidationState` ne contient que
`candidate`. Revue, correction, validation et promotion restent des responsabilites
distinctes. `ReviewResult` ne modifie pas sa cible et `CorrectionRequest` decrit
une transformation version-orientee ulterieure.

`UseCaseRequest` compose le `UseCaseContext` canonique et ne connait aucun handler.
`UseCaseResult` compose `ApplicationOutcome`; ses erreurs metier, avertissements et
side effects restent donc visibles sans duplication. Les contrats tools ne font
qu'exprimer une intention et son resultat public. Un `tool_id` ne confere aucune
autorisation et aucun outil n'est execute dans cette zone.

Les gates emploient les statuts exacts `pending`, `approved`, `rejected`, `deferred`
et `expired`. Une decision ne peut etre attribuee logiquement a AG-01. Les events
emploient le `WorkflowStatus` exact de Phase 11.8 et ne mettent en oeuvre aucun
backend de logs ou de traces.

Pour les requetes et resultats sans vocabulaire specialise fixe par Phase 11.8,
C2 reutilise respectivement `InvocationStatus` et `AgentResultStatus` lorsque leur
semantique runtime est identique. `UseCaseResult` reutilise `OutcomeStatus` via
`ApplicationOutcome`. La Phase 12.3-C3 auditera globalement la completude, les
status mappings, le lineage et le versioning preparatoire.

## Permissions et erreurs

`PermissionScope` est seulement un data contract immutable. Il exprime principal,
capabilities, ressources, operations, contraintes, validite, budget, delegabilite,
gates et deny rules. Aucun evaluator, `allows`, merge, grant ou union de scopes
n'est implemente en 12.3-C1. L'evaluator et `CapabilityRegistry` restent prevus
pour 12.4.

`ErrorEnvelope` materialise la taxonomie enrichie de Phase 11.13 avec categorie,
source, severite, retryability declarative, etat d'effet, action recommandee,
references liees et details agent-safe. `effect_state=unknown` reste representable,
et `retryable=True` ne declenche aucune action.

## Donnees agent-safe

Les mappings runtime passent par le helper Shared Kernel `freeze_safe_mapping`,
complete par le rejet des cles agentiques privees : chain of thought, raisonnement
prive et prompt systeme. Les metadonnees provider-neutral telles que `token_count`,
`input_tokens`, `output_tokens`, `token_budget`, `search_query` et `query_kind`
restent autorisees.

## Hors lot

Le coeur runtime ne contient aucun provider, framework, SDK, HTTP, ORM, SQL,
scheduler, registry, evaluator, recovery, RAG, LLM, routing policy, tool policy,
execution de use case, execution d'outil ou gate engine. Ces responsabilites ne
sont pas introduites par C2.
