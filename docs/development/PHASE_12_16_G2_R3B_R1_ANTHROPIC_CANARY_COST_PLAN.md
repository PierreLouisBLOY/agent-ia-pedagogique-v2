# Phase 12.16-G2-R3B-R1 — Plan de coût du canary Anthropic

## Matrice scellée

- Plan : `12.16-g2-r3b-r2-anthropic-canary-v1`.
- Matrice SHA-256 : `60ffe8fd1d99cf60c53d3ea0644624fe09f820d6a59552e7cd2fec3597c334a4`.
- Approval required : `TRUE`.
- Appels : `1` ; retry/rerun : `0/0`.
- Call neuf : `remediation.r3.anthropic-scorer.scn-01.c.clarity.canary.r1`.
- Source échouée : `r3.cal.score.anchor.scn-01.c.clarity.r1` ; slot logique : `cal.score.anchor.scn-01.c.clarity.r1`.
- Provider/modèle/profil : `anthropic` / `claude-sonnet-5` / `anthropic.claude-sonnet-5.scorer`.
- Input/observation/schema inchangés : `b6cc367de3229a83ac3af9cdf717db21b00aad6a9dc23b490dd2fb35343b914f` / `ca1906fafb88814565125c344f31e051fd154d4bd17ca267517d991f70dabd79` / `968312b8f7f4059cfb47b4c70bff98ec14f61089b2b72fa78821368d62bc4dc1`.
- Max output : `512` ; retry : `0`.

## Prix officiel et plafond

- Source : https://platform.claude.com/docs/en/about-claude/pricing.
- Claude Sonnet 5 : `2.00 USD/MTok input`, `0.20 USD/MTok cache hit`, `10.00 USD/MTok output`.
- Input maximum : `8000` tokens, soit `0.016000 USD`.
- Output maximum : `512` tokens, soit `0.005120 USD`.
- Base : `0.021120 USD` ; marge 25 % : `0.005280 USD`.
- Hard ceiling demandé : `0.026400 USD`.

## Ledger local préparé

- Chemin Git-ignoré : `artifacts/calibration/12.16-g2-r3b-r2/ledger.json`.
- États fermés : `PENDING`, `STARTED`, `COMPLETED`, `FAILED`.
- Seul `PENDING` est exécutable ; `STARTED` est ambigu et arrête ; un terminal n'est jamais rappelé.
- Le ledger et les raws R3 originaux ne sont jamais modifiés.

## Approbation R2 requise

```text
J'approuve exclusivement l'exécution de la matrice
12.16-g2-r3b-r2-anthropic-canary-v1,
checksum 60ffe8fd1d99cf60c53d3ea0644624fe09f820d6a59552e7cd2fec3597c334a4,
1 appel maximum (Anthropic Scorer claude-sonnet-5, max_output_tokens 512),
plafond 0.026400 USD,
aucun retry et arrêt immédiat après ce canary quel que soit le résultat.
```

R2 n'est pas exécuté par R1.
