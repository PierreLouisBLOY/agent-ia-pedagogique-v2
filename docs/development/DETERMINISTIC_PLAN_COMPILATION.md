# Compilation déterministe des sélections en plans

## Frontière entre sélection et compilation

`WorkflowSelector` choisit des topologies à partir d'exigences explicites.
`PlanCompiler` ne refait jamais ce choix : il reçoit la décision 12.6-C, les
métadonnées globales du plan et des bindings concrets fournis par le caller.

Le caller fournit la sémantique : capability métier, objectif précis, références
d'entrée, output contract, critères de succès, budgets et référence opaque de
scope. Le compiler fournit uniquement la topologie : `StepKind`, `ExecutorRef`,
`depends_on`, `parallel_group`, capacités non ambiguës des nœuds de contrôle et
composition des stages.

Il ne résout aucun scope, ne crée aucune permission, ne route vers aucun handler
ou provider et n'exécute aucun step.

## Modèle de binding

`PlanStepBinding` relie une responsabilité d'un stage à un `step_id`, un objectif
et ses données caller-supplied. Il ne contient ni kind, ni executor, ni
dépendance, ni agent, ni statut. `HumanGateBinding` fournit séparément le contenu
d'une gate humaine et exige un `HumanGateAnchor` explicite.

`PlanCompilationRequest` porte la sélection, les métadonnées immutables du plan,
les bindings, les `gate_refs` opaques et les budgets déclaratifs. Une sélection
`waiting_human` est refusée avant construction : une ambiguïté non clarifiée ne
produit aucun plan spéculatif.

## Dérivation canonique

| Responsabilité | StepKind | Executor | Capability |
| --- | --- | --- | --- |
| DIRECT_APPLICATION | USE_CASE | APPLICATION | caller, READ/APPLICATION_ACTION |
| EVIDENCE | AGENT | AG-02 | caller, classe EVIDENCE, owner AG-02 |
| GENERATE_TRANSFORM | AGENT | AG-03 | caller, classe GENERATE_TRANSFORM |
| REVIEW | AGENT | AG-04 | caller, classe REVIEW |
| DETERMINISTIC_VALIDATION | USE_CASE | APPLICATION | CAP-A01 exact |
| CORRECTION | AGENT | AG-03 | CAP-G03 exact |
| EVIDENCE_JOIN | JOIN | RUNTIME | CAP-O04 dérivée |
| VARIANT_GENERATION | AGENT | AG-03 | caller, classe GENERATE_TRANSFORM |
| VARIANT_JOIN | JOIN | RUNTIME | CAP-O04 dérivée |
| VARIANT_SELECTION | DECISION | RUNTIME | aucune |
| GATE | GATE | RUNTIME | CAP-O05 dérivée |
| PROMOTION | USE_CASE | APPLICATION | CAP-A02 exact |

Les classes et owners sont contrôlés via `BASELINE_CAPABILITY_REGISTRY` et
`BASELINE_WORKFLOW_RESPONSIBILITY_DESCRIPTORS`, jamais par une troisième table
d'autorité. Les nœuds AGENT/USE_CASE/TOOL exigent une `permission_scope_ref` ;
JOIN/GATE/DECISION l'interdisent. Ces refs restent opaques et ne sont jamais
évaluées.

## Expansion des topologies

- WF-0 compile une ou plusieurs opérations Application explicites en chaîne.
- WF-1 compile une evidence AG-02.
- WF-2 compile génération, puis validation optionnelle.
- WF-3 compile une review indépendante AG-04.
- WF-4 compile evidence, génération, puis validation optionnelle.
- WF-5 compile génération, validation optionnelle, puis review.
- WF-6 compile evidence, génération, CAP-A01, puis review.
- WF-7 compile correction CAP-G03, puis review optionnelle, sans cycle.
- WF-8 compile N branches AG-02 indépendantes et un JOIN CAP-O04 commun.
- WF-9 compile N variantes AG-03, JOIN, puis DECISION de sélection.
- WF-10 n'est jamais un stage : il reste un overlay avec anchor explicite.
- WF-11 compile CAP-A01, gate policy CAP-O05, puis promotion CAP-A02.

Les fan-outs exigent des `branch_index` contigus à partir de zéro. Le compiler
ne divise pas les budgets : chaque sous-budget reste explicitement fourni par le
caller.

## Handoff WF-8 vers WF-4/WF-6

Dans `WF-8+WF-4` et `WF-8+WF-6`, le JOIN evidence satisfait la responsabilité
EVIDENCE de la continuation. Aucun binding EVIDENCE n'est attendu dans WF-4 ou
WF-6, aucun AG-02 supplémentaire n'est construit, et GENERATE_TRANSFORM dépend
directement du JOIN. WF-6 poursuit ensuite validation puis review.

Cette règle ne transfère aucune future `result_ref` dans `input_refs`. Le DAG
porte seulement l'ordre et le lineage ; le transfert effectif relève de 12.10 et
des agents spécialisés.

## Overlay WF-10

Les anchors sont fermés :

- `BEFORE_FIRST_STAGE` place la gate avant tous les roots initiaux ;
- `AFTER_EVIDENCE` la place après l'evidence pertinente, après le JOIN pour WF-8 ;
- `AFTER_REVIEW` la place après la dernière review, éventuellement en terminal ;
- `BEFORE_PROMOTION` la place avant l'entrée de WF-11.

La gate humaine WF-10 et la gate policy intrinsèque WF-11 restent deux steps
distincts. Aucun anchor implicite ou fallback n'existe.

## Identité descriptive et validation finale

Un stage unique sans overlay conserve `WF-N`. Une composition utilise `+`, par
exemple `WF-8+WF-6` ou `WF-9+WF-0+WF-3`. L'overlay est suffixé par
`|overlay:WF-10`. Cette chaîne reste opaque pour le runtime 12.5 et ne crée aucun
nouveau `WorkflowKind`.

Le compiler construit le `Plan` canonique puis appelle obligatoirement
`PlanValidator`. Un plan invalide n'est jamais retourné ; l'erreur publique ne
contient que les `PlanValidationCode` triés et dédupliqués.

Le Coordinator arrive en 12.6-E, les agents en 12.7-12.9, le routing et les gates
concrets en 12.10, et le recovery en 12.11.
