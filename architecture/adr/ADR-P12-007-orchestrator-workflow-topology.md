# ADR P12-007 - Catalogue canonique des topologies de workflow

## Statut

Accepté.

## Contexte

La Phase 12.6-B doit donner une représentation technique unique aux douze
topologies WF-0 à WF-11 sans anticiper leur sélection ou leur compilation. La
taxonomie finale vient de Phase 11.7 consolidée en 11.19 ; la table de scénarios
11.17 est legacy et ne peut pas renommer WF-3 à WF-11.

Le runtime déterministe de Phase 12.5 possède déjà `Plan`, `StepSpec`, la
validation DAG, le scheduler, l'exécution par Protocols et la révision. Le
nouveau catalogue ne doit modifier aucune de ces frontières ni devenir une
seconde autorité de permission ou d'exécution.

## Décision

`backend/agent_runtime/orchestration/workflows/` porte un modèle immutable
composé d'un `WorkflowKind` fermé, d'un vocabulaire de responsabilités, de trois
profils structuraux, de contraintes d'ordre acycliques et d'un descriptor de
topologie. `WorkflowCatalog` contient exactement les douze descriptors baseline
et fournit seulement `get`, `contains` et `all`.

Une responsabilité topologique n'est ni une capability, ni un step, ni un
executor, ni un use case. Son descriptor d'ownership associe éventuellement
AG-02, AG-03 ou AG-04 et des classes de capability admissibles, à titre
strictement descriptif. Il n'accorde aucun droit et ne remplace ni
`AccessMatrix`, ni `PermissionScope`.

AG-01 coordonne implicitement chaque topologie au-dessus du catalogue. Il n'est
pas ajouté à `WorkflowResponsibility` et ne devient pas `ExecutorKind.AG_01`.
Aucun orchestrateur/coordinator concret n'est créé dans ce lot.

WF-7 reste un graphe acyclique CORRECTION vers REVIEW. La répétition bornée
utilisera de nouvelles étapes et une nouvelle version de plan avec
`PlanRevisionEngine` dans les phases 12.6-E/F. WF-8 et WF-9 expriment un minimum
de deux branches, sans fixer la cardinalité réelle, et exigent un join commun.
WF-10 est un overlay de gate humaine composable avec une topologie de base.
WF-11 reste à la frontière Application et exige validation, gate policy puis
promotion, conformément au statut `REQUEST_GATE` de CAP-A02.

Le catalogue ne sélectionne aucun workflow et ne construit aucun `Plan` ou
`StepSpec`. La sélection est réservée à 12.6-C et la compilation à 12.6-D. Si
une topologie plus simple conserve la sémantique, les garanties et les gates,
elle devra être préférée par la sélection future.

## Conséquences

- les douze identifiants et leurs invariants possèdent une source technique
  unique et testable ;
- aucun moteur par workflow, provider, LLM, RAG, HTTP, ORM ou SQL n'est requis ;
- la cardinalité parallèle réelle et la composition des gates restent différées ;
- les agents concrets restent 12.7-12.9, le routing et les gates 12.10, et le
  recovery 12.11 ;
- `Plan.workflow_kind` demeure un `str`, compatible ultérieurement avec le
  `StrEnum` sans mutation de son contrat.
