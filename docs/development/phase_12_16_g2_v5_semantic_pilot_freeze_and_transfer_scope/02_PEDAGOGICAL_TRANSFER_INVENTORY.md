# Phase 12.16-G2-V5 — Inventaire des transferts pédagogiques

## Scope canonique

`PEDAGOGICAL_TRANSFER_SCOPE_SHA256 = c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93`.

Le hash couvre la sélection et l'ordre des 21 calls, les champs, les instructions, les schémas, les rubriques et le contenu exact des projections. Il change si un contenu ou un champ transférable change.

## Catégories

| `PROJECTION_NAME` | Source locale | Transformation | Payloads | Occurrences de projection | Volume UTF-8 estimé | Template SHA-256 |
|---|---|---|---:|---:|---:|---|
| `V5_ABSOLUTE_ANCHOR_OBSERVATION` | `anchor_corpus_v4.py` | anchor V4 vers observation V5 bornée ; tier et attente retirés | 15 | 15 | 60 037 octets | `53f38a9927ba438d9fb8fcf0c0bf9149a48d6b3d77078baf383550533fc673a4` |
| `V5_PAIRWISE_ANCHOR_OBSERVATION` | `anchor_corpus_v4.py` | deux anchors vers comparaison directe aveugle | 5 | 10 | 21 100 octets | `a9d6d3ab144f6c8f2f3709479e4c30d7c53eafabce9a950212c7d32627339200` |
| `V5_PAIRWISE_SELECTED_OUTPUT_OBSERVATION` | raw local V4.2 ignoré par Git | JSON vérifié, extraction exclusive de `sections[code,text]`, deux projections bornées | 1 | 2 | 4 788 octets | `b512293cc313cd06b71af2cde945c042b280ffc9a9957ed4a90b26f92ea959e8` |

Total : 21 payloads logiques, 27 occurrences de projections, 85 925 octets estimés. Le fournisseur unique est Anthropic. La finalité exclusive est le scoring sémantique du pilote robuste V5.

## Champs inclus

Le payload logique envoyé contient exactement :

- `model` ;
- `max_output_tokens` ;
- `system` ;
- `input.contract_version` ;
- identifiant opaque d'observation ou de comparaison ;
- `input.scenario` ;
- `input.criterion` avec rubrique evidence-first ;
- une ou deux projections candidates bornées ;
- `output_schema` fermé.

## Champs exclus

Sont absents des payloads : tier, score ou décision attendus, identité fournisseur/producteur des candidats, chemin local, raw output path, fichier brut, warnings, uncertainties, outcome technique, credentials, secrets, données personnelles, SQLite, document source complet et contenu hors scoring.

Les trois catégories ont `PERSONAL_DATA_PRESENT = FALSE` et `SECRETS_PRESENT = FALSE` après validation de l'allowlist et scan défensif.
