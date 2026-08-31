# 12.16-G2-V4 — Pricing à source unique implémenté

## Autorité technique

```text
SNAPSHOT_ID = official-2026-08-31-v4
SNAPSHOT_SHA256 = 31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8
TERRA = 2.00 / 0.20 / 12.00 USD/Mtok
SOL = 4.00 / 0.40 / 20.00 USD/Mtok
SONNET_5 = 2.00 / 0.20 / 10.00 USD/Mtok
```

`pricing_snapshot_v4.json` est l'unique source fonctionnelle. `pricing.py` vérifie son checksum avant chargement. Le call plan, les coûts maximaux, les coûts observés, le ledger et le rapport consomment les mêmes quotes. La duplication `_G2_PRICING` a été supprimée.

Pour 102 appels :

```text
ESTIMATED_BASE_USD = 0.877656
MAXIMUM_BEFORE_MARGIN_USD = 2.601312
PROPOSED_TECHNICAL_CEILING_USD = 3.251640
APPROVED_HARD_CEILING_USD = NONE
```

Le plafond technique n'est pas une approbation financière. Toute mutation du snapshot ou de son checksum échoue avant transport.
