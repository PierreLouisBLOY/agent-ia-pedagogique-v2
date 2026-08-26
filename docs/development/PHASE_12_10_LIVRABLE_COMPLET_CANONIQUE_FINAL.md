# Phase 12.10 — Livrable complet canonique final

## Statut canonique

```text
PHASE 12.10 = CLOSED / MERGED
FUNCTIONAL_SHA = e10591d4cb48b3edc7df583e29c15b6d7af3116c
ENTRY_BASELINE = bbc3520668467393e9ec51349025f455e64f973f
MERGE_MODE = FAST_FORWARD_ONLY
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
NEXT_PHASE = 12.11
```

Ce document est l'unique changement documentaire de 12.10-H3. Il clôt la
Phase 12.10 sans engager de travail de Phase 12.11.

## 1. Objet de la Phase 12.10

La Phase 12.10 établit le routage déterministe et fail-closed entre le runtime
agent, les outils techniques sandboxés, les use cases Application, les agents
spécialisés et les décisions externes de gate. Elle conserve séparées les
autorités TOOL, APPLICATION, AGENT, GATE et RUNTIME.

Le code fonctionnel livré relie les frontières de policy, registry, sandbox,
routing et gate au `PlanExecutor` existant. Il ne livre ni fournisseur réel, ni
accès métier direct, ni persistence de retry/recovery, ni promotion automatique.

## 2. Baseline d'entrée et delta fonctionnel

La baseline d'entrée est le commit :

```text
bbc3520668467393e9ec51349025f455e64f973f
docs: close phase 12.9 canonical delivery
```

Le code fonctionnel 12.10 se termine au commit :

```text
e10591d4cb48b3edc7df583e29c15b6d7af3116c
feat: integrate trusted runtime routing
```

Le delta fonctionnel exact entre ces deux commits est :

```text
85 files changed, 12541 insertions(+), 9 deletions(-)
```

Classification vérifiée :

| Catégorie | Nombre |
| --- | ---: |
| Production | 31 |
| ADR | 6 |
| Documents de baseline | 6 |
| Supports/fakes de tests | 4 |
| Fichiers de tests | 38 |
| Total | 85 |

Ces statistiques excluent le présent document H3.

## 3. Phase 12.10-A — audit d'ouverture

L'audit A a inventorié les contrats ToolCall, UseCase, Gate et planning/runtime,
la policy de capability existante, les mécanismes attendus et leurs autorités.
Il a confirmé les gaps réels : registry et policy tool, sandbox, ToolRouter,
UseCaseRouter, GateEngine et composition runtime. Il a également établi les
risques d'authority-smuggling, path traversal, symlink escape, contenu actif,
credential leakage, reflection de handler et retry utilisé comme bypass.

A n'a modifié aucun fichier et a ouvert l'implémentation B avec :

```text
PHASE 12.10-A — PASS / CLOSED
IMPLEMENTATION_GATE = 12.10-B_READY
```

## 4. Phase 12.10-B — classification d'effet, ToolRegistry et ToolCallPolicy

B introduit les quatre classes d'effet anticipé : `READ_ONLY`, `PURE_COMPUTE`,
`LOCAL_FILE_TRANSFORM` et `EXTERNAL_MUTATION`. Elles restent distinctes de
`EffectState`, qui décrit l'effet observé après une tentative.

`ToolRegistry` est statique, provider-neutral et exact-match. Ses descriptors
ne contiennent ni handler, callable, secret, provider, connexion ou risque
dupliqué. Il réutilise le `CapabilityRegistry` canonique.

La baseline routable contient exactement :

| Tool | Capability | Classe d'effet | Profil sandbox |
| --- | --- | --- | --- |
| `tool.render_document` | CAP-T02 | `LOCAL_FILE_TRANSFORM` | `sandbox.local_file_transform.v1` |
| `tool.convert_format` | CAP-T03 | `LOCAL_FILE_TRANSFORM` | `sandbox.local_file_transform.v1` |

CAP-T01 et CAP-T04 restent hors `ToolRegistry` et hors `ToolRouter`.

