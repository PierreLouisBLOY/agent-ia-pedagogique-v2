# Phase 12.10-G — Baseline d’intégration du routing runtime

## Périmètre livré

G connecte les frontières B–F au runtime déterministe existant. La composition reste :

```text
PlanExecutor
  -> RoutingPreLaunchGuard
  -> RoutingStepRunner
```

`PlanExecutor`, `DeterministicScheduler`, les agents spécialisés et les catalogues de
workflows ne sont pas modifiés.

## Résolution trusted

`RuntimeRoutingResolverPort` expose uniquement :

- `resolve_use_case_input` ;
- `resolve_tool_input` ;
- `resolve_gate_input` ;
- `resolve_agent_input`.

Les valeurs résolues sont frozen/slotted. Le runtime revalide appartenance au plan,
scope ref, run, step, corrélation, capability, executor, route, gate ref et root
sandbox. Le port ne décide ni permission, ni capability, ni executor, ni facts.
Aucune implémentation production I/O n’est livrée.

## Prelaunch

| Route | Contrôle | Résultat |
|---|---|---|
| GATE / A02 WAITING ou DEFERRED | `GateEngine.evaluate` | `WAITING_GATE` |
| GATE / A02 REJECTED ou EXPIRED | `GateEngine.evaluate` | `DENY` |
| GATE / A02 APPROVED | security check | `ALLOW` de lancement |
| TOOL T02/T03 condition non résolue | dry `ToolCallPolicy` | `CONDITION_REQUIRED` |
| AGENT | policy AG-01→owner exact | `ALLOW` ou `DENY` |
| USE_CASE non-A02, JOIN, DECISION | forme/route statique | `ALLOW` ou `DENY` |

Le prelaunch n’appelle jamais Application, sandbox, tool executor ou agent port.

## Exécution

| `StepKind` | Frontière exacte | Autorité requise |
|---|---|---|
| TOOL | `ToolRouter` | ALLOW + sandbox |
| USE_CASE | `UseCaseRouter` | REQUEST |
| GATE | `GateEngine` revalidé | APPROVED |
| AGENT | `AgentStepRouter` | DELEGATE vers owner |
| JOIN / DECISION | runtime-control delegate | RUNTIME |

Les références retournées sont limitées aux artifacts outil, `result_ref`
Application, `decision_ref` gate, refs du résultat agent et refs du delegate runtime.

## Classification pré/post-effet

Les erreurs outil avant executor et Application avant inbound deviennent des échecs
connus, non retryables, avec effet NONE. Les erreurs après ces appels remontent au
`PlanExecutor` pour reconciliation. Les exceptions agent et runtime-control remontent
également : le composite n’ajoute aucun retry implicite.

Le mapping Application conserve `OutcomeStatus` : SUCCESS→SUCCEEDED,
SUCCESS_WITH_WARNING→PARTIAL, REJECTED/FAILED/INDETERMINATE→FAILED. Sans enveloppe
canonique, une enveloppe sûre est créée; un échec indéterminé ou nécessitant
reconciliation porte UNKNOWN, et des side effects déclarés portent PARTIAL.

## Workflows couverts

- WF-0 : lecture Application réelle ;
- WF-2/WF-4/WF-5 : CAP-A01 via Application ;
- WF-6 : AG-02→AG-03→CAP-A01→AG-04 avec bindings exacts ;
- WF-7 : correction G03 compatible avec le port agent opaque et PlanRevision ;
- WF-10 : attente gate sans attempt, puis revalidation et transfert du decision ref ;
- WF-11 : A01→O05→A02, facts uniquement depuis GateEngine et aucun auto-promotion ;
- plans TOOL explicites : T02/T03 via ToolRouter, sans modification du catalogue WF.

## Frontières préservées

- registries, policies, routers, GateEngine, PlanExecutor et scheduler restent uniques ;
- aucun provider SDK, réseau, DB, filesystem OS, subprocess ou shell ;
- aucun import dynamique, reflection, plugin discovery ou handler arbitraire ;
- aucun polling, retry automatique, persistence ou mutation runtime par output ;
- dépendances projet inchangées : `[]`.

## Validation de clôture

- neuf suites G exécutées individuellement : 45 tests réussis ;
- régression cumulative B→G : 415 tests réussis ;
- suite globale : 2 713 tests réussis ;
- Ruff : aucun finding ;
- mypy : 554 fichiers source, aucun problème ;
- `compileall backend` et `git diff --check` : succès ;
- `[project].dependencies` : `[]`.

## Rationalisation

Les dispositions TOOL ALLOW, Application REQUEST, Agent DELEGATE et Gate APPROVED
restent intentionnellement distinctes.

`NO_SAFE_CONSOLIDATION_REQUIRED`.
