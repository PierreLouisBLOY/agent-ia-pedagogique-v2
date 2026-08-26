# ADR-P12-028 — Frontière de routage des use cases Application

## Statut

Accepté — Phase 12.10-E.

## Contexte

Les contrats `UseCaseRequest` (C-12) et `UseCaseResult` (C-13), le catalogue des
capabilities et `CapabilityAuthorizationPolicy` existaient déjà. Il manquait une
frontière explicite entre une étape `USE_CASE` du runtime agent et un port inbound
Application. Cette frontière ne doit ni choisir un handler depuis des données agent,
ni accorder une autorisation métier, ni contourner la gate de CAP-A02.

Le routage d’un outil et celui d’un use case ont des sémantiques d’autorité
différentes. Un outil exige `ALLOW`. Une capability dont la route est `APPLICATION`
est transmissible uniquement lorsque la politique retourne `REQUEST` : cette
disposition autorise le handoff, pas l’effet métier.

## Décision

Un package autonome `backend.agent_runtime.application_routing` porte :

- `UseCaseDescriptor` et un `UseCaseRegistry` statique, immutable et exact-match ;
- six identifiants inbound correspondant exactement à CAP-R01/R02/R03/A01/A02/A03 ;
- `ApplicationInboundPort` ainsi que des bindings injectés séparément des metadata ;
- `UseCaseRoutingContext`, dont le `PermissionScope` résolu reste fourni par le
  caller trusted et lié au `permission_scope_ref` du `StepSpec` ;
- `UseCaseRouter`, qui valide l’étape et les identités, compose la policy canonique,
  exige `REQUEST`, résout un binding exact, invoque au plus une fois puis reconstruit
  et revalide le résultat canonique.

Le mapping d’opération est fermé et reprend le vocabulaire déjà consacré par les
tests de politique : `READ` pour CAP-R01/R02/R03 et `REQUEST` pour
CAP-A01/A02/A03. Aucun alias `validate`, `promote` ou `export` n’est ajouté au
vocabulaire de permission.

CAP-A02 reste `REQUEST_GATE` sans `PolicyFacts.matrix_gate_satisfied`. Le router ne
crée et ne vérifie aucune décision de gate. Un fait trusted fourni ultérieurement par
F/G peut amener la policy à `REQUEST`, sans transformer cette disposition en
autorisation de promotion.

CAP-A02 et CAP-A03 exigent conservativement une clé d’idempotence. E ne stocke pas
la clé et n’implémente ni ledger, replay, retry, recovery ni reconciliation ; ces
responsabilités restent hors de ce lot et, pour le ledger/replay, relèvent de 12.11.

Les payloads et `requested_effect` sont des données. Un filtre récursif refuse les
clés de contrôle capables de smuggler capability, permission, gate, handler,
provider ou executor. Les mots métier génériques comme `status` et `validation`
restent autorisés.

## Conséquences

- L’Application conserve seule l’autorité du résultat métier et de ses effets.
- Les erreurs Domain/Application, `ApplicationFailure`, validations, warnings,
  side effects et références restent portés par `ApplicationOutcome` sans remapping.
- Une route inconnue, non bindée, incohérente ou non `REQUEST` échoue fermée avant
  l’inbound ; un résultat forgé échoue fermé après exactement un appel.
- Aucun use case métier artificiel, import dynamique, provider, réseau, filesystem,
  subprocess, `GateEngine`, `StepRunner`, scheduler ou intégration runtime n’est
  introduit.
- `ToolRegistry`, `ToolExecutorBindings` et `ToolRouter` restent distincts. Une
  abstraction générique masquerait la différence `ALLOW`/`REQUEST` et n’est donc
  pas sûre.

## Alternatives écartées

- Placer un handler ou un import path dans le descriptor : autorité pilotable par
  metadata et couplage à l’implémentation.
- Réutiliser `ToolRouter` : sémantique de disposition incorrecte et risque de bypass
  des frontières Application/sandbox.
- Créer une gate locale ou traiter `REQUEST_GATE` comme routable : extension de
  périmètre et bypass de la phase F.
- Ajouter des opérations de permission ad hoc : duplication du vocabulaire
  canonique existant.

## Rationalisation

`NO_SAFE_CONSOLIDATION_REQUIRED`.
