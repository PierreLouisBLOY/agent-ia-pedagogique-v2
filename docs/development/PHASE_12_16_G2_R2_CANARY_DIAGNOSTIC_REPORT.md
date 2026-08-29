# Phase 12.16-G2-R2A — Diagnostic offline du canary R2

## Décision

```text
PHASE 12.16-G2-R2A = PASS / CLOSED
OPENAI_REVIEW_FAILURE_CLASSIFICATION = NO_OUTPUT_TEXT
ANTHROPIC_CANARY_REUSABLE = TRUE
R2B_CALLS = 1
R2A_LIVE_PROVIDER_CALLS = 0
R2A_PROVIDER_COST_USD = 0
NEXT_GATE = 12.16-G2-R2B_READY_AFTER_EXPLICIT_APPROVAL
```

Ce lot est intégralement offline. Aucun credential n'a été résolu et aucun
transport provider n'a été construit ou appelé.

## Baseline

- branche : `phase12/12-16-provider-model-calibration` ;
- HEAD/upstream d'entrée : `4d3b93be82bbda1e1600ba5a17c0c7906fcb4d50` ;
- parent : `005cf33dc84917f3f3d06b755e3ae93988d69a53` ;
- main/origin-main : `7ae02ee109bcc6399ec0f71616da6aef07abda81` ;
- worktree d'entrée : propre.

## Intégrité des preuves R2

La lecture est restée limitée aux artefacts locaux ignorés par Git. Aucun octet
des fichiers existants n'a été modifié.

| Preuve | Taille | SHA-256 |
|---|---:|---|
| `artifacts/calibration/12.16-g2-r2/summary.json` | 468 | `bf8aa0277c04dbceec63d2c8dff004bf9fb2849cfc069449b159d428025c67b7` |
| `artifacts/calibration/12.16-g2-r2/ledger.json` | 1 886 | `45316f4e72f3d634cb31117e6f9cc690b68da43891b035558ed9a2aa46b33eb9` |
| raw Anthropic référencé | 61 | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` |

Contrôles : matrice `d0d972312a0c9922f9a0629728e7579836dd2abbbade034b5316003bf54fee13`,
plafond `0.100200 USD`, deux records terminaux, zéro `PENDING`, zéro
`STARTED`, zéro doublon, zéro retry et zéro rerun.

| Call ID | Statut | Input | Output | Coût |
|---|---|---:|---:|---:|
| `remediation.openai-review.scn-05.canary.r1` | `FAILED / OPENAI_REVIEW_INVALID_RESPONSE` | 870 | 1 024 | `0.023960 USD` |
| `remediation.anthropic-scorer.scn-01.clarity.canary.r1` | `PASSED / STRUCTURED` | 979 | 168 | `0.003638 USD` |

Coût R2 total : `0.027598 USD`.

## Classification OpenAI

Le record OpenAI ne contient ni `raw_output_path` ni `raw_output_sha256` et le
répertoire raw ne contient aucun fichier OpenAI. La seule classification
supportée par les preuves est donc :

```text
CLASSIFICATION = NO_OUTPUT_TEXT
UTF8_BYTES = 0
SHA256 = NONE
JSON_PARSE_STATUS = NOT_APPLICABLE
POST_VALIDATION_STATUS = NOT_APPLICABLE
LAST_EXPECTED_SYNTAX_TYPE = NONE
```

L'usage `1024/1024` établit une saturation du budget de sortie, mais ne prouve
pas à lui seul une troncature JSON. La raison provider et les reasoning tokens
n'ayant pas été conservés par R2, aucune certitude supplémentaire n'est
revendiquée.

## Diagnostic privé OpenAI

L'audit du code a confirmé que le contrat privé conservait status, texte et
usage, mais perdait `incomplete_details.reason` et
`output_tokens_details.reasoning_tokens`. Le transport mappait déjà
`status=incomplete`; Review parsait ensuite le payload avant d'ajouter son
warning, transformant un payload non parseable en `INVALID_RESPONSE`.

R2A ajoute sans modifier `ReviewPort`, `GenerationPort` ni un contrat public :

- `OpenAIIncompleteReason = none | max_output_tokens | content_filter | other` ;
- `OpenAIResponseUsage.reasoning_tokens` avec préservation de `None` et `0` ;
- `OpenAIReasoningEffort = none | low | medium | high | xhigh | max` ;
- émission de `reasoning.effort` uniquement lorsqu'un caller le fournit ;
- cause privée `OPENAI_REVIEW_INCOMPLETE_MAX_OUTPUT_TOKENS` pour un output
  non parseable borné par `max_output_tokens` ;
- maintien de `ReviewPortError.INVALID_RESPONSE` côté public ;
- maintien d'un payload incomplet mais cohérent en `PARTIAL`, avec warning
  `OPENAI_RESPONSE_INCOMPLETE`.

La documentation OpenAI officielle confirme que `max_output_tokens` couvre les
tokens visibles et de raisonnement et expose `incomplete_details.reason` ainsi
que les reasoning tokens :
`https://developers.openai.com/api/reference/cli/resources/responses/methods/create`.

