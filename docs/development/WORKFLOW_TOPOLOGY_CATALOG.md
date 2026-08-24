# Catalogue des topologies de workflow

## Portée et autorité

Ce catalogue matérialise la taxonomie finale de Phase 11.7, consolidée en Phase
11.19. La table de scénarios numérotés de Phase 11.17 est legacy et incohérente
pour WF-3 à WF-11 : elle ne constitue pas une autorité de renommage.

Les douze entrées sont des topologies déclaratives immutables et
provider-neutral. Elles ne sont ni douze moteurs, ni des plans, ni des routes
concrètes. `WorkflowResponsibility` décrit une responsabilité topologique ; ce
vocabulaire reste distinct de `CapabilityId`, `CapabilityClass`, `StepKind`,
`ExecutorKind`, `AgentId` et des use cases Application.

AG-01 pilote implicitement toutes les topologies. Il n'apparaît pas comme une
responsabilité agentique et ne devient pas un `ExecutorKind`. Sa coordination se
placera au-dessus du catalogue en 12.6-C/D/E.

## Taxonomie canonique

| Kind | Nom | Responsabilités requises | Optionnelles | Profil |
| --- | --- | --- | --- | --- |
| WF-0 | Application/direct | DIRECT_APPLICATION | — | frontière Application |
| WF-1 | Evidence | EVIDENCE | — | séquentiel |
| WF-2 | Generation/Transformation | GENERATE_TRANSFORM | DETERMINISTIC_VALIDATION | séquentiel |
| WF-3 | Independent review | REVIEW | — | review indépendante |
| WF-4 | Evidence then generation | EVIDENCE, GENERATE_TRANSFORM | DETERMINISTIC_VALIDATION | séquentiel |
| WF-5 | Generation then review | GENERATE_TRANSFORM, REVIEW | DETERMINISTIC_VALIDATION | séquentiel |
| WF-6 | Evidence generation validation review | EVIDENCE, GENERATE_TRANSFORM, DETERMINISTIC_VALIDATION, REVIEW | — | séquentiel |
| WF-7 | Bounded correction/re-review | CORRECTION | REVIEW | révision bornée/versionnée |
| WF-8 | Parallel evidence | EVIDENCE, EVIDENCE_JOIN | — | fan-out evidence, N >= 2 |
| WF-9 | Parallel variants and selection | VARIANT_GENERATION, VARIANT_JOIN, VARIANT_SELECTION | — | fan-out variantes, N >= 2 |
| WF-10 | Human-gated workflow | GATE | — | overlay gate humaine |
| WF-11 | Application validation and promotion | DETERMINISTIC_VALIDATION, GATE, PROMOTION | — | frontière Application, gate policy |

Une contrainte d'ordre qui implique une responsabilité optionnelle s'applique
uniquement lorsque cette responsabilité est matérialisée par une phase future.

## Décisions structurantes

WF-7 ne contient aucun cycle. Son descriptor exprime seulement CORRECTION puis
REVIEW optionnelle. Une répétition correction/re-review sera matérialisée par de
nouvelles étapes et une nouvelle `plan_version`, via `PlanRevisionEngine` et les
travaux 12.6-E/F. `StepSpec.depends_on` demeure acyclique.

WF-8 et WF-9 portent une cardinalité minimale, pas deux branches figées. Le futur
compilateur acceptera N branches indépendantes, avec N >= 2, puis construira un
JOIN commun. WF-8 joint les preuves ; WF-9 joint les variantes avant la sélection.

WF-10 est un profil composable `overlay=True`. En 12.6-C/D, une gate humaine
pourra envelopper une topologie de base. Ce profil n'est ni un moteur séparé ni
une décision LLM.

WF-11 impose la séquence validation déterministe, gate policy, promotion via
l'Application. Cette frontière reflète CAP-A02 `REQUEST_GATE` dans la baseline
12.4. Le catalogue ne réalise ni la gate ni la promotion et n'accorde aucune
permission.

## Ownership descriptif

| Responsabilité | Owner | Classes de capability admissibles |
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

`owner_agent=None` désigne ici une responsabilité non détenue par un agent
spécialiste. Ces métadonnées ne sont ni une permission, ni une route concrète et
ne remplacent jamais `AccessMatrix` ou `PermissionScope`.

## Minimalité et phases différées

Le catalogue ne contient aucun score, parseur d'intention, sélecteur, mapping de
demande ou `PlanCompiler`. Si une topologie plus simple conserve la même
sémantique, les mêmes garanties et les mêmes gates, elle devra être préférée par
12.6-C.

La sélection est différée à 12.6-C et la compilation en `Plan`/`StepSpec` à
12.6-D. Les agents réels relèvent de 12.7 à 12.9, le routing et les gates
concrets de 12.10, et le recovery de 12.11.
