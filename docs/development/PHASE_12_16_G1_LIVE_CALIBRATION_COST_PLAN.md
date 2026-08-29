# Phase 12.16-G1 — Plan de cout live de calibration pedagogique

## Etat ferme

- `PLAN_VERSION=12.16-g2-plan-v1`
- `CALL_MATRIX_SHA256=997e814f65ac7c5fc25da990cf286800fa6ca4edd761d821a6f6f59f5e2550ed`
- `OPENAI_CALL_COUNT=20`
- `ANTHROPIC_CALL_COUNT=76`
- `TOTAL_CALL_COUNT=96`
- `ESTIMATED_BASE_COST_USD=1.087576`
- `ESTIMATED_MAXIMUM_BEFORE_MARGIN_USD=3.277152`
- `ESTIMATED_MAX_COST_USD=4.096440`
- `SAFETY_MARGIN_MULTIPLIER=1.25`
- `APPROVAL_REQUIRED=TRUE`
- `LIVE_PROVIDER_CALL_COUNT=0`
- `LIVE_PROVIDER_COST_USD=0.000000`

Aucun montant n'est un seuil qualite ou release. Le maximum avec marge est le
plancher du plafond a approuver pour la matrice exacte; ce n'est pas une
autorisation de depense.

## Snapshot tarifaire officiel

Snapshot verifie le 2026-08-29, exprime en USD par million de tokens :

| Fournisseur | Modele | Entree | Cache lu | Sortie | Source | Note |
|---|---|---:|---:|---:|---|---|
| OpenAI | `gpt-5.6-terra` | 2.00 | 0.20 | 12.00 | [Comparaison officielle](https://developers.openai.com/api/docs/models/compare) | a reverifier avant G2 |
| OpenAI | `gpt-5.6-sol` | 4.00 | 0.40 | 20.00 | [Fiche officielle](https://developers.openai.com/api/docs/models/gpt-5.6-sol) | prix promotionnel affiche au moins jusqu'au 2026-11-21; a reverifier |
| Anthropic | `claude-sonnet-5` | 3.00 | 0.30 | 15.00 | [Tarification officielle](https://platform.claude.com/docs/en/about-claude/pricing) | tarif standard applicable le 2026-09-01, retenu par prudence a la place de la promotion |

Le calcul conservateur n'impute aucun token au tarif cache. Le tarif cache reste
documente pour rapprocher les usages reels en G2.

## Cardinalite par charge

| Fournisseur | Charge | Appels | Entree maximale | Sortie maximale | Cout maximal avant marge |
|---|---|---:|---:|---:|---:|
| OpenAI | generation | 8 | 48 000 | 16 384 | 0.377760 USD |
| OpenAI | transformation | 2 | 10 000 | 3 072 | 0.056864 USD |
| OpenAI | correction | 3 | 18 000 | 4 608 | 0.139872 USD |
| OpenAI | review | 7 | 49 000 | 7 168 | 0.294976 USD |
| Anthropic | scoring | 76 | 608 000 | 38 912 | 2.407680 USD |

La generation couvre cours, exercice, evaluation et QCM. La transformation
couvre une ressource. La correction couvre la remediation. La review couvre
exercice, evaluation, correction et QCM. Le scoring couvre les 48 couples
ancre/critere, 16 repetitions deterministes et 12 evaluations de sorties
selectionnees.

Les primaires sont Terra pour generation/transformation, Sol pour correction et
review, et Sonnet 5 pour scoring. Les fallbacks compares sont Sol pour la
generation et Terra pour correction/review. Le fallback degrade Sol du scoring
est seulement documente : il ne figure pas dans les 96 appels et aucune
implementation de scorer OpenAI n'est ajoutee en G1.

## Methode de calcul

- Base : plafond UTF-8 d'entree divise par quatre, arrondi au token superieur;
  moitie de la sortie maximale.
- Maximum : un octet UTF-8 compte comme un token d'entree, puis sortie maximale.
- Marge : multiplication du maximum par 1.25.
- Arithmetique : `Decimal`, sans flottant; arrondi monetaire par exces a six
  decimales.
- Le cout reel G2 devra utiliser les compteurs d'usage fournisseur, les appels,
  tokens entres, tokens caches, tokens sortis et latences par call ID.

## Conditions bloquantes avant G2

Le garde refuse l'appel si le checksum, le call ID, le fournisseur, le modele ou
le compte divergent; si le plafond approuve est absent ou inferieur a 4.096440
USD; si le cout observe le depasse; ou si l'appelant declare le credential
indisponible. G1 n'a inspecte, resolu ni affiche aucun credential reel.

Toute variation de prix, modele, corpus, borne, repetition ou charge produit une
nouvelle matrice et exige une nouvelle approbation explicite.

Les sorties brutes non revues portent leur call ID et un hash de contenu, sans
secret. Elles sont conservees au plus sept jours sous le chemin ignore, puis
supprimees apres production et controle du rapport agrege. Cette retention ne
concerne pas les rapports agreges suivis.
