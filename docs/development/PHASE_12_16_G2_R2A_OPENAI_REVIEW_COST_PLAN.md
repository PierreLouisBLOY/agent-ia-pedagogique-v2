# Phase 12.16-G2-R2A — Plan de coût OpenAI Review R2B

```text
APPROVAL_REQUIRED = TRUE
R2A_LIVE_CALLS = 0
R2A_PROVIDER_COST = 0
PLAN_VERSION = 12.16-g2-r2b-openai-review-canary-v1
CHECKSUM = f2f4b224299a958b1a2e0d82b61b671befb222bb244efbe18342b41823ce05d3
CALL_COUNT = 1
```

## Paramètres gelés

- provider/workload : OpenAI Review ;
- modèle : `gpt-5.6-sol` ;
- effort de raisonnement : `low`, explicite ;
- borne input prudente : 7 000 unités tarifaires à partir de la borne UTF-8 ;
- borne output totale, reasoning inclus : 4 096 tokens ;
- retry et rerun automatiques : zéro.

La documentation OpenAI officielle consultée le 29 août 2026 donne pour Sol
`4.00 USD/Mtok` input, `0.40 USD/Mtok` input caché et `20.00 USD/Mtok`
output : `https://developers.openai.com/api/docs/models/gpt-5.6-sol`.

## Calcul Decimal

```text
INPUT_MAX_COST  = 7000 × 4.00 / 1_000_000  = 0.028000 USD
OUTPUT_MAX_COST = 4096 × 20.00 / 1_000_000 = 0.081920 USD
BASE_MAX_COST   = 0.109920 USD
MARGIN_25_PCT   = 0.027480 USD
REQUESTED_CAP   = 0.137400 USD
```

Le plafond demandé ne constitue pas une autorisation. R2B reste fermé jusqu'à
l'approbation explicite du plan, du checksum, de l'appel unique et du plafond.
