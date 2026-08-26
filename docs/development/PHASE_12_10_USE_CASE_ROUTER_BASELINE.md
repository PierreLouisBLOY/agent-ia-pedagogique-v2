# Phase 12.10-E — Baseline UseCaseRouter / frontière Application

## Périmètre livré

Cette baseline ajoute uniquement le routage fail-closed d’un `UseCaseRequest` vers
un port inbound Application injecté. Elle ne contient aucun handler métier, aucune
résolution repository, aucune gate, aucun runner de workflow et aucune intégration
runtime.

Le package canonique est `backend/agent_runtime/application_routing/` :

| Surface | Responsabilité |
|---|---|
| `UseCaseDescriptor` | Metadata statique sans handler, owner, route, risk ni provider |
| `UseCaseRegistry` | Catalogue exact-match validé contre `CapabilityRegistry` |
| `ApplicationInboundPort` | Invocation provider-neutral d’un `UseCaseRequest` |
| `UseCaseInboundBindings` | Association immutable et exacte ID → port injecté |
| `UseCaseRoutingContext` | `StepSpec`, scope ref, scope résolu et facts trusted |
| `UseCaseRouter` | Policy, handoff unique et revalidation de `UseCaseResult` |

## Registry baseline

| use_case_id | capability | opération | idempotence requise |
|---|---|---|---:|
| `application.read_canonical_resource` | CAP-R01 | `READ` | non |
| `application.read_production` | CAP-R02 | `READ` | non |
| `application.read_metadata_status` | CAP-R03 | `READ` | non |
| `application.run_deterministic_validation` | CAP-A01 | `REQUEST` | non |
| `application.request_promotion` | CAP-A02 | `REQUEST` | oui |
| `application.export_artifact` | CAP-A03 | `REQUEST` | oui |

Tous utilisent C-12 comme contrat de requête et C-13 comme contrat de résultat.
Le mapping d’opération est statique. `REQUEST` pour A01/A02/A03 réutilise la
sémantique déjà canonisée par les tests de `CapabilityAuthorizationPolicy` ; aucun
alias libre n’est créé.

Les exigences conservatrices d’idempotence sur A02/A03 protègent les effets
mutables possibles. E ne fournit aucun stockage, ledger, replay ou retry ; le
ledger/replay reste explicitement réservé à 12.11.

## Invariants de routage

Avant tout inbound call :

1. la requête et le contexte sont reconstruisibles avec les contrats canoniques ;
2. `step.kind` vaut `USE_CASE` et son executor vaut `APPLICATION` ;
3. le `permission_scope_ref` du contexte correspond exactement à celui du step ;
4. step, request et actor context conservent step ID et corrélation ;
5. l’acteur de la requête, l’`AgentId` appelant et le principal du scope coïncident ;
6. la capability du step est connue, de route `APPLICATION`, de classe `READ` ou
   `APPLICATION_ACTION`, et sans owner agent ;
7. le descriptor et le step portent exactement la même capability ;
8. idempotence et absence de metadata d’autorité dans `payload` et
   `requested_effect` sont vérifiées ;
9. `CapabilityAuthorizationPolicy` retourne exactement `REQUEST` pour la même
   capability et la route `APPLICATION` ;
10. un binding exact existe.

`DENY`, `ALLOW`, `DELEGATE`, `REQUEST_GATE` et `CONDITION_REQUIRED` ne sont jamais
routables. Contrairement au ToolRouter, `ALLOW` est une configuration incohérente à
cette frontière ; seul `REQUEST` autorise la transmission à l’Application.

## Gate CAP-A02

Sans fait trusted de gate, la policy retourne `REQUEST_GATE` et aucun port inbound
n’est appelé. Avec `PolicyFacts(matrix_gate_satisfied=True)` fourni par un caller
trusted, la policy peut retourner `REQUEST` et le handoff devient possible. Le
router ne construit aucune `GateDecision`, n’atteste aucune décision humaine et ne
considère jamais la promotion comme approuvée.

## Données et résultat

Les clés de contrôle suivantes, y compris sous forme camelCase et à profondeur
arbitraire, sont refusées dans `payload` et `requested_effect` : capability,
permission/scope, gate decision/approval, promotion approval, validated/approved,
handler/import path, provider/credentials, runtime override, executor et use-case
override. `status` et `validation` ne sont pas censurés.

Après l’unique appel inbound, le router vérifie les identités use case/run/step,
les corrélations du résultat et de l’outcome, le couple status/outcome, l’erreur et
ses refs, `result_ref`, les domain events et les références d’outcome. Il reconstruit
`ContractMeta`, `ErrorEnvelope`, `ApplicationOutcome` et `UseCaseResult`. Un succès
ne peut masquer ni business error, ni `ApplicationFailure`, ni `ErrorEnvelope`.
Une rejection ou failure Application reste une rejection ou failure Application.

## Frontières préservées

- Aucun accès direct aux modules métier, repositories, SQL, secrets ou filesystem.
- Aucun provider, réseau, subprocess, import dynamique, reflection ou plugin.
- Aucun fallback entre use cases et aucun retry.
- A03 reste un use case Application distinct de T02/T03 et du `ToolRouter`; il ne
  contourne pas le sandbox.
- A01 conserve son `validation_result` opaque : le router ne le réinterprète pas.
- R01/R02/R03 restent trois routes exactes sans fallback ni mutation locale.
- Aucun `GateEngine`, `StepRunner`, `PlanExecutor` ou scheduler n’est ajouté.

## Erreurs sûres

Les erreurs de routage ont des codes fermés et des raisons sans payload brut :
contexte invalide, use case inconnu/non bindé, mismatch step/executor/capability,
capability non Application, requête non routable, idempotence manquante, metadata
d’autorité interdite, échec inbound, mismatch d’identité résultat et résultat
invalide. Une exception du port est réduite à `INBOUND_FAILED` et n’est jamais
retentée.

## Validation attendue

Les cinq fichiers de tests E ciblés, la régression B–E, la suite globale, Ruff,
mypy sur `backend`, compileall et `git diff --check` doivent réussir réellement.
Les dépendances runtime de `pyproject.toml` restent `[]`.

## Rationalisation

`ToolRegistry`/`ToolExecutorBindings`/`ToolRouter` et leurs équivalents use case ont
des formes voisines mais une autorité différente (`ALLOW` contre `REQUEST`). Aucun
generic router ou registry n’est introduit.

`NO_SAFE_CONSOLIDATION_REQUIRED`.
