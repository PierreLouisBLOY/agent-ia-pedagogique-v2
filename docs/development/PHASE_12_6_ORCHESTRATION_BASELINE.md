# Baseline de clôture Phase 12.6 — Orchestration déterministe

## Statut et lignée

La Phase 12.6 est `CLOSED` sur la branche
`phase12/12-6-orchestrator-workflows`. Tous les lots sont fermés :

| Lot | Objet | Commit |
| --- | --- | --- |
| 12.6-B | Catalogue des topologies | `3938b26c6d49db5bbcfe11a53d15bf401e8d220c` |
| 12.6-C | Sélection déterministe | `e016ecc097ea88ef741bb0dc97085d8b9f692403` |
| 12.6-D | Compilation en Plan canonique | `333c6c665eb166ecc42be428b8d87380607d88b8` |
| 12.6-E | Coordination AG-01 | `b71dafedcacfc3e27a5e8ef514da3d84bc973d05` |
| 12.6-F | Scénarios, fitness et clôture | commit portant ce document, parent 12.6-E |

Le baseline antérieur et `main/origin/main` restent
`668034fc1d04e4f0b747c8d8b2221d4fdfce39b9`. Aucun lot 12.6 n'a modifié
`backend/agent_runtime/runtime/**`, les modules métier, les adapters ou
l'infrastructure.

## Catalogue WF-0 à WF-11

| Workflow | Topologie canonique | Propriété essentielle |
| --- | --- | --- |
| WF-0 | Application/direct | une ou plusieurs actions Application séquentielles |
| WF-1 | Evidence | AG-02 seul |
| WF-2 | Génération/transformation | AG-03, validation déterministe optionnelle |
| WF-3 | Review indépendante | AG-04 seul |
| WF-4 | Evidence puis génération | AG-02 → AG-03, validation optionnelle |
| WF-5 | Génération puis review | AG-03 → validation optionnelle → AG-04 |
| WF-6 | Evidence, génération, validation, review | AG-02 → AG-03 → Application → AG-04 |
| WF-7 | Correction/re-review bornée | AG-03 CAP-G03 puis AG-04 optionnel ; répétition par nouvelle version |
| WF-8 | Fanout evidence | N AG-02 indépendants → JOIN CAP-O04 |
| WF-9 | Fanout variantes | N AG-03 → JOIN CAP-O04 → DECISION Runtime |
| WF-10 | Overlay gate humaine | overlay uniquement, jamais stage autonome |
| WF-11 | Validation et promotion | Application CAP-A01 → gate CAP-O05 → Application CAP-A02 |

`WorkflowKind` demeure un enum fermé décrivant ce catalogue.
`Plan.workflow_kind` demeure une chaîne opaque capable de conserver une
composition telle que `WF-8+WF-6|overlay:WF-10` sans étendre l'enum.

## Responsabilités et autorités

| Responsabilité | Owner | Classe(s) autorisée(s) |
| --- | --- | --- |
| DIRECT_APPLICATION | Application | READ, APPLICATION_ACTION |
| EVIDENCE | AG-02 | EVIDENCE |
| GENERATE_TRANSFORM | AG-03 | GENERATE_TRANSFORM |
| REVIEW | AG-04 | REVIEW |
| DETERMINISTIC_VALIDATION | Application | APPLICATION_ACTION |
| CORRECTION | AG-03 | GENERATE_TRANSFORM |
| EVIDENCE_JOIN | Runtime | ORCHESTRATION |
| VARIANT_GENERATION | AG-03 | GENERATE_TRANSFORM |
| VARIANT_JOIN | Runtime | ORCHESTRATION |
| VARIANT_SELECTION | Runtime | ORCHESTRATION |
| GATE | Runtime | ORCHESTRATION |
| PROMOTION | Application | APPLICATION_ACTION |

Le registre contient exactement AG-01 à AG-04. AG-01 orchestre mais n'est pas
un `ExecutorKind`. AG-02 reste limité à E*, AG-03 à G* et AG-04 à V*. Les actions
Application ne sont jamais transformées en exécution agent. Les métadonnées de
workflow n'accordent aucune permission ; le compiler conserve uniquement une
référence opaque `permission_scope_ref` pour les steps exécutables.

## Chaîne déterministe

La chaîne canonique est :

`WorkflowCatalog → WorkflowSelector → PlanCompiler → runtime 12.5 → OrchestrationCoordinator`.

- le catalogue décrit les topologies et leurs contraintes ;
- le selector transforme des exigences explicites en chemin minimal ;
- le compiler transforme la sélection et des bindings caller-supplied en
  `Plan/StepSpec`, puis appelle `PlanValidator` ;
- le runtime planifie et exécute un seul cycle borné avec des ports injectés ;
- le coordinateur supervise l'`ExecutionCycleResult` sans lancer de nouvel
  effet.

À entrées identiques, selector et compiler produisent les mêmes décisions,
l'ordre des steps, dépendances, kinds, executors, capabilities et groupes
parallèles. Aucun random ni temps système implicite n'intervient.

## Gates WF-10 et WF-11

WF-10 est un overlay humain distinct. Ses anchors canoniques peuvent placer une
gate avant le premier stage, après l'evidence — y compris après le JOIN WF-8 —,
après review ou avant la séquence de promotion. Le guard pré-launch peut arrêter
le cycle en `WAITING_GATE`; le runner de la gate et les steps aval ne sont alors
pas appelés. AG-01 ne fabrique et ne consomme aucune `GateDecision`.

