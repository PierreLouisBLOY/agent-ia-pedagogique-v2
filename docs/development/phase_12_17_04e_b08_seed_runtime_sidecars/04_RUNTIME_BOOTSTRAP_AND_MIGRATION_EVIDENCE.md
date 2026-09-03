# Phase 12.17.4E-B08 — Bootstrap runtime et migrations

La runtime absente a été copiée vers un fichier temporaire du même répertoire,
authentifiée contre le seed avant migration, migrée puis publiée par création
atomique d'un nom frais. Aucun remplacement de destination n'est possible.

```text
RUNTIME_CREATED = TRUE
RUNTIME_EXISTING_PRE = FALSE
RUNTIME_SIZE = 105553920
RUNTIME_SHA256 = de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1
RUNTIME_INVENTORY = 98 tables / 20 explicit indexes / 7 triggers / 2 views
RUNTIME_INTEGRITY = ok
RUNTIME_QUICK_CHECK = ok
RUNTIME_FOREIGN_KEY_VIOLATIONS = 0
RUNTIME_JOURNAL_MODE = wal
DOCUMENTS_PRE_POST_MIGRATION = 15 -> 15
```

La seule migration autorisée et appliquée est `001`, checksum
`5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102`.
Le ledger runtime contient exactement cette identité.

Un second bootstrap a pris la branche runtime existante : aucune copie, aucune
migration rejouée, hash et mtime du fichier principal identiques. Le backup et
la restauration vers une cible fraîche ont été validés par hash,
integrity/quick et FK dans la gate réelle temporaire ; aucun backup de test
n'est entré dans Git.
