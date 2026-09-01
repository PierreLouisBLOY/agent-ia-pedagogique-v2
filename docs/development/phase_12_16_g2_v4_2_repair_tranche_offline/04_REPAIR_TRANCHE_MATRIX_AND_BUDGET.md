# Phase 12.16-G2-V4.2 — Matrice et budget de la repair tranche

## Synthèse

- records logiques : 102 ;
- carry-forward : 63 ;
- nouveaux appels requis : 39 ;
- OpenAI : 20, dont 10 `gpt-5.6-terra` et 10 `gpt-5.6-sol` ;
- Anthropic : 19 `claude-sonnet-5` ;
- workloads : 8 generation, 2 transformation, 3 correction, 7 review, 19 scoring ;
- retries automatiques : 0.

Les canaries de famille sont placés en tête de leur famille :

1. `cal.generation.course.primary.r1` pour OpenAI generation/correction ;
2. `cal.review.exercise.primary.r1` pour OpenAI Review ;
3. `cal.score.anchor.scn-08.strong.feedback-quality.r2` pour Anthropic Scorer.

## Calls de la tranche

| # | Call id | Provider / model | Workload | Input bytes max | Output tokens max | Motif |
| ---: | --- | --- | --- | ---: | ---: | --- |
| 1 | cal.generation.course.primary.r1 | openai / gpt-5.6-terra | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 2 | cal.generation.course.primary.r2 | openai / gpt-5.6-terra | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 3 | cal.generation.course.fallback.r1 | openai / gpt-5.6-sol | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 4 | cal.generation.exercise.primary.r1 | openai / gpt-5.6-terra | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 5 | cal.generation.assessment.primary.r1 | openai / gpt-5.6-terra | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 6 | cal.generation.assessment.fallback.r1 | openai / gpt-5.6-sol | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 7 | cal.generation.qcm.primary.r1 | openai / gpt-5.6-terra | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 8 | cal.generation.qcm.fallback.r1 | openai / gpt-5.6-sol | generation | 6000 | 2048 | SOURCE_PROJECTION_CHANGED |
| 9 | cal.transformation.resource.primary.r1 | openai / gpt-5.6-terra | transformation | 5000 | 1536 | SOURCE_PROJECTION_CHANGED |
| 10 | cal.transformation.resource.primary.r2 | openai / gpt-5.6-terra | transformation | 5000 | 1536 | SOURCE_PROJECTION_CHANGED |
| 11 | cal.correction.remediation.primary.r1 | openai / gpt-5.6-sol | correction | 6000 | 1536 | SOURCE_PROJECTION_CHANGED |
| 12 | cal.correction.remediation.primary.r2 | openai / gpt-5.6-sol | correction | 6000 | 1536 | SOURCE_PROJECTION_CHANGED |
| 13 | cal.correction.remediation.fallback.r1 | openai / gpt-5.6-terra | correction | 6000 | 1536 | SOURCE_PROJECTION_CHANGED |
| 14 | cal.review.exercise.primary.r1 | openai / gpt-5.6-sol | review | 1792 | 3072 | SOURCE_NOT_COMPLETED |
| 15 | cal.review.exercise.primary.r2 | openai / gpt-5.6-sol | review | 1792 | 3072 | SOURCE_NOT_COMPLETED |
| 16 | cal.review.exercise.fallback.r1 | openai / gpt-5.6-terra | review | 1792 | 3072 | SOURCE_NOT_COMPLETED |
| 17 | cal.review.assessment.primary.r1 | openai / gpt-5.6-sol | review | 1536 | 3072 | SOURCE_NOT_COMPLETED |
| 18 | cal.review.correction.primary.r1 | openai / gpt-5.6-sol | review | 1792 | 3072 | SOURCE_NOT_COMPLETED |
| 19 | cal.review.qcm.primary.r1 | openai / gpt-5.6-sol | review | 1536 | 3072 | SOURCE_NOT_COMPLETED |
| 20 | cal.review.qcm.fallback.r1 | openai / gpt-5.6-terra | review | 1536 | 3072 | SOURCE_NOT_COMPLETED |
| 21 | cal.score.anchor.scn-08.strong.feedback-quality.r2 | anthropic / claude-sonnet-5 | scoring | 8000 | 2048 | SOURCE_NOT_COMPLETED |
| 22–39 | 18 `cal.score.output.*` dépendants | anthropic / claude-sonnet-5 | scoring | 8000 chacun | 2048 chacun | UPSTREAM_CALL_SPEC_CHANGED |

Les 18 ids du dernier groupe couvrent les scores selected-output SCN-03 à SCN-08 et
sont sélectionnés par dépendance upstream explicite dans le module exécutable.

## Budget technique proposé

Le pricing est inchangé et son snapshot est vérifié. L'estimation nominale utilise
input-bytes/4 et output-budget/2. Le maximum technique conservateur utilise un token
par input byte et la totalité du budget output, puis applique une marge de 1,25.

- input nominal : 59 944 tokens ;
- output nominal : 42 240 tokens ;
- coût nominal : `0.705384 USD` ;
- input maximum : 239 776 tokens ;
- output maximum : 84 480 tokens ;
- maximum avant marge : `1.688992 USD` ;
- plafond après marge, arrondi au millionième supérieur : `2.111240 USD`.

`PROPOSED_REPAIR_TRANCHE_CEILING_USD = 2.111240`

`APPROVED_REPAIR_TRANCHE_CEILING_USD = NONE`

`LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`

Le budget guard refuse un plafond absent, trop faible, dépassé, une matrice différente,
un call non planifié, dupliqué ou au-delà de 39. Le scoring Anthropic failed devient un
nouvel appel futur explicitement autorisé, jamais un retry implicite.

`MATRIX_SHA256 = 605358444f1bc9052ca7b4e55057c9d5424b3ad3b4deecc17bdde83e23c18aa5`

`PRICING_SHA256 = 31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`