## Réutilisation Anthropic

Le canary R2 et `cal.score.anchor.scn-01.a.clarity.r1` sont identiques sur les
huit dimensions exigées : critère, scénario, anchor, sérialisation de
l'observation, modèle, profil, schéma et plafond de sortie.

- anchor : 278 octets,
  `5468fd843013bbd89f2bea9f2c0fe35a73323303f9a3a5059d96dc1c703035eb` ;
- observation des deux appels : 1 089 octets,
  `6c6ff1c3b4d4b3687b4e3c8230559577a7e5d3582d53b44157e4e6ee9fe39e68` ;
- schéma :
  `968312b8f7f4059cfb47b4c70bff98ec14f61089b2b72fa78821368d62bc4dc1` ;
- modèle/profil : `claude-sonnet-5` /
  `anthropic.claude-sonnet-5.scorer` ;
- output max : 512.

```text
ANTHROPIC_CANARY_REUSABLE_AS_G2_SCORE = TRUE
ANTHROPIC_FAMILY_READINESS = PASSED
```

Anthropic est exclu de R2B et ne doit pas être rejoué.

## Matrice R2B gelée

```text
PLAN_VERSION = 12.16-g2-r2b-openai-review-canary-v1
CHECKSUM = f2f4b224299a958b1a2e0d82b61b671befb222bb244efbe18342b41823ce05d3
CALL_COUNT = 1
PROVIDER = OpenAI
WORKLOAD = Review
MODEL = gpt-5.6-sol
REASONING_EFFORT = low
MAX_OUTPUT_TOKENS = 4096
AUTOMATIC_RETRY = 0
APPROVAL_REQUIRED = TRUE
REQUESTED_CEILING_USD = 0.137400
```

L'appel reprend le contenu logique SCN-05 et référence explicitement le canary
R2 échoué. Le schéma demeure inchangé : 3 377 octets, sept propriétés racine,
32 findings maximum, SHA-256
`844a0a76f9dc828c9e7dc89ed3ea724e209fb8abbb5f1d688683aa04ea20851f`.

Le choix `low` conserve un raisonnement non nul tout en réduisant le risque lié
au défaut provider `medium`. Le budget 4 096 quadruple la borne saturée, reste
très inférieur à la limite modèle et n'altère ni schéma ni post-validation.
OpenAI documente pour Sol les efforts `none`, `low`, `medium` par défaut,
`high`, `xhigh`, `max`, ainsi que les prix `4/20 USD` par million de tokens :
`https://developers.openai.com/api/docs/models/gpt-5.6-sol`.

## Architecture et sécurité

- delta de port public : zéro ;
- Generation, Transformation et Correction continuent d'omettre l'effort ;
- aucun comportement Anthropic modifié ;
- aucun corpus, anchor, rubric, registre, retrieval ou harness core modifié ;
- aucun raw, ledger, summary, secret ou chemin absolu committé ;
- `ADR_REQUIRED = NO`, car l'effort explicite reste un paramètre du seul canary
  R2B et non une politique runtime générale.

STOP après R2A. Ne pas exécuter R2B sans approbation humaine du nouveau
checksum et du nouveau plafond.
