# ADR-P12-042 — Intégration globale sécurité runtime et recovery

## Statut

Accepté pour la Phase 12.12-G.

## Contexte

Les lots B à F ont établi le vocabulaire de confiance et d'événement, l'isolation
instruction/donnée, les contrôles Tool/Application, la sécurité des handoffs et
les limites anti-exfiltration. Ces politiques existaient aux frontières mais
devaient être composées dans les chemins réels `PlanExecutor`, routing et
recovery, sans créer une nouvelle autorité ni modifier les garanties d'effet de
12.11.

## Décision

`RoutingPreLaunchGuard` demeure la composition canonique avant effet. Il
exécute l'autorité propriétaire puis applique `SecurityRuntimeGuard`, façade
pure et restrictive. Cette façade compose seulement des assessments B–F :
`PASS` et `RESTRICT` permettent de poursuivre une décision d'autorité déjà
positive ; `DENY`, `QUARANTINE` et `ESCALATE` ne peuvent jamais autoriser.

```text
Tool        : ToolCallPolicy ALLOW -> sécurité request -> exécution
Application : capability REQUEST  -> sécurité request -> inbound Application
Agent       : capability DELEGATE -> sécurité invocation/handoff -> specialist
Gate        : GateEngine APPROVED -> poursuite du chemin concerné
```

Les résultats Tool, Application et Agent sont réévalués avant leur projection
en `StepExecutionResult`. Un refus détecté avant appel ne lance aucun effet. Un
refus après appel produit `RECONCILIATION_REQUIRED` avec effet inconnu ; le
contenu hostile ne peut pas être utilisé pour déduire `NONE`, `PARTIAL` ou
`COMMITTED`.

## Événements et état

`SecurityEvent` reste data-only. Il n'existe aucun sink, store, logger ou
exporter. Un échec de frontière transporte au plus un événement minimisé dans
`PreLaunchDecision` puis `ExecutionCycleResult`. Ces événements sont
transitoires : ils ne sont copiés ni dans `RunState`, ni dans les directives,
ni dans les snapshots recovery.

Les IDs, refs, métriques, raisons de blocage et raisons d'arrêt du runtime sont
bornés et contrôlés par les invariants agent-safe de F. Aucune valeur sensible,
contenu hostile brut ou chemin privé ne peut devenir un état persistant.

## Recovery

Retry, replay et reprise après crash rappellent le `RoutingPreLaunchGuard`
canonique avec les données courantes. Un assessment antérieur n'est jamais une
preuve d'autorité ni un cache de sécurité. `ReplayPreconditions` porte seulement
un statut fermé `VALID`, `INVALID` ou `NOT_REQUIRED` ; `INVALID` bloque le
replay avec `SECURITY_INVALID`.

L'ordre des décisions d'effet de 12.11 reste prioritaire : `COMMITTED` bloque,
`UNKNOWN` réconcilie, `PARTIAL` reste manuel ou à réconcilier, et seul `NONE`
peut atteindre les préconditions de replay. La réconciliation ne consomme que
les facts typés du ledger et les probes propriétaires, jamais un output ou un
assessment sécurité comme preuve d'effet.

## Invariants

```text
SECURITY_RESTRICTS_BUT_NEVER_GRANTS_AUTHORITY
ROUTING_PRELAUNCH_GUARD_REMAINS_CANONICAL
DETECTABLE_PRE_EFFECT_FAILURE_CALLS_NO_EXTERNAL_PORT
POST_EFFECT_SECURITY_FAILURE_REQUIRES_RECONCILIATION
RUNSTATE_DIRECTIVES_AND_SNAPSHOTS_ARE_RAW_FREE
RECOVERY_REVALIDATES_CURRENT_SECURITY
STALE_SECURITY_ASSESSMENTS_ARE_NON_AUTHORITATIVE
EFFECT_STATE_12_11_REMAINS_DOMINANT
SECURITY_EVENT_REMAINS_DATA_ONLY
```

## Hors périmètre

Aucun provider, SecretStore, DLP externe, observabilité, sink, scheduler,
worker ou infrastructure 12.13 n'est ajouté. Les autorités Gate, Tool,
Application et Agent ne sont ni fusionnées ni dupliquées.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```