`ToolCallPolicy` compose `CapabilityAuthorizationPolicy`. Seule une disposition
`ALLOW`, avec binding exact, scope non élargi, idempotency key requise, timeout
sous la ceiling et profil sandbox exact, devient un `ToolCallDecision.ALLOW`.
Les mutations externes sont interdites et tout écart échoue fermé.

## 5. Phase 12.10-C — frontière sandbox

C introduit le profil unique `sandbox.local_file_transform.v1`, les chemins
relatifs typés, le root opaque, les metadata résolues, la policy data-only et le
port filesystem abstrait.

Le profil autorise :

- entrées `.docx`, `.md`, `.pdf`, `.txt` ;
- sorties `.docx`, `.pdf`, `.txt` ;
- 25 MiB maximum par entrée ;
- 50 MiB maximum par sortie ;
- 20 fichiers maximum ;
- aucun symlink, contenu actif, exécutable ou chemin réseau.

`SandboxRelativePath` refuse les chemins absolus, drives Windows, UNC, URI,
traversal, backslashes, segments ambigus et formes Unicode non canoniques.
`SandboxRootRef` ne transporte que des identifiants opaques ; aucun chemin OS
absolu n'est exposé. `SandboxFilesystemPort` reste abstrait et aucun adapter
filesystem de production n'est livré. Le sandbox borne une opération déjà
autorisée ; il ne crée aucune permission.

## 6. Phase 12.10-D — ToolRouter

Le pipeline du `ToolRouter` est fermé et ordonné :

```text
ToolCallPolicy
-> résolution et inspection des inputs
-> SandboxPolicy pré-exécution
-> binding executor exact
-> un unique appel executor
-> revalidation ToolCallResult
-> réinspection des outputs
-> SandboxPolicy post-output
```

Aucun retry, fallback, fuzzy match, import dynamique ou executor fournisseur de
production n'est introduit. Une erreur connue avant executor peut porter
`EffectState.NONE`. Après l'appel executor, une incertitude d'effet n'est jamais
reclassée en `NONE` : elle exige reconciliation et conserve `UNKNOWN` ou l'état
partiel approprié. Les outputs ne deviennent pas une preuve d'autorité.

## 7. Phase 12.10-E — routing Application

`UseCaseRegistry` est metadata-only et exact-match. Il contient exactement :

| Use case | Capability | Opération |
| --- | --- | --- |
| `application.read_canonical_resource` | CAP-R01 | READ |
| `application.read_production` | CAP-R02 | READ |
| `application.read_metadata_status` | CAP-R03 | READ |
| `application.run_deterministic_validation` | CAP-A01 | REQUEST |
| `application.request_promotion` | CAP-A02 | REQUEST |
| `application.export_artifact` | CAP-A03 | REQUEST |

`ApplicationInboundPort` est provider-neutral et ses bindings sont séparés des
descriptors. Le `UseCaseRouter` exige le couple exact StepKind/Executor,
capability, `PermissionScope`, acteur, run, step et corrélation. Seule
`PolicyDisposition.REQUEST` autorise au plus un appel inbound ; `ALLOW`,
`DELEGATE`, `REQUEST_GATE`, `CONDITION_REQUIRED` et `DENY` ne sont pas routables.

Les erreurs métier et Application ne sont pas masquées. Aucun retry n'est
effectué. CAP-A03 reste une route Application et ne contourne jamais le sandbox
ou le `ToolRouter`.

Pour CAP-A02, l'absence de gate approuvée produit `REQUEST_GATE` et aucun appel
inbound. Des `PolicyFacts` trusted issus d'une gate approuvée permettent seulement
de réévaluer la policy jusqu'à `REQUEST`; ils ne promeuvent rien automatiquement.

## 8. Phase 12.10-F — GateAuthorityPolicy et GateEngine

La baseline de `GateAuthorityPolicy` admet uniquement `ActorKind.USER`.
AGENT, TOOL, PROVIDER, SYSTEM et APPLICATION sont refusés.

`GateEngine` appelle `GateDecisionSourcePort.receive()` au plus une fois. Il ne
poll pas, ne retente rien et ne livre aucun source adapter de production. `None`
devient `WAITING`. Les dispositions fermées sont `WAITING`, `APPROVED`,
`REJECTED`, `DEFERRED` et `EXPIRED`.

