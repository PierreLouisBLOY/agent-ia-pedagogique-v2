# CP645 — intégration du seed canonique

## Actif
- Fichier : `CP645_FINALISATION_628_SUR_628.sqlite`
- SHA-256 : `9d64d15e9c246924edeff16e7bbb5fb7a53791fc2ddf217541824771b34053e1`
- Taille : 227557376 octets
- 628 notions canoniques
- 210 formules `APPROVED`
- 121 tables, 23 index explicites, 7 triggers, 11 views
- `integrity_check = ok`, `quick_check = ok`, 0 erreur FK

## Installation locale
Le binaire reste hors Git.

Sous Windows, le contrat existant attend par défaut :
`%LOCALAPPDATA%\ProjetV2\seed\base_pedagogique_v2.sqlite`

Variables publiques :
- `PROJET_V2_CANONICAL_DB`
- `PROJET_V2_RUNTIME_DB`

La runtime doit être distincte du seed. Le bootstrap doit copier le seed vers la runtime puis appliquer les migrations allowlistées. Le seed ne doit jamais être migré.

## Écart à corriger
`backend/adapters/outbound/persistence/migrations.py` authentifie encore l'ancien seed :
- 105553920 octets
- SHA `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`
- 98 tables, 20 index, 7 triggers, 2 views

Mettre à jour l'identité vers CP645 après audit du diff de schéma. Ne pas assouplir l'authentification.

## Migrations
Les migrations 001 et 002 ont été exécutées hors dépôt sur une copie CP645 :
- 001 : PASS
- 002 : PASS
- 67 lignes `document` avant/après
- seed byte-identique avant/après

Ce smoke test ne remplace pas le replay du runner réel.

## Tests minimum
Rejouer :
- tests seed/runtime SQLite ;
- tests path configuration ;
- tests evidence adapters ;
- tests local boundary ;
- tests vocabulary mappings ;
- tests R5 concernés ;
- lint/typecheck documentés.

Ne déclarer PASS que pour des commandes réellement exécutées.
