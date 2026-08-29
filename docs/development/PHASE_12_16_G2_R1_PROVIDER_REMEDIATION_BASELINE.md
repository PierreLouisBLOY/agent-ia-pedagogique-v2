# Phase 12.16-G2-R1 — remédiation offline des providers

## Décision

```text
PHASE 12.16-G2-R1 = PASS / CLOSED
PROVIDER_SCHEMA_COMPATIBILITY = REMEDIATED
SYSTEMIC_CANARY_BREAKER = ESTABLISHED
LIVE_PROVIDER_CALLS = 0
LIVE_PROVIDER_COST_USD = 0
NEXT_GATE = 12.16-G2-R2_READY_AFTER_EXPLICIT_APPROVAL
```

R1 corrige uniquement les frontières techniques déjà décidées. Aucun appel
OpenAI ou Anthropic n'a été exécuté, aucun retry n'a été tenté et R2 n'a pas été
lancé.

## Références Git et immutabilité G2

- branche : `phase12/12-16-provider-model-calibration` ;
- parent R1 / commit G2 : `005cf33dc84917f3f3d06b755e3ae93988d69a53` ;
- parent G1 : `413a61ad2f50f6c061891a44d8c0987374722f81` ;
- `main` et `origin/main` à l'entrée :
  `7ae02ee109bcc6399ec0f71616da6aef07abda81` ;
- relation d'entrée `main...branch = 0/9`, merge-base = `main` ;
- commit R1 : commit contenant le présent document, SHA rapporté dans le
  handoff Git afin d'éviter une référence auto-récursive.

Les preuves G2 n'ont pas été modifiées :

| Preuve | SHA-256 d'entrée et de sortie |
|---|---|
| `PHASE_12_16_G2_PEDAGOGICAL_CALIBRATION_REPORT.md` | `380EC585D1B4E7423BD22F2C2B4611438D5A43CFEC5EC3F80BED4A3D1BCA24DC` |
| `PHASE_12_16_G2_PEDAGOGICAL_CALIBRATION_REPORT.json` | `3C091BEE7B378AB05505D7893A05304C4E0717142B1D6118B41A9EF7F87D1423` |

Le ledger G2 reste terminal et immuable : 13 `COMPLETED`, 83 `FAILED`, aucun
retour à `PENDING`, aucun retry et aucun doublon.

## Confirmation de la cause OpenAI Review

L'audit confirme les sept éléments causaux :

1. `build_openai_review_request()` construisait un JSON Schema strict ;
2. sans référence admissible, l'item schema valait `{"not": {}}` ;
3. le Review schema contenait aussi plusieurs `uniqueItems` ;
4. le transport envoyait ce schema avec `strict = true` ;
5. la documentation OpenAI exclut explicitement `not`, ne liste que
   `minItems` et `maxItems` parmi les contraintes array supportées et annonce
   une erreur pour un schema strict non supporté ;
6. le schema Generation, plus simple, a produit 13 succès structurés en G2 ;
7. les 7 Review failures avaient chacune 0 token et une latence de 195 à
   238 ms.

Source officielle :
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

```text
OPENAI_REVIEW_ROOT_CAUSE = UNSUPPORTED_PROVIDER_JSON_SCHEMA_KEYWORDS
UNSUPPORTED_KEYWORDS_FOUND = not, uniqueItems
```

Les keywords `allOf`, `dependentRequired`, `dependentSchemas`, `if`, `then` et
`else` ont aussi été audités récursivement : aucun ne subsiste dans les schemas
envoyables.

## Abaissement OpenAI provider-specific

La nouvelle frontière `backend/adapters/outbound/openai/schema.py` réalise :

```text
V2_CANONICAL_SCHEMA
-> deliberate uniqueItems lowering
-> OPENAI_SUPPORTED_STRICT_SCHEMA validation
-> transport
```

Décisions :

- `uniqueItems` est retiré uniquement de la copie provider ;
- quand aucune evidence ref n'est admissible, un item schema supporté est
  conservé et les deux tableaux concernés imposent `maxItems = 0` ;
- `not` n'est jamais envoyé ;
- tout keyword inconnu ou explicitement non supporté échoue avant l'appel SDK ;
- les objets conservent toutes leurs clés `required` et
  `additionalProperties = false` ;
- types, enums, `anyOf`, bornes numériques et `minItems`/`maxItems` supportés
  sont conservés ;
- le schema source est copié et n'est jamais muté ;
- Generation passe par le même validateur en régression.

Avant :

```json
{"items":{"not":{}},"maxItems":0,"uniqueItems":true}
```

Après, pour un tableau sans référence admissible :

```json
{"items":{"type":"string"},"maxItems":0}
```

La post-validation Review reste autoritaire : elle rejette encore les
séquences dupliquées, les finding IDs dupliqués et toute evidence ref absente
de l'ensemble admissible. Aucun contrat public `ReviewPort` n'a changé.