WF-11 contient sa propre gate policy obligatoire entre CAP-A01 et CAP-A02. La
gate est un ancêtre direct de la promotion. Une gate humaine WF-10 et la gate
policy WF-11 restent deux steps distincts même lorsqu'elles utilisent toutes
deux CAP-O05. Le routing et la reprise après décision restent différés à 12.10.

## Fanout WF-8 et WF-9

WF-8 et WF-9 exigent au moins deux branches, des `branch_index` contigus et un
`parallel_group` commun. Un JOIN CAP-O04 dépend de toutes les branches. WF-9
ajoute ensuite un nœud DECISION Runtime sans capability.

La limite canonique `max_parallel_steps=4` reste détenue par le scheduler 12.5.
Les scénarios N=5 prouvent un lancement 4+1 sur des cycles explicitement demandés
par le test. Aucune boucle automatique n'est ajoutée. Dans WF-8+WF-4 et
WF-8+WF-6, le JOIN satisfait l'evidence de la continuation : aucun AG-02
supplémentaire n'est créé.

## WF-7 et révision de Plan

WF-7 est un DAG correction puis re-review optionnelle, jamais une boucle. Un
second passage correction/re-review est un replacement `plan_version=current+1`
fourni à `PlanRevisionEngine`. Le moteur existant reste seul propriétaire de :

- la limite de six versions ;
- l'identité run/plan/workflow et l'absence de goal drift ;
- la validation statique ;
- le refus d'une modification lorsqu'un step est `RUNNING` ;
- la réutilisation des steps `SUCCEEDED` ;
- le reset `PENDING` des autres steps avec conservation de `attempt_count` ;
- le refus no-progress et la détection de cycle structurel.

Un `PlanHistory` conserve un seul `workflow_kind`. Il n'existe aucun reselect
automatique au cours du même run.

## Coordination et completion

Pour un run non terminal, la priorité fail-closed est :

1. reconciliation ;
2. attente gate ;
3. replan ;
4. retry demandé ;
5. décision sur résultat partial ;
6. attente de condition ;
7. continuation ou completion.

La reconciliation domine tout replay lorsque l'effet est inconnu. Un retry
demandé ne modifie ni snapshot ni attempt et ne rappelle aucun runner. Un
partial produit `REVIEW_PARTIAL`, jamais une promotion ou un succès implicite.

La completion globale n'est évaluée qu'à quiescence, sans step `RUNNING`,
`READY` ou `PENDING` et sans directive prioritaire. Le
`WorkflowCompletionEvaluator` reste un Protocol sans implémentation production.
Le fake de scénario est appelé exactement une fois et peut décider SUCCEEDED,
PARTIAL ou REPLAN_REQUIRED. Des steps techniquement terminaux ne suffisent donc
jamais à eux seuls à déclarer le workflow réussi.

## Audit de rationalisation

Résultat : `NO_SAFE_CONSOLIDATION_REQUIRED`.

L'audit cumulatif n'a trouvé ni classe concurrente, import circulaire, dead code
identifiable, helper production dupliqué, pseudo-framework, ni déplacement de
logique entre orchestration et runtime. Les séparations suivantes sont
intentionnelles et doivent être conservées :

- `WorkflowKind` et `Plan.workflow_kind` opaque ;
- `WorkflowSelectionDecision` et le nœud runtime DECISION ;
- `ExecutionDirectiveCode` et `CoordinationAction` ;
- `WorkflowCompletionDecision` et `GateDecision` ;
- `PlanRevisionEngine` et `WorkflowSelector` ;
- gate humaine WF-10 et gate policy WF-11 ;
- catalogue, selector, compiler et coordinator.

Ces types portent des responsabilités, temporalités et autorités différentes.
Les fusionner réduirait les contrôles fail-closed et recréerait une autorité
implicite.

## Findings historiques

Tous les findings antérieurs nécessaires à cette baseline sont fermés :

- 12.5-B — permission scope manquant, join strategy et required gate : `CLOSED` ;
- 12.5-C — dépassement de la hard-limit parallèle : `CLOSED` ;
- 12.5-D — contrat runner et liaison error/attempt : `CLOSED` ;
- 12.5 — préservation des snapshots terminaux : `CLOSED`.

Les scénarios 12.6-F n'ont révélé aucun nouveau finding de production.

## Périmètre différé

- 12.7 : agent AG-02 réel ;
- 12.8 : agent AG-03 réel ;
- 12.9 : agent AG-04 réel ;
- 12.10 : routing concret, gates et consommation des décisions ;
- 12.11 : retry, recovery et reconciliation opérationnels.

Aucun provider, choix de modèle, LLM/RAG, HTTP, SQL/ORM, handler concret,
GateEngine, retry engine, recovery store, BudgetState ou observabilité 12.13
n'appartient à cette baseline.

## Invariants à ne pas casser

1. Les phases 6 et 11 restent normatives et aucune autorité métier n'est acquise
   par un agent ou une métadonnée de workflow.
2. Génération, validation, évaluation et promotion restent distinctes.
3. CAP-A02 reste une action Application derrière une gate obligatoire.
4. Unknown effect exige reconciliation avant replay.
5. PermissionDenied et GateRejected ne sont jamais contournés.
6. Le runtime n'importe pas l'orchestration et l'orchestration ne crée aucune
   boucle d'exécution.
7. `PlanRevisionEngine` reste l'unique moteur technique de révision.
8. `WorkflowCompletionEvaluator` reste une frontière injectée tant qu'aucun
   evaluator canonique des success criteria n'est décidé.
9. Les dépendances runtime externes restent vides.
