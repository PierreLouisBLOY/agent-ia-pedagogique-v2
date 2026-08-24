# ADR P12-009 - Compilation déterministe des sélections en plans

## Statut

Accepté.

## Contexte

Les Phases 12.6-B/C fournissent un catalogue canonique et une sélection
déterministe, tandis que 12.5 fournit `Plan`, `StepSpec` et `PlanValidator`. Il
manque une frontière qui matérialise une sélection en DAG sans inventer la
sémantique métier, acquérir une permission ou exécuter le plan.

## Décision

`backend/agent_runtime/orchestration/compilation/` contient un `PlanCompiler`
immutable. Le caller fournit des bindings explicites avec capability, objectif,
refs, contrats, critères et budgets. Le compiler dérive exclusivement les kinds,
executors, dépendances, groupes parallèles et capabilities de contrôle
canoniques.

La validation des capabilities réutilise le registry 12.4 et les descriptors
d'ownership 12.6-B. Les scopes restent des références opaques obligatoires pour
les steps exécutables et interdites pour les nœuds de contrôle. Aucun
`PermissionScope`, `AccessMatrix` ou handler n'est construit ou évalué.

Chaque stage est un petit DAG composé par ses roots et terminals. WF-8 et WF-9
créent N branches indépendantes avec indices contigus et JOIN explicite. Dans les
compositions WF-8 vers WF-4/WF-6, le JOIN satisfait l'evidence attendue par la
continuation : aucun second AG-02 n'est généré.

WF-10 reste un overlay et requiert un anchor explicite. Son insertion réécrit
uniquement la coupe concernée du DAG. Une gate humaine WF-10 ne fusionne pas avec
la gate policy de WF-11. Une décision `waiting_human` n'est jamais compilée.

`Plan.workflow_kind` conserve une représentation opaque stable : `+` compose les
stages et `|overlay:WF-10` décrit l'overlay. Cette représentation n'étend pas
`WorkflowKind`.

Après construction, `PlanValidator` est toujours appelé. Le compiler ne corrige
pas automatiquement un plan invalide et expose seulement les codes de validation
triés/dédupliqués.

## Conséquences

- le caller reste responsable de toute sémantique concrète ;
- le compiler reste pur, déterministe et provider-neutral ;
- aucun plan ambigu, binding absent ou capability incompatible n'est complété
  par spéculation ;
- aucun budget de branche n'est alloué ou divisé automatiquement ;
- l'exécution, les outputs réels et les gates restent hors de cette phase ;
- le Coordinator est différé à 12.6-E, les agents à 12.7-12.9, le routing et les
  gates à 12.10, et le recovery à 12.11.
