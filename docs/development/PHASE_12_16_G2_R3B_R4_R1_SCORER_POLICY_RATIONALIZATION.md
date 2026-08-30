# Phase 12.16-G2-R3B-R4-R1 — Rationalisation de la policy Anthropic Scorer

## Preuve R4 préservée

- Ledger : `2163050a6dc580acadddcedbb72ec13ee5b984f0769b51593a965d2bace99c82`.
- Summary : `50e7c8171e97f9ba732a78ca30c6fb195e095a59ad7becaff0496cf214ac9859`.
- Classification : `MAX_TOKENS_EXHAUSTED_BEFORE_TEXT` : réponse reçue, `stop_reason=max_tokens`, `0` text block et `512/512` output tokens.
- R1 ne prétend pas que les 512 tokens sont tous des thinking tokens.

## Audit du transport avant R1

- Aucun `thinking` ni `output_config.effort` explicite.
- Thinking blocks et `usage.output_tokens_details.thinking_tokens` non capturés.
- Seuls les text blocks étaient comptés ; `max_retries=0` était déjà actif.

## Revalidation officielle Anthropic

- Sonnet 5 active l'adaptive thinking par défaut ; l'effort API par défaut est `high`.
- Thinking peut être désactivé ; `low` est supporté via `output_config.effort`.
- `max_tokens` couvre thinking + texte ; les thinking tokens sont exposés dans `usage.output_tokens_details.thinking_tokens`.
- Sources officielles :
  - https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5
  - https://platform.claude.com/docs/en/build-with-claude/effort
  - https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
  - https://platform.claude.com/docs/en/api/messages/create
  - https://platform.claude.com/docs/en/about-claude/pricing

## Décision

- Option A `disabled/512` rejetée : changement méthodologique trop fort.
- Option B retenue : `adaptive/low/2048`, raisonnement conservé et headroom x4.
- Option C rejetée : effort `high` implicite trop consommateur et non explicite.
- Policy : `EXPLICIT_ADAPTIVE_LOW_2048` ; delta des ports publics : `NONE`.
- La télémétrie conserve uniquement les counts et tokens, jamais le thinking brut.

## Scores Anthropic historiques

| Logical slot | Proof | Output SHA-256 | Final status |
| --- | --- | --- | --- |
| `cal.score.anchor.scn-01.a.clarity.r1` | `R2` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION` |
| `cal.score.anchor.scn-01.a.organization-utility.r1` | `R3B` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION` |
| `cal.score.anchor.scn-01.b.clarity.r1` | `R3B` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION` |
| `cal.score.anchor.scn-01.b.organization-utility.r1` | `R3B` | `be29addb485255f4ed3903747562fe27f9d26a5a2a90846aa31d2b34056fa70b` | `DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION` |
| `cal.score.anchor.scn-01.c.clarity.r1` | `R3B-R2` | `3d2e4cb76ed3d5f10eabd369f19933404a5900df95674eaa2bc96c67b815ba3d` | `DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION` |

Les cinq preuves restent intactes mais ne comptent plus dans la calibration finale.
Les `20` résultats OpenAI restent réutilisables pour les projections selected-output.

## Nouvelle population homogène

- `48` anchors initiaux + `16` répétabilités + `12` selected-output = `76` slots.
- Aucun ancien score Anthropic n'est soustrait.

## Plans gelés

- R2 one-shot : `12.16-g2-r4-r2-anthropic-policy-canary-v1` / `906de866d6c5f3503a20c38f9909182f48b9e7aaf980f0138470cb25dd1a717b`.
- R3 conditionnel : `12.16-g2-r4-r3-anthropic-uniform-completion-v1` / `5ed0abbb6a27b0118be7045abc412216ef320a6fe407ad4d02a6076d621ccd82`.
- Les anciennes approbations ne valent pas pour ces nouveaux checksums.

## Preuve offline

- `LIVE_PROVIDER_CALLS_R1 = 0`.
- `LIVE_PROVIDER_COST_R1 = 0.000000 USD`.
- R4 ledger/summary non modifiés ; R2/R3 non exécutés.
