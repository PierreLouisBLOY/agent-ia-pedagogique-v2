# Structure du depot

Cette baseline materialise sans logique metier la structure normative issue de la Phase 6.15.

## Correspondance des zones

| Zone reelle | Responsabilite canonique |
| --- | --- |
| `backend/shared_kernel/` | Primitives techniques generiques partagees |
| `backend/core_contracts/` | Frontieres contractuelles transverses futures |
| `backend/agent_runtime/contracts/` | Contrats techniques runtime agentiques provider-neutral |
| `backend/agent_runtime/agents/` | Frontieres techniques provider-neutral des responsabilites agentiques specialisees, sans adapters ni autorite metier |
| `backend/agent_runtime/registry/` | Catalogues statiques agents/capabilities et ceiling matrix exhaustive |
| `backend/agent_runtime/policy/` | Garde-fous techniques runtime configurables, sans autorite metier |
| `backend/agent_runtime/orchestration/` | Catalogue, selection, compilation et coordination deterministes des workflows, sans execution ni routing |
| `backend/agent_runtime/runtime/` | Plan et revision versionnee, validation du DAG, etat technique, scheduler pur et frontiere d'execution deterministe sans binding concret ni autorite metier |
| `backend/modules/` | Coeur metier decoupe en M01 a M12 et MX1 |
| `backend/adapters/inbound/` | Entrees API, UI locale, CLI, outils agents et batch |
| `backend/adapters/outbound/` | Integrations sortantes futures |
| `backend/infrastructure/` | Configuration, composition et observabilite |
| `tests/` | Tests par niveau et par frontiere |
| `architecture/adr/` | Decisions d'architecture explicites |

Les repertoires sont des frontieres et des emplacements reserves. Les marqueurs `__init__.py` ne contiennent aucune logique metier.

## Modules canoniques

| Code | Repertoire |
| --- | --- |
| M01 | `knowledge_reference` |
| M02 | `documents_provenance` |
| M03 | `resource_library` |
| M04 | `pedagogical_design` |
| M05 | `transformation_assembly` |
| M06 | `analysis_simulation` |
| M07 | `pedagogical_context` |
| M08 | `work_orchestration` |
| M09 | `validation_control` |
| M10 | `quality_evaluation` |
| M11 | `lifecycle_promotion` |
| M12 | `materialization_export` |
| MX1 | `audit_traceability` |

Chaque module porte les memes sous-frontieres `domain/`, `contracts/`, `ports/` et `application/` definies par la Phase 6.15. Aucun adaptateur ni element d'infrastructure n'est place sous un module.

## Regle de dependance

Le metier reste local a son module. Le shared kernel demeure generique. Les adaptateurs consomment les ports et use cases prevus; les outils agents entrent uniquement par `backend/adapters/inbound/agent_tools/`. Les contrats restent independants de HTTP, d'un ORM et des SDK fournisseurs.

Les repertoires globaux `backend/domain/`, `backend/repositories/` et `backend/services/` sont interdits. Les tests de `tests/architecture/` gardent cette baseline sans anticiper les fitness functions completes des phases suivantes.

Sous `backend/agent_runtime/runtime/execution/`, le guard pre-launch et le runner
restent des Protocols injectes. Cette zone applique uniquement les transitions
techniques et directives de 12.5-D ; elle ne contient aucun adapter, provider,
gate engine, routing concret, retry loop ou repository.

Sous `backend/agent_runtime/runtime/planning/revision.py`, E valide et adopte un
replacement externe, reconstruit un snapshot courant et conserve un historique
immutable en memoire. Cette zone ne genere aucun Plan et ne persiste aucun
historique ou RunState.

Sous `backend/agent_runtime/orchestration/workflows/`, le catalogue immutable
decrit uniquement les topologies canoniques WF-0 a WF-11 et leur ownership
indicatif. Il ne selectionne aucun workflow, ne construit aucun Plan/StepSpec et
n'accorde aucune permission.

Sous `backend/agent_runtime/orchestration/selection/`, un selector immutable
compose ces topologies a partir d'exigences explicites et emet des reason codes
fermes. Il ne parse aucune intention, ne construit aucun Plan/StepSpec, ne route
aucun appel et n'evalue aucune permission.

Sous `backend/agent_runtime/orchestration/compilation/`, le PlanCompiler
materialise une selection et des bindings caller-supplied en Plan/StepSpec
canoniques, puis appelle PlanValidator. Il n'invente aucune semantique, n'evalue
aucun scope et n'execute ni ne route aucun step.

