# Baseline de policy Phase 12.4

## Statut et revision

Statut : **Phase 12.4 implementation baseline**. Ce document consolide les
invariants livres par B, C, D et leur audit de cloture E ; il ne remplace pas les
documents specialises.

- baseline d'entree de l'audit E : `9941aa7657da32c5155e586bfeff8b6802a42aad` ;
- baseline de sortie attendue : le commit contenant ce document, portant le
  message `test: close phase 12.4 policy fitness` sur la branche
  `phase12/12-4-registries-permissions-policies` ;
- cette revision reste une branche de travail jusqu'a audit independant et merge
  explicite ulterieur.

## Catalogues et ceiling statique

La baseline expose exactement quatre agents : AG-01 orchestrateur, AG-02
Evidence/Retrieval, AG-03 Generator/Transformer et AG-04 Reviewer/Critic. Il
n'existe ni AG-05, ni agent `Validator` distinct. Les catalogues restent
immutables et descriptifs. L'expression historique « Boss Agent » designe le role
d'AG-01 et non un agent supplementaire.

Le `CapabilityRegistry` contient 24 capabilities :

| Famille | Nombre | Route | Owner | Risque |
| --- | ---: | --- | --- | --- |
| CAP-R* | 3 | APPLICATION | aucun | R0 |
| CAP-E* | 3 | AGENT | AG-02 | R0 |
| CAP-G* | 3 | AGENT | AG-03 | R1 |
| CAP-V* | 2 | AGENT | AG-04 | R1 |
| CAP-A01/A03 | 2 | APPLICATION | aucun | R3 |
| CAP-A02 | 1 | APPLICATION | aucun | R4 |
| CAP-T01/T04 | 2 | UTILITY | aucun | R0 |
| CAP-T02/T03 | 2 | UTILITY | aucun | R2 |
| CAP-O* | 6 | RUNTIME | aucun | R0 |

`AccessMatrix` materialise les 96 cellules du produit 4 x 24. Elle est une
ceiling statique, pas un grant dynamique. Une cellule absente est une erreur de
configuration. AG-01 delegue CAP-E/G/V vers leur owner et ne les execute jamais
directement. Les routes Application ne portent aucun `ALLOW` direct.

## Garde-fous runtime

`AgentRuntimePolicy` regroupe uniquement des limites techniques configurables :
steps, plans, parallelisme, profondeur de delegation, tool calls, retries,
reviews, rounds d'evidence, ratios de contexte et deadlines. Elle ne derive
aucune permission de `RuntimeMode` ou `AutonomyLevel`, ne consomme aucun budget et
n'implemente ni scheduler ni etat de run/step.

## PermissionScope et evaluation

`PermissionScope` reste un contrat data-only. `PermissionScopeEvaluator` applique
un ordre fail-closed : configuration, principal, revocation, temps, deny,
capability, operation, ressources, contraintes, gates, budget, puis `ALLOW`.

La grammaire deny v1 est fermee aux cles `capability_id`, `operation`,
`resource_scope` et `reason_code`. Une cle ou une operation inconnue invalide le
scope. Le premier deny correspondant prevaut sur les grants.

Le narrowing des ressources est inclusif : le check ou l'enfant peut selectionner
moins de ressources que le grant. Le narrowing des contraintes est conservateur :
toute contrainte parent doit rester presente et l'enfant peut la renforcer. Ces
relations ne donnent aucune semantique implicite aux noms de champs.

Le budget est une enveloppe de limites. La Phase 12.4 compare seulement les
plafonds et deadlines ; elle ne definit ni consommation, reservation, remaining
budget, ni `BudgetState`.

La revocation est un fait trusted distinct de la temporalite. `REVOKED` reste
distinct de `EXPIRED`; en delegation, `PARENT_REVOKED` reste distinct de
`PARENT_INACTIVE`.

## Narrowing et delegation

`DelegationScopePolicy` est le filtre scope-only de C. Elle autorise uniquement
AG-01 vers AG-02/03/04, exige `delegable=True`, un enfant narrower/equal, conserve
denies et gates, refuse R3/R4 directs et interdit la redelegation des
specialistes. Elle ne consulte pas `AccessMatrix`.

La policy finale D ajoute la ceiling et l'ownership : la capability doit etre
`DELEGATE` pour AG-01, le target doit etre l'owner canonique avec une rule
`ALLOW`, et la capability du mandat doit appartenir au grant parent **ET** au
grant enfant. La revocation et le narrowing restent ensuite composes par C.

## Decision finale

L'autorisation finale est l'intersection :

```text
AccessMatrix ceiling ∩ explicit PermissionScope grant
```

Elle n'est jamais l'union des permissions des agents. Les dispositions finales
sont `DENY`, `ALLOW`, `REQUEST`, `DELEGATE`, `REQUEST_GATE` et
`CONDITION_REQUIRED`.

- `DENY` prevaut et ne propose aucun fallback ou reroutage ;
- `REQUEST` n'est pas un `ALLOW` et n'appelle pas Application ;
- `DELEGATE` n'est pas une execution par AG-01 ;
- CAP-A02 exige toujours la gate matrix ; une gate satisfaite produit seulement
  `REQUEST` vers Application ;
- CAP-T02/T03 utilisent la condition canonique
  `request_or_allow_by_workflow`, resolue uniquement par un fact workflow trusted ;
- aucun fact de permission n'est derive d'un agent, document ou LLM.

Le mapping d'autorite logique est :

| Classe/capability | Autorite |
| --- | --- |
| ORCHESTRATION | AGENT_RUNTIME |
| EVIDENCE / GENERATE_TRANSFORM / REVIEW | AGENT_SPECIALIST |
| READ | APPLICATION |
| CAP-A01 / CAP-A02 | APPLICATION_DOMAIN |
| CAP-A03 | APPLICATION |
| TECHNICAL_UTILITY | TECHNICAL_UTILITY |

Ce mapping ne reference aucun handler concret.

## Rationalisation de cloture

La condition `request_or_allow_by_workflow` a une seule source Python publique,
provider-neutral, dans `registry/access_matrix.py`. La matrice, la validation de
configuration et la decision finale reutilisent cette constante.

Les vocabulaires ressemblants restent volontairement separes : `AccessMode`
decrit la ceiling, `ScopeEvaluationCode` la cause d'une evaluation de grant, et
`PolicyDisposition`/`PolicyDecisionCode` la decision composee. Les fusionner
melangerait des responsabilites distinctes. De meme, `DelegationScopePolicy`
reste scope-only tandis que `CapabilityAuthorizationPolicy` combine matrix,
owner et scope.

## Invariants de securite et frontieres

- exactement 4 agents, 24 capabilities et 96 rules ;
- AG-01 est le seul orchestrateur et ne possede pas l'union des specialistes ;
- tout mode positif reste soumis au scope explicite ;
- matrix `DENY` et scope deny restent terminaux ;
- owner et target sont verifies avant toute delegation ;
- un mandat ne peut executer une capability absente de ses grants ;
- PermissionScope reste data-only et son evaluator reste independant de matrix ;
- aucune decision deny ne contient fallback ou alternative agent ;
- aucune donnee agent/document ne modifie registry, permission ou autorite ;
- aucune dependance runtime tierce n'est ajoutee.

La Phase 12.5 porte le scheduler et les etats de run/step. La Phase 12.10 porte le
routing concret tools/use cases, `ToolRegistry`, `ToolCallPolicy`, gates
d'execution et sandbox. Providers, LLM, RAG, HTTP, ORM et SQL restent hors de la
Phase 12.4.
