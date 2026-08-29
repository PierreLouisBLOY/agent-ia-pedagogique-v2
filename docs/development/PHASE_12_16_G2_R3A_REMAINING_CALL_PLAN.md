# Phase 12.16-G2-R3A � Matrice r�siduelle

## Gel canonique

- Plan : `12.16-g2-r3-completion-v1`
- Matrice SHA-256 : `245f0c8b2e4d74f61ec58bd5b02824b4d0edfae3dbd55c1c518a9a09ccecee98`
- Manifeste r�utilis� SHA-256 : `cace6d138a8ac1fef2920fc45abedbae7b3c99cc30ab9e76af86a16ed3f0ca4e`
- Approval required : `TRUE`
- Retry/rerun : `0/0`
- Appels live R3A : `0`
- Co�t live R3A : `0 USD`

## Comptabilit� r�siduelle

- `96 - 15 = 81` slots.
- OpenAI Review : `6`.
- Anthropic Scoring : `75` (`47` anchors initiaux, `16` r�p�tabilit�s, `12` selected-output).

## Reviews restantes et ordre

| Ordre | Slot logique | Mod�le | Profil | Effort | Max output | R�le canary |
|---:|---|---|---|---|---:|---|
| 1 | `cal.review.exercise.fallback.r1` | `gpt-5.6-terra` | `openai.gpt-5.6-terra.review-fallback` | `low` | 4096 | `FAMILY_CANARY` |
| 2 | `cal.review.exercise.primary.r2` | `gpt-5.6-sol` | `openai.gpt-5.6-sol.review` | `low` | 4096 | `NO` |
| 3 | `cal.review.assessment.primary.r1` | `gpt-5.6-sol` | `openai.gpt-5.6-sol.review` | `low` | 4096 | `NO` |
| 4 | `cal.review.correction.primary.r1` | `gpt-5.6-sol` | `openai.gpt-5.6-sol.review` | `low` | 4096 | `NO` |
| 5 | `cal.review.qcm.primary.r1` | `gpt-5.6-sol` | `openai.gpt-5.6-sol.review` | `low` | 4096 | `NO` |
| 6 | `cal.review.qcm.fallback.r1` | `gpt-5.6-terra` | `openai.gpt-5.6-terra.review-fallback` | `low` | 4096 | `NO` |

La premi�re Review Terra est le call 1 de toute la matrice. En cas d'�chec, tous les autres appels deviennent `BLOCKED_BY_CANARY` avant tout fan-out.

Les param�tres `low/4096` sont limit�s � la calibration rem�di�e. `PRODUCTION_REVIEW_LIMIT_ADOPTION = DEFERRED_TO_12.16-H`.

## Readiness et ledger

- `OPENAI_REVIEW_SOL = PASSED` via hashes R2B.
- `ANTHROPIC_SCORER = PASSED` via hashes R2.
- `OPENAI_REVIEW_TERRA = PENDING` jusqu'au canary R3.
- Ledger pr�par� : `artifacts/calibration/12.16-g2-r3/ledger.json`.
- �tats : `PENDING`, `STARTED`, `COMPLETED`, `FAILED`, `SKIPPED_DEPENDENCY_FAILED`, `BLOCKED_BY_CANARY`.
- `PENDING` est le seul �tat ex�cutable ; `STARTED` est ambigu et arr�te ; un terminal n'est jamais rappel�.
- Le ledger importe uniquement le hash du manifeste, jamais les raws historiques.

## Prix officiels revalid�s

| Mod�le | Input / MTok | Cached input / MTok | Output / MTok | Source |
|---|---:|---:|---:|---|
| `gpt-5.6-sol` | `4.00` | `0.40` | `20.00` | https://developers.openai.com/api/docs/models/gpt-5.6-sol |
| `gpt-5.6-terra` | `2.00` | `0.20` | `12.00` | https://developers.openai.com/api/docs/models/gpt-5.6-terra |
| `claude-sonnet-5` | `2.00` | `0.20` | `10.00` | https://platform.claude.com/docs/en/about-claude/pricing |

Terra supporte officiellement `low`, Responses et Structured Outputs ; le candidat `low/4096` est donc valide pour ses deux slots.

## Co�t R3 futur

- Estimation de r�f�rence : `0.739992 USD`.
- Maximum conservateur avant marge : `2.149984 USD`.
- Marge 25 % : `0.537496 USD`.
- Hard ceiling demand� : `2.687480 USD`.
- Par mod�le : `claude-sonnet-5=1.584000, gpt-5.6-sol=0.439680, gpt-5.6-terra=0.126304` USD.
- Co�t R3 d�j� consomm� : `0 USD`.

## Approbation R3B requise

```text
J'approuve exclusivement l'ex�cution de la matrice
12.16-g2-r3-completion-v1,
checksum 245f0c8b2e4d74f61ec58bd5b02824b4d0edfae3dbd55c1c518a9a09ccecee98,
81 appels maximum (6 OpenAI Review : 4 gpt-5.6-sol et 2 gpt-5.6-terra, reasoning effort low, max_output_tokens 4096 ; 75 Anthropic Scorer claude-sonnet-5, max_output_tokens 512),
plafond 2.687480 USD,
aucun retry, canary gpt-5.6-terra en premier et arr�t imm�diat avant tout autre appel si ce canary �choue.
```

R3B n'est pas ex�cut� par R3A.