Sous `backend/agent_runtime/orchestration/coordination/`, AG-01 supervise un
`ExecutionCycleResult` deja produit. Le coordinateur conserve les observations,
refuse les directives decisives incoherentes, evalue la completion uniquement a
quiescence via un Protocol injecte et delegue l'adoption d'un replacement fourni
a `PlanRevisionEngine`. Il n'execute aucun retry, gate, runner ou handler.

Sous `backend/agent_runtime/agents/evidence/`, la frontiere AG-02 12.7-B decrit
les requetes techniques, candidats, signaux et acces documentaire provider-neutral
ainsi que deux Protocols injectables. Elle reutilise les contrats C-05/C-06 sans
construire de preuve publique et ne contient aucun coordinator, adapter, SQL,
HTTP, provider ou vector store.

La couche 12.7-C du meme repertoire ajoute un `RetrievalCoordinator` pur. Elle
execute les canaux dans un ordre ferme, applique l'admissibilite STRUCTURED avant
la pertinence, deduplique par identite et version, puis fusionne les rangs en
`Decimal`. Elle ne recherche aucun contenu DOCUMENT, ne construit aucune preuve
publique et n'ajoute ni adapter, ni retry, ni reranker.

La couche 12.7-D ajoute `EvidenceAgent`, qui separe CAP-E01, CAP-E02 et CAP-E03.
Elle controle l'identite et la version du contenu, materialise les contrats C-06,
mesure uniquement la couverture structurelle et preserve les divergences de
versions. Le meta reste fourni par le caller ; aucun enchainement automatique,
provider concret, retry ou autorite metier n'est introduit.

La couche 12.7-E du meme repertoire ajoute un scanner pur d'indicateurs
d'injection/poisoning et un advisor d'expansion bornée. Les documents restent
des donnees non autoritatives, les duplications ne deviennent pas une
corroboration independante et les URL ne sont jamais suivies. L'advisor conserve
scope et source policy, applique les bornes 3 rounds/12 items et no-progress,
puis produit uniquement une proposition pour AG-01. Il n'execute aucune round,
n'introduit ni recursion, ni provider, ni SecurityEvent global, ni wiring
runtime/orchestration.

Sous `backend/agent_runtime/agents/generation/`, la frontiere 12.8-B definit les
operations techniques immutables, la requete preparee, le resultat technique et
le Protocol outbound unique d'AG-03. Elle reste distincte des contracts
`ProductionCandidate` et `CorrectionResult`, ne choisit aucun provider, modele
ou prompt et n'effectue ni recherche, ni acces direct aux donnees, ni validation,
promotion, retry ou wiring runtime/orchestration.

La couche 12.8-C du meme repertoire prepare deterministement C-07 pour ce port,
verifie capability, operation, target et lineage d'evidence, puis autorise au
plus un appel outbound. Elle revalide tout appel prepare avant execution, ne
construit aucune `ProductionCandidate` ou correction et ne traduit ni ne retente
les erreurs techniques du port.

La couche 12.8-D ajoute `GeneratorAgent` pour CAP-G01 et CAP-G02. Apres
preparation et execution par le coordinateur, une operation explicite revalide
la lineage et materialise le contrat C-08 existant avec un metadata et une
`production_id` fournis par le caller. Seuls `SUCCEEDED` et `PARTIAL` produisent
un candidat ; `REFUSED` et `INSUFFICIENT_EVIDENCE` n'en produisent aucun. Cette
couche n'ajoute ni CAP-G03, ni correction, ni provider, ni validation, promotion,
persistance, retry ou wiring runtime.

La couche 12.8-E ajoute le chemin CAP-G03 explicite a partir de C-11 et d'une
cible versionnee deja resolue. Le meme `GenerationPort` produit un resultat
CORRECT dont le control block ferme est revalide avant construction d'une
nouvelle candidate C-08 et du `CorrectionResult` existant. La cible n'est jamais
chargee ou mutee ; aucune boucle locale, review, validation, promotion,
persistance, provider concret ou integration runtime n'est introduite.

La couche 12.8-F ajoute un guard pur obligatoire avant matérialisation G01/G02/G03.
Il revalide Prepared et résultat, contrôle uniquement la présence de grounding
déclaré et une structure bornée, puis signale des patterns de contenu FR/EN sans
conserver le texte ni suivre d'URL. Son assessment recomputable bloque les
dispositions repair/abstain/reject et ne propose qu'un repair non exécutable. Il
n'importe pas AG-02, n'établit aucun SOURCE_MATCH et n'ajoute ni provider, I/O,
review, validation, promotion, persistance, retry ou wiring runtime/orchestration.
