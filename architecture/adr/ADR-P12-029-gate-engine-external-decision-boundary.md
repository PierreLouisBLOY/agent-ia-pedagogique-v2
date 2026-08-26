# ADR-P12-029 — Frontière externe de décision de gate

## Statut

Accepté — Phase 12.10-F.

## Contexte

Les contrats C-16 `GateRequest` et C-17 `GateDecision` décrivent déjà une demande
pending et une décision externe. Le contrat interdit AG-01 comme auteur, mais il ne
porte ni policy générale d’autorité, ni validation du `run_id`, ni expiration au
moment où une décision est consommée. `CapabilityAuthorizationPolicy` sait faire
évoluer CAP-A02 de `REQUEST_GATE` vers `REQUEST` à partir d’un `PolicyFacts` trusted,
sans qu’une frontière ne valide encore l’origine de ce fait.

## Décision

Un package `backend.agent_runtime.gates` distinct des contrats et du runtime porte :

- `GateAuthorityPolicy`, avec baseline `ActorKind.USER` uniquement et interdiction
  structurelle de configurer `ActorKind.AGENT` ;
- `GateDecisionSourcePort`, port provider-neutral appelé au plus une fois ;
- `GateEngine`, moteur déterministe qui reconstruit les contrats, vérifie autorité,
  identité, lineage, temps, référence et option, puis produit une résolution ;
- `GateResolution`, valeur frozen/slotted avec les dispositions `WAITING`,
  `APPROVED`, `REJECTED`, `DEFERRED` et `EXPIRED` ;
- un bridge déterministe `to_policy_facts()` qui produit
  `matrix_gate_satisfied=True` uniquement pour `APPROVED`.

Les autorités TOOL, PROVIDER, SYSTEM et APPLICATION sont refusées par la baseline.
Tous les agents runtime présents et futurs sont refusés, indépendamment de leur ID.
Le moteur ne fabrique jamais de décision et ne transforme ni absence, ni délai, ni
deferment en approbation.

L’expiration est évaluée à la consommation : si `now > request.expires_at`, la
résolution est `EXPIRED`, même si la décision avait été prise avant l’expiration.
Une date de décision postérieure à `now` est invalide.

Les mappings `options` et `context_summary` restent des données agent-safe. Les clés
structurées tentant de remplacer autorité, gate, expiration, capability, permission,
handler, promotion ou `PolicyFacts` sont refusées ; le texte libre n’est jamais
interprété comme une instruction et n’est pas recopié dans les erreurs sûres.

## Relation avec E et G

Une résolution F n’appelle jamais l’Application. Seule une résolution `APPROVED`
peut produire le fait trusted qui, après réévaluation complète de capability et de
scope par E, fait passer CAP-A02 à `REQUEST`. Il s’agit d’un handoff Application,
pas d’une approbation métier ou d’un `ALLOW` technique.

L’intégration au `PreLaunchGuard` reste différée à G :

- `WAITING` et `DEFERRED` pourront mener à `WAITING_GATE` ;
- `REJECTED` et `EXPIRED` pourront mener à `DENY` ou à une directive workflow ;
- `APPROVED` impose une réévaluation policy et ne devient jamais directement
  `PreLaunchDisposition.ALLOW`.

## Conséquences

- Aucun adapter source production, UI, HTTP, provider, DB, filesystem, cache,
  queue, event bus, polling, retry ou background task n’est ajouté.
- Aucun `PreLaunchGuard`, `StepRunner`, `PlanExecutor`, scheduler ou
  `PromotionPolicy` n’est modifié ou créé.
- Les contrats Gate canoniques restent inchangés et séparés du moteur.
- Une exception de source devient `DECISION_SOURCE_FAILED` sans fuite de données ni
  seconde tentative.
- Les états normaux sont des résolutions, pas des exceptions.

## Alternatives écartées

- Accepter SYSTEM ou APPLICATION automatiquement : nouvelle autorité silencieuse.
- Faire décider le moteur ou déduire l’approbation : violation de la frontière
  externe.
- Réutiliser `PreLaunchGuard` comme moteur : mélange validation d’autorité et
  orchestration runtime.
- Persister ou poller la source : hors périmètre F et création d’effets inutiles.
- Fusionner Gate, capability policy et use-case routing : responsabilités et
  dispositions différentes.

## Rationalisation

`NO_SAFE_CONSOLIDATION_REQUIRED`.
