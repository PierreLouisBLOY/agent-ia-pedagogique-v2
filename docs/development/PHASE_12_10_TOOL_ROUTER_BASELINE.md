# Baseline Phase 12.10-D - ToolRouter execution boundary

## Statut et perimetre

Le lot D descend directement du commit C
`815ac25dfd67204aa10d515d98cbcc14f237b877` sur la branche
`phase12/12-10-routing-gates-sandbox`.

Il livre uniquement :

```text
ToolExecutorPort + bindings injectes
+ ToolRoutingContext + PreparedToolExecution
+ ToolRouter + ToolExecutionOutcome
+ revalidation resultats et outputs
```

Il ne livre aucun executor production, adapter filesystem OS, provider, reseau,
shell, subprocess, plugin, retry, scheduler, UseCaseRouter, GateEngine,
StepRunner ou integration runtime.

## Frontiere et pipeline

Le package `backend/agent_runtime/tools/` applique l'ordre immuable :

1. ToolCallPolicy doit produire ALLOW ;
2. chaque input est resolve/inspecte puis autorise READ par SandboxPolicy ;
3. chaque output est resolve/inspecte puis autorise CREATE/WRITE ;
4. le binding exact est resolu ;
5. l'executor est appele une seule fois ;
6. ToolCallResult et produced paths sont revalides ;
7. chaque output produit est re-resolu, inspecte et autorise par SandboxPolicy.

Aucun binding n'est consulte avant les ALLOW tool et sandbox.

## Models

`ToolRoutingContext` contient uniquement le root opaque trusted, les input paths
types et les output targets avec operation et metadata declarees.

`PreparedToolExecution` fixe request, descriptor, decisions ALLOW, profile,
paths, timeout, idempotency key, run/step/correlation et contract IDs. Il ne
contient aucun absolute path, handler, provider, credential ou override.

`ToolExecutionOutcome` contient le ToolCallResult canonique et les produced
paths. Un succes doit produire exactement les outputs autorises ; aucun path
supplementaire n'est accepte.

## Port et bindings

`ToolExecutorPort.execute(execution=...)` est provider-neutral. Une surface
injectee separee fournit le mapping exact `tool_id -> executor`. Les doublons,
fuzzy matches, fallback et imports dynamiques sont interdits.

Les deux seuls IDs routables sont :

```text
tool.render_document
tool.convert_format
```

CAP-T01 et CAP-T04 restent hors ToolRouter.

## Revalidation

Le routeur refuse les mismatches tool/run/step/correlation, outcomes malformes,
erreurs masquees en succes, mappings non agent-safe et metadata d'autorite. Un
FAILED valide est retourne sans promotion ni conversion en succes.

Les sorties sont revalidees depuis le contexte trusted, jamais depuis un root,
profile ou token fourni par l'executor. Symlink, sortie hors root, extension ou
MIME interdit, depassement de taille et contenu actif/executable produisent un
refus post-execution.

## Erreurs fermees

Le routeur utilise des codes fermes et messages fixes :

```text
TOOL_NOT_ALLOWED
TOOL_NOT_BOUND
SANDBOX_PROFILE_REQUIRED
SANDBOX_RESOLUTION_FAILED
SANDBOX_DENIED
EXECUTOR_FAILED
RESULT_TOOL_MISMATCH
RESULT_RUN_MISMATCH
RESULT_STEP_MISMATCH
RESULT_CORRELATION_MISMATCH
OUTPUT_PATH_MISMATCH
OUTPUT_SANDBOX_DENIED
INVALID_EXECUTION_OUTCOME
```

Aucun chemin hostile ni detail provider n'entre dans le message agent-safe.

## Timeout et idempotence

Seuls `ToolCallDecision.effective_timeout` et la cle exacte deja validee par B
sont transmis. D ne cree ni timer, thread/process manager, ledger,
deduplication, replay ou retry.

## Rationalisation

Les ports agents, registries, prepared calls et validators existants ne
partagent pas simultanement la semantique, les invariants et la frontiere
d'autorite de l'execution tool sandboxee.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Validation

Resultats executes avec Python 3.12.13 :

- `tests/unit/test_tool_execution_model.py` : 14 PASS ;
- `tests/unit/test_tool_router.py` : 21 PASS ;
- integration ToolRouter/sandbox : 9 PASS ;
- fitness architecture execution tool : 9 PASS ;
- regression ciblee B-D : 203 PASS ;
- suite globale : 2 559 PASS ;
- `compileall` : PASS ;
- Ruff : PASS ;
- mypy : PASS sur 537 fichiers source ;
- dependencies runtime : `[]`.

L'audit securite et Git final complete cette matrice avant le commit de
cloture.

## Suite

Le prochain lot autorise est 12.10-E. Aucun travail E n'est commence en D.
