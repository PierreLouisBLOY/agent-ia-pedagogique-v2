# Baseline Phase 12.12-G — Intégration globale sécurité

## Périmètre livré

Le lot G part du commit F
`b8408f87e0b70f3bb5100d30054dc3b99f1a6d90` sur
`phase12/12-12-security-hardening`.

Il relie les contrôles B–F aux chemins runtime et recovery réels :

```text
RoutingPreLaunchGuard
  -> autorité canonique Tool / Application / Agent / Gate
  -> SecurityRuntimeGuard restrictif
  -> RoutingStepRunner
  -> validation sécurité du résultat
  -> PlanExecutor / directives
  -> OrchestrationCoordinator
  -> RecoveryCoordinator / ReplayGuard
```

## Matrice de composition

| Frontière | Autorité conservée | Contrôle sécurité courant | Refus pré-effet | Refus post-effet |
| --- | --- | --- | --- | --- |
| Tool | `ToolCallPolicy.ALLOW` | arguments D/F | zéro appel executor | réconciliation |
| Application | capability `REQUEST` via `UseCaseRouter` | payload/effect D/F | zéro appel inbound | réconciliation |
| Agent | capability `DELEGATE` + scope enfant E | invocation, lineage, contexte E/F | zéro appel specialist | réconciliation |
| Gate | `GateEngine.APPROVED` | aucune autorité dérivée du contenu | attente/refus canonique | sans changement |

`SecurityRuntimeGuard` n'a aucun port et ne connaît aucune policy d'autorité.
Il agrège les dispositions de contenu en `PASS`, `RESTRICT`, `DENY`,
`QUARANTINE` ou `ESCALATE`. Seules les deux premières peuvent accompagner un
`ALLOW` déjà produit par le propriétaire d'autorité.

## Runtime et minimisation

`ResolvedAgentInput` contient désormais l'`AgentInvocation` déléguée exacte.
Le port spécialiste reçoit cette invocation et retourne un `DelegationResult` ;
le router vérifie identité, run, step, corrélation, cible, scope enfant,
lineage, Evidence et contenu avant de projeter les seules refs/métriques/erreurs
sûres vers `StepExecutionResult`.

`ExecutionCycleResult.security_events` est un transport transitoire typé. Une
frontière échouée produit au plus un événement. Ni le contenu brut, ni la
valeur sensible, ni un chemin privé n'apparaissent dans `RunState`,
`ExecutionDirective`, checkpoint ou snapshot. Les collections de refs et les
textes runtime ont des bornes explicites et réutilisent les contrôles F.

## Recovery et crash

Le guard recovery délègue toujours d'abord au prelaunch canonique. Les chemins
de retry et de reprise d'une réservation abandonnée réévaluent donc les scopes,
gates, inputs et handoffs courants. `SecurityRevalidationStatus.INVALID` bloque
le replay ; aucun assessment ancien n'est sauvegardé.

La matrice d'effet est inchangée :

| EffectState | Décision dominante |
| --- | --- |
| `COMMITTED` | aucun replay, récupération du résultat |
| `UNKNOWN` | réconciliation ou manuel |
| `PARTIAL` | réconciliation ou manuel |
| `NONE` | replay possible après toutes les revalidations courantes |

Un rejet de résultat après un appel externe est donc traité comme effet
inconnu. Les probes et records typés restent les seules sources de vérité pour
la réconciliation.

## Architecture et exclusions

Les fitness tests vérifient l'absence d'I/O et d'autorité dans la composition
sécurité, la revalidation recovery et l'absence d'assessment/event dans les
snapshots. Aucun logger, sink, store, provider, réseau, filesystem métier,
SecretStore, Vault, KMS ou dépendance runtime n'est ajouté.

## Validations de clôture

Les valeurs exactes sont renseignées après le dernier replay de validation :

```text
Python                          3.12.13
tests ciblés G                  16 passed
régressions B-F/recovery       241 passed
suite globale                 3300 passed
compileall backend              PASS
Ruff                            PASS
mypy backend                    PASS (591 source files)
git diff --check                PASS
```

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
