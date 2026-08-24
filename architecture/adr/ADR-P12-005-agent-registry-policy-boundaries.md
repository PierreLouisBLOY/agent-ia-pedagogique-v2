# ADR P12-005 - Frontieres des registries et de la policy runtime

## Statut

Accepte.

## Contexte

La Phase 12.4-B doit materialiser les catalogues statiques des agents et des
capabilities, la ceiling policy issue de la matrice de Phase 11.10 et les
garde-fous techniques consolides en Phase 11.19. Ces structures doivent rester
provider-neutral et ne pas acquerir l'autorite des modules metier.

## Decision

`AgentRegistry` et `CapabilityRegistry` sont des catalogues immuables du runtime.
Ils decrivent les quatre agents canoniques, les 24 capabilities et leurs routes
logiques. Ils ne sont ni une source metier, ni un catalogue de tools ou de use
cases concrets. Une route `APPLICATION` indique seulement une frontiere logique ;
elle ne stocke aucun handler.

`AccessMatrix` materialise exhaustivement les 96 cellules agent-capability. Elle
est une ceiling policy statique. Elle ne prend aucune decision d'autorisation
effective : l'evaluation isolee de `PermissionScope` appartient a 12.4-C et la
combinaison finale a 12.4-D. En particulier, `CONDITIONAL` ne vaut jamais
implicitement `ALLOW`.

`AgentRuntimePolicy` porte des garde-fous techniques configurables de volumes,
ratios et deadlines. Ces valeurs ne sont pas des regles Domain. `RuntimeMode` et
`AutonomyLevel` ne modifient jamais les permissions, et aucune consommation de
budget, boucle de retry ou decision de stop n'est executee dans ce lot.

La policy composite de `ToolCall`, le routing concret des tools, le sandbox et
les gates d'execution restent differes a la Phase 12.10. Aucun scheduler, provider,
SDK, HTTP, ORM, SQL ou LLM reel n'est introduit.

## Consequences

- les catalogues sont inspectables et fail-fast sans devenir une autorite metier ;
- chaque cellule de la matrice est explicite, une absence est une erreur de
  configuration et non un `DENY` silencieux ;
- les limites runtime peuvent etre configurees sans couplage a un fournisseur ;
- l'evaluation des permissions et toute execution restent hors de 12.4-B ;
- des fitness functions protegent les cardinalites et les frontieres de dependance.

## Extension Phase 12.4-C

La decision de frontiere reste inchangee. C materialise desormais un evaluator
pur de `PermissionScope`, ses relations conservatrices de narrowing et une policy
de delegation AG-01 vers AG-02/03/04. Les facts de revocation et de gates
satisfaites sont fournis explicitement par une couche runtime/policy de confiance.

Cet evaluator ne consulte pas `AccessMatrix`. La combinaison entre ceiling matrix
et scope, y compris le controle d'ownership du target, reste reservee a 12.4-D.
Les budgets sont seulement compares comme enveloppes ; `BudgetState`, consommation,
gate engine, scheduler, routing concret et policy composite de `ToolCall` restent
hors de C.

La revocation du scope parent est opposable a toute nouvelle delegation via un
fait bool explicite et trusted. Elle reste distincte de l'inactivite temporelle.
Ce choix ne cree ni registry mutable, ni persistance, ni propagation automatique
de revocation : ces responsabilites runtime restent hors de 12.4-C.
