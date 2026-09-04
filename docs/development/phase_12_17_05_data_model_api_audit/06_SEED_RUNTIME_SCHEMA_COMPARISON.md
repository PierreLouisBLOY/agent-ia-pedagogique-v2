# Phase 12.17.5 — Comparaison structurelle seed/runtime

```text
SQLITE_ACCESSED = TRUE
SQLITE_WRITE_OPERATIONS = 0
SEED_PRE_POST_UNCHANGED = TRUE
RUNTIME_PRE_POST_UNCHANGED = TRUE
EXPECTED_SCHEMA_DIFFERENCES = 2
UNEXPECTED_SCHEMA_DIFFERENCES = 5
SCHEMA_ALIGNMENT_VERDICT = MISMATCH
```

## Méthode sûre

Le seed a été ouvert en `mode=ro&immutable=1`, le runtime en `mode=ro`, puis les
deux connexions ont reçu `PRAGMA query_only=ON`. L'inspection a porté sur
`sqlite_master`, `table_xinfo`, `index_list/index_info`, `foreign_key_list`, les
triggers et `version/checksum` du ledger. Aucune ligne pédagogique n'a été lue.

Les snapshots PRE/POST des fichiers principaux, WAL et SHM sont identiques.
Le seed principal reste à `105553920` octets et au SHA-256
`38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`.
Le runtime reste au SHA-256
`de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1`.

## Inventaire

| Base | Tables | Index explicites | Triggers | Vues |
|---|---:|---:|---:|---:|
| seed | 98 | 20 | 7 | 2 |
| runtime | 99 | 20 | 7 | 2 |

Toutes les entrées `sqlite_master` sont identiques sauf la table ledger et le
DDL de `document`. Les index et triggers sont identiques.

## Différences attendues

1. table runtime `_runtime_migration_ledger` avec la version `001` et le checksum
   `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102` ;
2. CHECK SHA-256 ajouté sur `document.sha256` par la migration 001.

## Différences inattendues

La reconstruction de `document` dans `001_document_sha256_check.sql` supprime :

1. `CHECK (size_bytes IS NULL OR size_bytes >= 0)` ;
2. `DEFAULT 'OTHER'` sur `document_type` ;
3. `DEFAULT 'fr'` sur `language_code` ;
4. `DEFAULT 'ACTIVE'` sur `document_status` ;
5. `DEFAULT CURRENT_TIMESTAMP` sur `created_at`.

Le premier écart rend la persistance moins sûre. Les quatre autres modifient le
contrat physique du seed sans décision owner. Les tests de migration vérifient
le SHA, le nombre de documents, les foreign keys, l'idempotence et le checksum,
mais pas la préservation complète du DDL.

Le verdict est donc `MISMATCH`. La remédiation devra être conçue et approuvée
dans un lot séparé, sur copie runtime fraîche, sans modifier le seed.