La décision est reconstruite et vérifiée contre request, gate, acteur, run,
step, corrélation, fenêtre temporelle, référence et option. Les décisions futures
ou expirées sont refusées. `matrix_gate_satisfied=True` n'est produit que pour
`APPROVED`. Le moteur n'appelle ni Application, ni outil, ni promotion.

Une gate `APPROVED` est une décision externe trusted, pas une permission métier
et pas une promotion.

## 9. Phase 12.10-G — intégration du routing runtime

G compose les frontières B–F avec le runtime existant :

```text
PlanExecutor
  -> RoutingPreLaunchGuard
  -> RoutingStepRunner
```

`PlanExecutor`, `DeterministicScheduler`, les agents spécialisés et les
catalogues de workflows restent inchangés.

`RuntimeRoutingResolverPort` expose exactement quatre méthodes typées :
`resolve_use_case_input`, `resolve_tool_input`, `resolve_gate_input` et
`resolve_agent_input`. Il n'existe aucune résolution générique `ref -> object`
et aucune implémentation I/O de production.

Le `RoutingPreLaunchGuard` mappe `WAITING`/`DEFERRED` vers `WAITING_GATE`,
`REJECTED`/`EXPIRED` vers `DENY` et `APPROVED` vers l'autorisation de lancement
seulement. Pour TOOL, il effectue uniquement un dry-check de policy.

Le `RoutingStepRunner` applique un dispatch fermé :

| StepKind | Frontière |
| --- | --- |
| TOOL | `ToolRouter` |
| USE_CASE | `UseCaseRouter` |
| AGENT | `AgentStepRouter` |
| GATE | `GateEngine` |
| JOIN / DECISION | contrôle RUNTIME |

## 10. AgentStepRouter et autorité AGENT

Les bindings agent concernent uniquement AG-02, AG-03 et AG-04 ; aucun executor
AG-01 n'est créé. Le propriétaire exact, `PolicyDisposition.DELEGATE` et le
`target_agent` exact sont exigés.

Le mapping reste : E01/E02/E03 vers READ, G01 vers CREATE, G02/G03 vers
TRANSFORM et V01/V02 vers REVIEW. Aucune logique métier agent n'est déplacée
dans le runtime et aucun output agent n'acquiert d'autorité.

## 11. JOIN et DECISION

JOIN et DECISION restent des contrôles d'orchestration appartenant au runtime.
Ils passent par le delegate runtime-control injecté, sans policy engine parallèle,
sans accès métier et sans mécanisme de permission implicite.

## 12. Séparation finale des cinq autorités

| Autorité | Chaîne exigée | Limite |
| --- | --- | --- |
| TOOL | `PolicyDisposition.ALLOW` -> `SandboxPolicy` -> executor exact | Sandbox n'est pas permission ; output sans autorité |
| APPLICATION | `PolicyDisposition.REQUEST` -> inbound Application | Application conserve l'autorité métier |
| AGENT | `PolicyDisposition.DELEGATE` -> owner agent exact | DELEGATE n'est pas ALLOW |
| GATE | décision externe `APPROVED` -> `PolicyFacts` trusted | APPROVED n'est pas promotion |
| RUNTIME | JOIN / DECISION / orchestration | Aucun pouvoir métier direct |

En particulier : `REQUEST != ALLOW`, `DELEGATE != ALLOW`, sandbox != permission,
tool output != authority, agent output != authority et LLM/document != authority.

## 13. Effets et erreurs pré/post exécution

- TOOL pré-executor : échec connu, non retryable, `EffectState.NONE` possible.
- TOOL post-executor : effet possiblement commis, reconciliation et état
  `UNKNOWN`/partiel conservé.
- APPLICATION pré-inbound : échec connu, non retryable, `EffectState.NONE`.
- APPLICATION post-inbound : effet possiblement commis, reconciliation et
  `UNKNOWN`.
- AGENT et contrôle RUNTIME : une exception de port conserve l'incertitude
  d'effet et exige reconciliation.

