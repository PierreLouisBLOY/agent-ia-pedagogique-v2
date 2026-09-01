# Phase 12.16-G2-V5 — Revue de sécurité du périmètre de transfert

## Frontière pré-transport

`TransferScopeGuard.authorize_before_transport()` est la dernière gate de données avant toute future résolution de credential ou construction de transport. Dans cette baseline, aucune de ces deux opérations n'est accessible par ce module.

La gate vérifie successivement :

1. l'absence de dérive matrix/contract/pricing/manifest/pilot/budget ;
2. les 21 `call_id` exacts dans l'ordre approuvé ;
3. la forme fermée de chaque observation absolue ou pairwise ;
4. l'allowlist du payload logique ;
5. l'absence de contenu sensible, chemin, email, téléphone, SQLite ou clé ;
6. le hash réel du scope contre `c65e6460…f0e93` ;
7. la présence ultérieure d'une autorisation de transfert sur ce hash exact ;
8. la présence ultérieure d'une autorisation live distincte.

Toute divergence produit une erreur fermée avant transport : `POST_APPROVAL_TECHNICAL_DRIFT`, `TRANSFER_FIELD_FORBIDDEN`, `TRANSFER_CONTENT_FORBIDDEN`, `TRANSFER_SCOPE_MISMATCH`, `TRANSFER_SCOPE_AUTHORIZATION_REQUIRED` ou `LIVE_EXECUTION_FORBIDDEN`.

## Réduction des outputs sélectionnés

Les deux outputs SCN-03 proviennent de fichiers raw locaux ignorés par Git. Le loader :

- vérifie le ledger V4.2 SHA-256 `7d173accfc7591998d7cab1625a6ad562f1e530fc24027aea5f322a9c44bd10a` ;
- exige un statut `COMPLETED` ;
- impose que le chemin résolu reste sous le répertoire raw V4.2 ;
- vérifie le SHA-256 individuel du fichier ;
- exige la forme exacte `outcome`, `sections`, `warnings`, `uncertainties` ;
- exige warnings et uncertainties vides ;
- extrait uniquement `sections[].code` et `sections[].text` ;
- recompose une projection pédagogique inférieure ou égale à 2 500 caractères.

Le chemin, le fichier JSON, les métadonnées runtime et les champs exclus ne traversent pas la frontière.

## État d'autorisation

`PEDAGOGICAL_TRANSFER_AUTHORIZED = FALSE`.

`LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`.

Même avec le bon hash, le guard refuse donc actuellement toute continuation vers le live.