## Confirmation de la cause Anthropic

L'audit confirme que :

- `score_output_schema()` contient `minimum = 0` pour les deux entiers ;
- ce schema était passé directement à
  `messages.create(output_config.format.schema=...)` ;
- ni `anthropic.transform_schema()` ni `messages.parse()` n'étaient utilisés ;
- `_parse_outcome()` imposait déjà les entiers exacts, un dénominateur positif
  et un score rationnel normalisé dans `[0, 1]`.

La documentation Anthropic demande de retirer ou transformer notamment
`minimum`, `maximum`, `minLength` et `maxLength`, puis de valider contre le
schema original :
[Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

```text
ANTHROPIC_SCHEMA_ROOT_CAUSE = UNTRANSFORMED_UNSUPPORTED_JSON_SCHEMA_CONSTRAINT
ANTHROPIC_LIVE_UNIQUE_CAUSE = UNRESOLVED
```

Cette cause explique un rejet de schema possible, mais R1 ne prétend pas qu'il
s'agissait de l'unique cause live tant que billing, permission et accès modèle
ne sont pas confirmés.

## Transformation Anthropic

Le transport appelle désormais `anthropic.transform_schema()` sur une copie
défensive avant `messages.create`. Le schema source reste inchangé.

Avant :

```json
{"type":"integer","minimum":0}
```

Après :

```json
{"type":"integer","description":"{minimum: 0}"}
```

Le keyword `minimum` n'est plus présent dans le provider schema. Les types,
`required` et `additionalProperties = false` sont conservés. Une erreur de
transformation produit `INVALID_REQUEST` et interdit l'appel transport.

La validation V2 garde sa sémantique exacte : pas de float, dénominateur nul ou
négatif rejeté, numérateur négatif rejeté, numérateur supérieur au
dénominateur rejeté, et `INCONCLUSIVE` avec nombres rejeté.

## Taxonomie technique fermée

Les deux transports utilisent la même taxonomie fermée :

```text
INVALID_REQUEST
AUTHENTICATION
PERMISSION
BILLING
RATE_LIMIT
NOT_FOUND
TIMEOUT
CONNECTION
SERVER
REFUSED
UNAVAILABLE
```

Mapping OpenAI : 400/`BadRequestError` -> `INVALID_REQUEST`, 401 ->
`AUTHENTICATION`, 402 -> `BILLING`, 403 -> `PERMISSION`, 404 -> `NOT_FOUND`,
429 -> `RATE_LIMIT`, timeout -> `TIMEOUT`, connexion -> `CONNECTION`, 5xx ->
`SERVER`, autre -> `UNAVAILABLE`.

Mapping Anthropic : 400 -> `INVALID_REQUEST`, 401 -> `AUTHENTICATION`, 402 ->
`BILLING`, 403 -> `PERMISSION`, 404 -> `NOT_FOUND`, 429 -> `RATE_LIMIT`,
timeout -> `TIMEOUT`, connexion -> `CONNECTION`, 5xx/overloaded -> `SERVER`,
refusal -> `REFUSED`, autre -> `UNAVAILABLE`.

Les ports publics restent fermés. Les recording transports du runner capturent
uniquement le code avant re-raise, ce qui permet par exemple :

```text
OPENAI_REVIEW_TRANSPORT_INVALID_REQUEST
ANTHROPIC_SCORER_TRANSPORT_BILLING
```

Aucun message, body, header, identifiant de requête, prompt, secret ou contenu
raw provider n'est mémorisé.

## Systemic canary breaker

`SystemicCanaryBreaker`, owner test-only du runner, maintient un état distinct
pour `OPENAI_REVIEW` et `ANTHROPIC_SCORER` :

```text
PENDING -> canary success -> PASSED -> fan-out autorisé
PENDING -> canary failure -> BLOCKED -> tout appel ultérieur interdit
```

Un fan-out avant canary est refusé. Un canary terminal ne peut pas être rejoué.
Toute catégorie fermée, notamment invalid request, auth, permission, billing,
not found, rate limit ou server, bloque la famille. Il n'existe aucun retry
automatique.

## Matrice R2 gelée mais non exécutée

```text
PLAN_VERSION = 12.16-g2-r2-canary-v1
APPROVAL_REQUIRED = TRUE
CALL_COUNT = 2
CHECKSUM = d0d972312a0c9922f9a0629728e7579836dd2abbbade034b5316003bf54fee13
LIVE_CALL_COUNT_R1 = 0
```

| Call ID | Famille | Source représentative | Input max | Output max |
|---|---|---|---:|---:|
| `remediation.openai-review.scn-05.canary.r1` | OpenAI Review | `cal.review.exercise.primary.r1` | 7 000 octets | 1 024 tokens |
| `remediation.anthropic-scorer.scn-01.clarity.canary.r1` | Anthropic Scorer | `cal.score.anchor.scn-01.a.clarity.r1` | 8 000 octets | 512 tokens |

Plafond prudent estimé, marge 1,25 incluse :

- OpenAI : `0.060600 USD` ;
- Anthropic, tarif historique conservateur : `0.039600 USD` ;
- total : `0.100200 USD`.

Ce checksum est distinct de la matrice G1/G2 et ne constitue pas une
autorisation d'exécution.

## Audit des 13 succès OpenAI G2

L'audit local n'a renvoyé que des compteurs et hashes :

```text
PRIOR_OPENAI_SUCCESS_COUNT = 13
PRIOR_RAW_OUTPUT_HASH_VALID_COUNT = 13
PRIOR_SCHEMA_PARSABLE_COUNT = 13
PRIOR_LINKED_CALL_COUNT = 13
PRIOR_WITHIN_RETENTION_COUNT = 13
PRIOR_RAW_OUTPUT_REUSABLE = TRUE
```

Les fichiers raw ne sont ni copiés ni ajoutés à Git. La fonction d'audit est
read-only et le ledger initial reste byte-identique.

## Readiness Anthropic avant R2

R1 n'inspecte aucun compte. Les cinq confirmations manuelles restent non
résolues :

- [ ] `ANTHROPIC_USAGE_CREDITS_POSITIVE = TRUE`
- [ ] `ANTHROPIC_PAYMENT_METHOD_VALID = TRUE`
- [ ] `ANTHROPIC_SPEND_LIMIT_AVAILABLE = TRUE`
- [ ] `ANTHROPIC_KEY_WORKSPACE_ACCESS = TRUE`
- [ ] `CLAUDE_SONNET_5_ACCESS = TRUE`

Ne consigner ni balance exacte, ni clé, ni moyen de paiement, ni donnée de
compte dans Git.

## Preuve no-call et validations

```text
R1_LIVE_PROVIDER_CALL_COUNT = 0
R1_PROVIDER_COST_USD = 0
CONCRETE_PROVIDER_TRANSPORT_IN_R1_TESTS = 0
AUTOMATIC_RETRY = 0
AUTOMATIC_RERUN = 0
```

Résultats autoritatifs :

| Gate | Résultat |
|---|---|
| tests ciblés D/E/G1/G2/R1/architecture | `139 passed, 1 skipped` |
| global pytest, seed canonique read-only | `4169 passed, 3 skipped` en `748.96 s` |
| Python | `3.12.13` |
| Ruff | PASS |
| mypy `backend` | PASS, 659 fichiers |
| mypy `evaluation_harness` | PASS, 30 fichiers |
| compileall `backend`, `evaluation_harness`, `tests` | PASS |
| `git diff --check` et cached diff-check | PASS |

Les trois skips globaux sont des gates explicitement fermés : calibration
provider live, semantic retrieval live et semantic retrieval offline R1. Une
première tentative globale sous sandbox a été écartée parce que le seed externe
n'était pas lisible ; le résultat ci-dessus provient du rerun autorisé en
lecture seule avec basetemp hors dépôt.

## Sécurité, diff et ADR

- aucun secret ou fichier `.env` suivi ;
- aucun raw output, ledger, log, base SQLite/index ou donnée runtime ajouté ;
- aucune dépendance ajoutée ;
- aucun registre capability/workflow, core du harness, corpus, rubric, index
  sémantique, sélection modèle ou pricing runtime modifié ;
- `main` demeure inchangé ;
- `ADR_REQUIRED = NO` : l'abaissement provider, la taxonomie privée et le
  breaker test-only corrigent l'exécution des décisions existantes sans changer
  une frontière durable de production.

Fichiers de production modifiés :

- `backend/adapters/outbound/openai/schema.py` ;
- `backend/adapters/outbound/openai/contracts.py` ;
- `backend/adapters/outbound/openai/transport.py` ;
- mappings OpenAI Generation et Review.

Fichiers test/calibration principaux :

- transport et contrats Anthropic test-only ;
- `tests/calibration/pedagogical/live_runner.py` ;
- `remediation_plan.py` et `reuse_audit.py` ;
- tests schema, erreur, scorer, runner, breaker et réutilisation.

## Handoff R3

R2 reste interdit sans les cinq confirmations Anthropic et une approbation
humaine explicite du nouveau checksum et du plafond.

Demande exacte attendue :

```text
J'approuve exclusivement l'exécution de la matrice
12.16-g2-r2-canary-v1,
checksum d0d972312a0c9922f9a0629728e7579836dd2abbbade034b5316003bf54fee13,
2 appels maximum (1 OpenAI Review, 1 Anthropic Scorer),
plafond 0.100200 USD,
aucun retry et arrêt immédiat de la famille au premier canary en échec.
```

STOP après R1. Ne pas exécuter R2 dans ce lot.
