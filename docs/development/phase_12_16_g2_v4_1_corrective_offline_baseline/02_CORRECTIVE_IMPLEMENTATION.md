# Phase 12.16-G2-V4.1 — Implémentation corrective

## Frontière versionnée

- `tests/calibration/pedagogical/call_plan_v4_1.py` porte la matrice corrective.
- `tests/calibration/pedagogical/live_runner_v4_1.py` porte le runner, le ledger et le reporting correctifs.
- Le runner et la matrice V4 exécutés restent inchangés et disponibles comme preuve historique au commit `2b378114...c1c76`.
- Les sorties V4.1 utilisent `artifacts/calibration/12.16-g2-v4-1/`; elles ne peuvent pas écraser le ledger V4.

## Contrats de sortie

- Anthropic scorer : source canonique `_MAX_OUTPUT_TOKENS = 2048` dans le scorer historique byte-exact, réexportée par la matrice V4.1 sous `ANTHROPIC_SCORER_REQUIRED_OUTPUT_TOKENS` sans duplication de valeur.
- OpenAI Review : source canonique V4.1 `OPENAI_REVIEW_MAX_OUTPUT_TOKENS = 2048`.
- La projection canonique de matrice contient `max_output_tokens`; une variation change donc nécessairement le Matrix SHA.
- `validate_call_matrix_contracts` est exécuté par le calcul du SHA, le calcul de coût, le budget guard et le préflight live.

## Diagnostic Review persistant

Les champs sûrs suivants sont initialisés, validés et persistés atomiquement par appel :

- `provider_response_status` ;
- `incomplete_reason` ;
- `finish_reason` ;
- `output_tokens` ;
- `private_diagnostic_code` ;
- `parse_error_category` ;
- `structured_output_validation`.

Les prompts, sorties brutes, credentials, headers et identifiants fournisseur ne sont pas copiés dans les rapports sûrs.

## Provenance runtime

`RuntimeAuthorizationProvenance` porte : commit, matrice, pricing, nombre maximal d'appels, plafond et source d'attestation. Le préflight compare ces valeurs à la baseline courante avant toute vérification de credential. Le ledger refuse une reprise avec une provenance différente.

## Canaries et fermeture

Les trois familles restent canary-first : génération/correction OpenAI, Review OpenAI et scorer Anthropic. L'état et la catégorie d'échec restent dans le ledger atomique. Un canary bloqué interdit tout fanout de sa famille et une reprise ne réémet aucun appel terminal.

RUNTIME_ROUTE_CHANGE = NONE

CORPUS_CHANGE = NONE

PREVIOUS_EVIDENCE_CHANGE = NONE