Aucun effet possiblement commis n'est remappé en `NONE`. Les erreurs agent-safe
emploient des codes et raisons fermés sans fuite de path, payload ou contexte.

## 14. Workflows couverts

- WF-0 : lecture réelle par Application.
- WF-2, WF-4 et WF-5 : CAP-A01 par Application.
- WF-6 : AG-02 -> AG-03 -> A01 -> AG-04 avec bindings exacts.
- WF-7 : correction G03 compatible avec le port agent opaque et `PlanRevision`.
- WF-10 : `WAITING_GATE` sans attempt, puis revalidation de la décision.
- WF-11 : A01 -> GATE -> A02 ; A02 impossible sans gate `APPROVED`.
- T02/T03 : plans TOOL explicites, sans injection dans le catalogue workflows.

## 15. Architecture finale et unicité

L'audit final trouve une définition canonique pour chacun des composants suivants :

- registries : `CapabilityRegistry`, `ToolRegistry`, `SandboxProfileRegistry`,
  `UseCaseRegistry` ;
- policies : `CapabilityAuthorizationPolicy`, `ToolCallPolicy`, `SandboxPolicy`,
  `GateAuthorityPolicy` ;
- routing : `ToolRouter`, `UseCaseRouter`, `GateEngine`, `AgentStepRouter`,
  `RoutingPreLaunchGuard`, `RoutingStepRunner` ;
- runtime : `PlanExecutor`, `DeterministicScheduler`.

Aucun second scheduler, executor de plan ou policy engine n'est introduit.
Registries, descriptors, bindings, prepared execution models, ports et fakes
restent séparés selon leurs autorités et leurs cycles de vie.

## 16. Code fonctionnel, abstractions et tests

Le code fonctionnel réel comprend les registries et policies, les modèles
sandbox, les routeurs tool/Application/agent, le `GateEngine`, le resolver typé,
le prelaunch et le step runner.

Les frontières suivantes restent abstraites et injectées, sans adapter de
production en 12.10 : `ToolExecutorPort`, `SandboxFilesystemPort`,
`ApplicationInboundPort`, `GateDecisionSourcePort`, les quatre résolutions du
`RuntimeRoutingResolverPort` et les ports agent/runtime-control.

Les fichiers sous `tests/support/` sont uniquement des fakes de preuve. Ils ne
sont ni composés en production ni présentés comme des handlers ou providers réels.
Les fichiers sous `tests/unit/`, `tests/integration/` et `tests/architecture/`
prouvent les invariants ; ils ne créent aucune autorité runtime.

## 17. Audit sécurité et I/O

L'audit cumulatif du delta fonctionnel ne trouve aucun secret ou credential,
SDK fournisseur, accès HTTP/réseau, DB/ORM, repository métier direct, filesystem
OS de production, subprocess/shell, import dynamique, reflection arbitraire,
`eval`/`exec`, plugin discovery, polling/background task ou retry automatique.

Les occurrences de noms tels que `secret`, `credential`, `api_key`, chemins
absolus et traversal appartiennent aux deny-lists, messages documentaires ou
tests négatifs. Elles ne contiennent aucune valeur sensible réelle.

Les filtres récursifs refusent les metadata capables de transporter capability,
permission, scope, gate approval, provider credentials, handler, executor ou
override runtime. Les `PolicyFacts` sont reconstruits depuis des décisions gate
validées ; aucune promotion directe et aucun retry contournant DENY n'existent.

```text
SECURITY_AUDIT = PASS
BLOCKING_FINDINGS = 0
```

## 18. Rationalisation finale

Les registries, policies, bindings, routeurs, ports, filtres de sécurité,
erreurs sûres, modèles de résolution et modèles d'exécution préparée ont été
comparés selon leur sémantique, leurs invariants, leur autorité et leur cycle de
vie. Les ressemblances de forme entre TOOL, APPLICATION, AGENT, GATE et RUNTIME
ne justifient pas une abstraction commune : elle effacerait leurs décisions
distinctes et élargirait l'autorité.

Les fakes et documents ne sont pas consolidés avec le code de production. Aucun
finding réel ne justifie un refactor H3.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## 19. H1 — audit pré-merge

