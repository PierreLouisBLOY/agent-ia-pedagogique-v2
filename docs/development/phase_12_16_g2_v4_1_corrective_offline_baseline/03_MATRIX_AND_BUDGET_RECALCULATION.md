# Phase 12.16-G2-V4.1 — Matrice et budget

## Identité corrective

- Plan : `12.16-g2-v4.1-plan-v1`.
- Matrix SHA-256 : `94eb067ac7dd8498eeb2605ee506315fd0c831259f454555ecac88acbe94403a`.
- Pricing SHA-256 : `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`.
- Appels : `102` (`20` OpenAI, `82` Anthropic).
- Modèles : `10` gpt-5.6-terra, `10` gpt-5.6-sol, `82` claude-sonnet-5.
- Workloads : `8` generation, `2` transformation, `3` correction, `7` review, `82` scoring.
- Anchors V4 : `24/24`.
- Références au plan V4 historique : `0`.
- Comparaisons pairwise effectives : `6`.

## Budgets de sortie

- OpenAI total maximal : `38400` tokens.
- Anthropic total maximal : `167936` tokens (`82 × 2048`).
- Total maximal : `206336` tokens.
- Entrées maximales conservatrices : `781000` tokens, selon la règle historique `1 octet UTF-8 = 1 token` au maximum.

## Formule canonique

Pour chaque appel et le tarif canonique du modèle :

`coût_max_appel = (input_upper_bound × tarif_input + max_output_tokens × tarif_output) / 1_000_000`

Le plafond technique est :

`ceil_6_decimales(somme(coût_max_appel) × 1.25)`

Résultats :

- entrée estimée : `195250` tokens ;
- sortie estimée : `103168` tokens ;
- coût de base estimé : `1.570904 USD` ;
- coût maximal avant marge : `3.987808 USD` ;
- marge de sécurité : `1.25` ;
- `PROPOSED_TECHNICAL_CEILING_USD = 4.984760`.

Le pricing canonique n'a pas changé. Le précédent plafond propriétaire `3.251640 USD` est caduc et n'est pas réutilisé.

OWNER_CONFIGURATION_APPROVAL = APPROVED

APPROVED_HARD_CEILING_USD = 4.984760

Cette approbation de configuration n'autorise aucun appel fournisseur.
