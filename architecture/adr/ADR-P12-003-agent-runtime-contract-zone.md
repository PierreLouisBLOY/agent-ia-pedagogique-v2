# ADR P12-003 - Zone technique des contrats runtime agentiques

## Statut

Accepte.

## Contexte

La Phase 12.3-C1 introduit les fondations contractuelles du runtime agentique. Ces
contrats doivent rester distincts du Domain, de l'Application, des modules metier,
des adaptateurs et de l'infrastructure. Ils materialisent des objets de donnees
immutables et provider-neutral, sans scheduler, registry, recovery ni evaluator.

## Decision

Le repertoire `backend/agent_runtime/` devient une zone technique distincte.
`backend/agent_runtime/contracts/` contient uniquement les contrats et value objects
runtime agentiques de la Phase 12.3-C1.

Cette zone peut dependre de `backend.shared_kernel` et de `backend.core_contracts`.
Les modules Domain/Application ne dependent jamais de `backend.agent_runtime`.
Les adaptateurs et l'infrastructure pourront l'implementer ou la consommer
ulterieurement par composition.

Les registries, scheduler, recovery, evaluator de permissions, adapters provider,
RAG, LLM, routing policy et tool policy restent hors de cette decision et hors du
lot 12.3-C1.

## Consequences

Les fitness functions d'architecture figent les regles suivantes :

- `backend.agent_runtime` n'importe pas `backend.modules`,
  `backend.adapters` ou `backend.infrastructure`.
- Les modules metier n'importent pas `backend.agent_runtime`.
- `backend.agent_runtime/contracts` n'introduit aucune dependance tierce.
- `StepSpec`, `DelegationEnvelope` et `AgentInvocation` ont une definition
  canonique unique.
- `DelegationRequest` n'est pas defini comme classe concurrente du nom final
  `DelegationEnvelope`.

Cette decision garde les contrats agentiques consommables par composition sans
attribuer d'autorite metier ou de logique runtime active a la nouvelle zone.
