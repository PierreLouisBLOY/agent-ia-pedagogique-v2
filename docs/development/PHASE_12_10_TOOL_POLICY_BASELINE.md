# Baseline Phase 12.10-B - ToolRegistry et ToolCallPolicy

## Statut et perimetre

Le lot B est construit depuis la baseline canonique
`bbc3520668467393e9ec51349025f455e64f973f` sur la branche
`phase12/12-10-routing-gates-sandbox`.

Il livre uniquement :

```text
ToolEffectClass + ToolRegistry + ToolCallPolicy
```

Il ne livre aucun ToolRouter, sandbox, UseCaseRouter, GateEngine, handler,
provider, I/O, subprocess, reseau, retry ou mecanisme Phase 12.11.

## Classification d'effet

| Classe | Semantique | Idempotence | Sandbox | Baseline |
| --- | --- | --- | --- | --- |
| READ_ONLY | lecture sans mutation | facultative | absent | aucun tool |
| PURE_COMPUTE | calcul side-effect free | facultative | absent | aucun tool |
| LOCAL_FILE_TRANSFORM | sortie locale mutable | obligatoire | obligatoire | T02/T03 |
| EXTERNAL_MUTATION | mutation externe reservee | obligatoire | selon futur ADR | interdite |

`ToolEffectClass` decrit l'effet anticipe. `EffectState` continue de decrire
l'etat constate apres une tentative. Aucun vocabulaire commun n'est cree.

## Registry statique

`ToolDescriptor` contient exactement : tool id, nom canonique, capability id,
identifiants de contrats input/output, classe d'effet, profil sandbox, exigence
d'idempotence et ceiling de timeout.

Le risque n'est pas duplique. `ToolRegistry` consulte le
`CapabilityRegistry` canonique et refuse toute capability inconnue, hors classe
`TECHNICAL_UTILITY`, hors route `UTILITY` ou possedee par un agent. IDs et noms
sont uniques ; le lookup inconnu produit `UnknownToolError` sans fallback.

### Baseline Option A

| Tool | Capability | Effet | Sandbox profile | Idempotence | Timeout ceiling |
| --- | --- | --- | --- | --- | ---: |
| `tool.render_document` | CAP-T02 | LOCAL_FILE_TRANSFORM | `sandbox.local_file_transform.v1` | requise | 120 s |
| `tool.convert_format` | CAP-T03 | LOCAL_FILE_TRANSFORM | `sandbox.local_file_transform.v1` | requise | 120 s |

CAP-T01 et CAP-T04 restent des utilities pures et ne sont pas enregistrees comme
tools routables. Aucun handler n'est associe aux descriptors.

## Decision ToolCall

`ToolCallDecision` porte uniquement : disposition/code, tool et capability,
decision capability composee, effet, profil sandbox, exigence d'idempotence et
timeout effectif. Les dispositions sont `ALLOW` et `DENY`.

Codes fermes :

```text
ALLOW
UNKNOWN_TOOL
UNKNOWN_CAPABILITY
NON_UTILITY_CAPABILITY
CAPABILITY_TOOL_MISMATCH
CAPABILITY_NOT_ALLOWED
PERMISSION_SCOPE_MISMATCH
IDEMPOTENCY_REQUIRED
TIMEOUT_EXCEEDS_CEILING
SANDBOX_REQUIRED
SANDBOX_PROFILE_MISMATCH
EXTERNAL_MUTATION_FORBIDDEN
INVALID_REQUEST
```

## Composition d'autorite

La sequence fail-closed est :

1. acteur de request exact ;
2. capability connue, TECHNICAL_UTILITY et route UTILITY ;
3. tool connu et binding capability exact ;
4. absence de cles d'arguments tentant de transporter une autorite ;
5. refus des mutations externes ;
6. evaluation canonique `CapabilityAuthorizationPolicy` sur le scope exact ;
7. disposition capability strictement ALLOW ;
8. idempotence ;
9. timeout ;
10. profil sandbox declarativement disponible.

La policy ne reimplemente ni AccessMatrix, ni PermissionScopeEvaluator, ni la
condition `request_or_allow_by_workflow`. Un scope deny produit
`PERMISSION_SCOPE_MISMATCH`; toutes les autres dispositions non-ALLOW restent
`CAPABILITY_NOT_ALLOWED`.

## Arguments et sandbox

Les arguments restent les mappings immutables agent-safe de `ToolCallRequest`.
Les cles permettant de choisir ou modifier tool, capability, permission, gate,
handler, import, provider, credentials ou sandbox sont refusees recursivement.
Le lot ne normalise aucun chemin et n'implemente aucun schema engine.

Le profil sandbox transporte seulement un besoin declaratif. Aucun root, path,
symlink, fichier ou cleanup n'est materialise avant 12.10-C.

## Idempotence et timeout

Une cle est obligatoire pour les deux tools baseline. La policy ne stocke pas
la cle, ne deduplique pas et ne rejoue rien. Ces responsabilites restent 12.11.

Un timeout explicite superieur a 120 secondes est refuse. Un timeout inferieur
ou egal est conserve ; un timeout absent prend la ceiling du descriptor.

## Securite et rationalisation

L'audit ne trouve aucun registry tool cache, enum d'effet anticipatif existant,
handler map, sandbox, provider ou helper d'execution a reutiliser. Les patterns
d'erreur inconnue et d'immutabilite restent locaux a leurs registries car leurs
identifiants et autorites different.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Validation

Resultats executes avec Python 3.12.13 :

- `tests/unit/test_tool_registry.py` : 14 PASS ;
- `tests/unit/test_tool_call_policy.py` : 31 PASS ;
- `tests/architecture/test_tool_routing_policy_fitness.py` : 8 PASS ;
- regression `tests/unit tests/architecture` : 2 176 PASS ;
- suite globale : 2 409 PASS ;
- `compileall` : PASS ;
- Ruff : PASS ;
- mypy : PASS sur 528 fichiers source ;
- dependencies runtime : `[]`.

L'audit securite et Git final complete cette matrice avant le commit de
cloture.

## Suite

Le prochain lot autorise est 12.10-C, dedie au sandbox. Aucun travail C n'est
inclus dans cette baseline.
