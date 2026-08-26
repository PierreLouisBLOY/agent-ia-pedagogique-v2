# Phase 12.10-F — Baseline GateEngine / décision externe

## Périmètre livré

F ajoute uniquement une frontière de validation de décision externe. Le moteur ne
décide pas, ne persiste rien, ne poll pas, ne retente rien et n’appelle ni
l’Application ni un outil.

| Surface | Responsabilité |
|---|---|
| `GateAuthorityPolicy` | Autorités externes admises, baseline USER uniquement |
| `GateDecisionSourcePort` | Réception provider-neutral, un appel maximum |
| `GateEngine` | Reconstruction et validation fail-closed |
| `GateResolution` | Résultat data-only sans autorité implicite |
| `to_policy_facts()` | Bridge F→policy, true uniquement pour APPROVED |

## Autorité

La baseline contient exactement `ActorKind.USER`. `ActorKind.AGENT` est refusé de
façon structurelle pour AG-01, AG-02, AG-03, AG-04 et tout futur agent. TOOL,
PROVIDER, SYSTEM et APPLICATION sont refusés par défaut. Le `required_actor` du
`GateRequest`, l’acteur de la décision et `meta.actor` doivent être identiques et
admis par la policy.

## Pipeline déterministe

1. reconstruire `ContractMeta` puis `GateRequest` ;
2. valider l’autorité du `required_actor` ;
3. retourner `EXPIRED` si la demande est expirée à la consommation ;
4. appeler `GateDecisionSourcePort.receive()` exactement une fois ;
5. retourner `WAITING` pour `None` ;
6. revalider request, gate ID, acteur, run, step, corrélation, temps, référence,
   option et status de la décision ;
7. reconstruire `ContractMeta`, la request embarquée et `GateDecision` ;
8. revérifier l’expiration ;
9. produire une `GateResolution` sans side effect.

Une exception de source est réduite à `DECISION_SOURCE_FAILED`. Aucun commentaire,
reason ou contexte brut n’entre dans la raison sûre et aucun second appel n’a lieu.

## Dispositions

| Résolution | Origine | `matrix_gate_satisfied` |
|---|---|---:|
| `WAITING` | Source sans décision | faux |
| `APPROVED` | Décision USER exacte et consommable | vrai |
| `REJECTED` | Rejet externe exact | faux |
| `DEFERRED` | Décision différée exacte | faux |
| `EXPIRED` | `now > expires_at` | faux |

`DEFERRED`, l’absence et l’expiration ne deviennent jamais `APPROVED`. Une décision
future est rejetée. Une décision prise avant expiration ne peut pas être réactivée
si elle est consommée après expiration.

## Anti-forgery et données

Le moteur ne fait confiance à aucun objet retourné par la source. Il reconstruit les
contrats et compare exactement request, gate ID, acteur, run, step et corrélation.
Il vérifie aussi la fenêtre temporelle, `decision_ref` et `selected_option`.

Les options et le résumé restent des mappings agent-safe. Les structures visant à
remplacer required actor, authority policy, expiration, gate ID, capability,
permission, handler, promotion ou `PolicyFacts` sont refusées récursivement. Les
chaînes reason/comment ne sont jamais analysées comme des commandes.

## Bridge F→E pour CAP-A02

- `WAITING`, `REJECTED`, `DEFERRED` et `EXPIRED` produisent des facts faux ; E
  réévalue CAP-A02 en `REQUEST_GATE` et n’appelle aucun inbound Application.
- `APPROVED` produit des facts vrais ; E réévalue capability et scope, obtient
  `REQUEST`, puis réalise au plus un handoff inbound.

Le GateEngine n’appelle jamais l’Application. Le UseCaseRouter ne reçoit et ne
valide jamais de `GateDecision`. Une gate approuvée n’est ni une promotion, ni un
`ALLOW` direct.

## Intégration différée à G

Le mapping futur documenté, non implémenté en F, est :

- `WAITING` / `DEFERRED` → `PreLaunchDisposition.WAITING_GATE` ;
- `REJECTED` / `EXPIRED` → `DENY` ou directive selon workflow policy ;
- `APPROVED` → réévaluation capability/scope, jamais `ALLOW` automatique.

Aucun `PreLaunchGuard`, `StepRunner` ou changement de `PlanExecutor` n’appartient à
F.

## Frontières préservées

- Aucun source adapter production, UI ou service d’approbation.
- Aucun provider, HTTP, réseau, DB, cache, filesystem, queue ou event bus.
- Aucun polling, retry, scheduler ou background task.
- Aucun dynamic import ou fallback.
- Aucune persistence ou décision fabriquée.
- Aucune `PromotionPolicy`.
- Dépendances projet inchangées et égales à `[]`.

## Rationalisation

`GateDecision`, `GateEngine`, `PreLaunchGuard` et
`CapabilityAuthorizationPolicy` restent distincts. Leur fusion brouillerait
respectivement données externes, validation, contrôle de lancement et autorisation
de capability.

`NO_SAFE_CONSOLIDATION_REQUIRED`.
