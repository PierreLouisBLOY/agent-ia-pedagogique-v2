# Contrats runtime agentiques

La Phase 12.3-C1 introduit `backend/agent_runtime/contracts/` comme zone technique
provider-neutral pour les fondations runtime agentiques. Cette zone est hors
Domain/Application, hors modules metier, hors adaptateurs et hors infrastructure.

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

La Phase 12.3-C2 reste responsable des contrats specialises C-05 a C-18. Le coeur
runtime ne contient aucun provider, framework, SDK, HTTP, ORM, SQL, scheduler,
registry, recovery, RAG, LLM, routing policy ou tool policy.
