# Phase 12.16-G2-V4.1 — Clôture des causes racines

## Baseline live précédente immuable

- Commit exécuté : `2b378114b2f439307a85007981f2239d14461c76`.
- Matrice exécutée : `f159f200bf45d9df631007dd742e6ea9cc44a3e487ed76180f92c1392cd6245e`.
- Pricing : `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`.
- Verdict : `CALIBRATION_INCONCLUSIVE`.
- Autorisation live précédente : `CONSUMED`.
- Ledger durable précédent : `6095374537d429973e750beddcb477e28bbf84f0c2cd1d34162985f62410d536`.

Aucun artefact, corpus, formulaire, attestation ou résultat du run précédent n'est modifié par V4.1. La correction est portée par des modules et des chemins versionnés distincts.

## E1 — Anthropic scorer

Cause racine : la matrice V4 construisait les 82 appels de scoring avec `max_output_tokens = 512`, tandis que le contrat canonique du scorer exigeait `2048`. La construction du scorer échouait donc localement avec `INVALID_PROVIDER_CONFIGURATION`, avant credential et transport.

Clôture V4.1 : la constante canonique existante `_MAX_OUTPUT_TOKENS = 2048` du scorer gelé reste l'unique source fonctionnelle. La matrice la réexporte sous le nom explicite `ANTHROPIC_SCORER_REQUIRED_OUTPUT_TOKENS` et `validate_call_matrix_contracts` refuse tout scoring inférieur, sans modifier le scorer historique byte-exact.

## E2 — OpenAI Review

Cause racine : les sept appels Review étaient plafonnés à `1024`. Le canary live a consommé exactement cette limite puis a produit `OPENAI_REVIEW_INVALID_RESPONSE`. Le ledger V4 ne persistait ni le statut fournisseur, ni l'équivalent d'`incomplete_details`, ni la catégorie de parsing ; une troncature restait donc probable mais non prouvée.

Clôture V4.1 : le budget canonique Review est `2048`. Le résultat et le ledger conservent désormais le statut fournisseur, l'incomplete reason, le finish reason s'il existe, les tokens de sortie, le diagnostic privé sûr, la catégorie de parsing et l'état de validation structurée. La classification distingue strictement :

- `OUTPUT_TRUNCATED_CONFIRMED` avec preuve fournisseur explicite ;
- `OUTPUT_TRUNCATION_SUSPECTED` lorsque seule l'atteinte de la limite est observée ;
- `STRUCTURED_OUTPUT_INVALID_OTHER` sans preuve de longueur.

## E3 — Provenance d'autorisation

Cause racine : le rapport V4 lisait la constante statique `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = False`, même lorsqu'une autorisation runtime distincte avait ouvert la gate.

Clôture V4.1 : le ledger et le rapport séparent `baseline_live_authorization_default` de `runtime_live_authorization_effective` et conservent les paramètres exacts de l'attestation runtime. Une génération offline reste explicitement `PENDING`; un run effectivement autorisé n'affiche plus une approbation en attente.

ROOT_CAUSE_CLOSURE = PASS