H1 a confirmé la baseline, les six commits B→G, l'absence de commit parasite,
l'unicité architecturale, les cinq autorités, la sécurité, les workflows, les
tests et la rationalisation. Le worktree était propre et la branche fonctionnelle
était six commits devant `main`, sans divergence.

```text
PHASE 12.10-H1 — PASS / CLOSED
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_GATE = FAST_FORWARD_READY
```

## 20. H2 — fast-forward strict

H2 a avancé `main` de `bbc3520668467393e9ec51349025f455e64f973f`
vers `e10591d4cb48b3edc7df583e29c15b6d7af3116c` exclusivement avec
`git merge --ff-only`, puis a poussé `main`. Aucun merge commit, rebase, squash,
cherry-pick, force-push ou déplacement de la branche source n'a eu lieu.

Après push, `main`, `origin/main`, la branche source locale et sa référence
distante pointaient toutes sur le SHA fonctionnel, avec un ahead/behind de 0/0.

```text
PHASE 12.10-H2 — PASS / CLOSED
MERGE_MODE = FAST_FORWARD_ONLY
POST_MERGE_GATE = H3_REQUIRED
```

## 21. Validations finales H3

Les validations ont été réellement exécutées sur `main` avec le Python de la
`.venv` du dépôt :

| Validation | Résultat observé |
| --- | --- |
| Python | 3.12.13 |
| Neuf suites G exécutées individuellement | 45 PASS |
| Régression canonique B→G | 415 PASS |
| Tous les 38 fichiers de tests touchés | 469 PASS |
| Suite globale | 2 713 PASS |
| `python -m compileall backend` | PASS |
| Ruff | PASS |
| mypy `backend` | PASS, 554 fichiers source |
| `git diff --check` | PASS |
| diff-check baseline fonctionnelle vers HEAD | PASS |
| `[project].dependencies` | `[]` |

La lignée fonctionnelle contient exactement six commits et aucun merge commit.

## 22. Lignée Git B→G

```text
907614a6c20758565530d84b63ca5f224bf7a4a8  feat: establish tool registry and call policy
815ac25dfd67204aa10d515d98cbcc14f237b877  feat: establish sandbox policy boundary
3c6d3e13d25c388638902d7093551ffb964b4867  feat: route authorized sandboxed tool calls
98b28bfaf184ef50418be73c09ffb1376f930df2  feat: route authorized application use cases
4e9f9fb0735e192bae255bc27622c8aa1bc344df  feat: establish external gate decision engine
e10591d4cb48b3edc7df583e29c15b6d7af3116c  feat: integrate trusted runtime routing
```

Le parent du futur commit documentaire H3 doit être exactement
`e10591d4cb48b3edc7df583e29c15b6d7af3116c`. La branche fonctionnelle locale et
distante doit rester sur ce SHA.

## 23. Responsabilités différées

Restent explicitement hors de la Phase 12.10 :

- accounting et effect ledger ;
- persistence des idempotency keys ;
- retry et recovery policy ;
- replay protection ;
- opérationnalisation de reconciliation/recovery ;
- limites et budgets d'exécution prévus par la feuille de route ;
- adapters réels de filesystem, outils, gates, Application ou resolver runtime.

Aucun de ces éléments n'est simulé par un fake ou inféré d'un output agent/outil.

## 24. Handoff Phase 12.11

Le prochain lot canonique est :

```text
Phase 12.11 — recovery, accounting, retries et snapshots persistants
NEXT_PHASE = 12.11
```

Ce handoff transmet uniquement les responsabilités différées ci-dessus. La Phase
12.11 n'est pas commencée par ce document.

## 25. Décision finale

Le code fonctionnel intégré est identique au SHA G, les audits post-merge sont
conformes, toutes les validations finales passent, les dépendances runtime restent
vides et le seul changement H3 est ce livrable canonique.

```text
PHASE 12.10-H3 — PASS / CLOSED
PHASE 12.10 — CLOSED / MERGED
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_MODE = FAST_FORWARD_ONLY
NEXT_PHASE = 12.11
```
