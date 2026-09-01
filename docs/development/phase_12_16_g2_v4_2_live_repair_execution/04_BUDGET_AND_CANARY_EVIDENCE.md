# Phase 12.16-G2-V4.2 — Budget et canaries

## Canaries

| Famille | Call id | État |
| --- | --- | --- |
| OpenAI generation/correction | `cal.generation.course.primary.r1` | PASSED |
| OpenAI Review | `cal.review.exercise.primary.r1` | PASSED |
| Anthropic Scorer | `cal.score.anchor.scn-08.strong.feedback-quality.r2` | PASSED |

Aucun fanout n'a précédé sa canary de famille. L'ancien scoring Anthropic en erreur
serveur a réussi comme nouvelle exécution autorisée, sans retry.

## Budget de la tranche

- coût OpenAI mesuré et prudent : `0.108168 USD` ;
- coût Anthropic mesuré et prudent : `0.051992 USD` ;
- coût total mesuré : `0.160160 USD` ;
- coût ledger prudent : `0.160160 USD` ;
- réserve pour usage inconnu : `0.000000 USD` ;
- plafond approuvé : `2.111240 USD` ;
- marge restante : `1.951080 USD` ;
- plafond préservé : oui.

Les transports OpenAI et Anthropic sont configurés avec `max_retries=0`. Aucun appel
n'a été rejoué après terminalisation.

`LIVE_AUTHORIZATION = CONSUMED`

`LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`
