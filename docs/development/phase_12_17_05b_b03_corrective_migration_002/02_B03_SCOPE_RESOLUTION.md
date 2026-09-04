# Phase 12.17.5B-B03 — Résolution du périmètre

```text
B03_CANONICAL_TITLE = Migration corrective 002
B03_SCOPE = Restore exactly five document invariants through migration 002
B03_OWNER_DECISION = DM-01 OPTION_A
B03_SQLITE_POLICY = TEMPORARY_TEST_DATABASES_ONLY
B03_COMMIT_POLICY = DISTINCT_COMMIT_REQUIRED_BY_PLAN
B04_CANONICAL_TITLE = Validation réelle de la chaîne et récupération
```

## Dans le périmètre

- `database/migrations/002_restore_document_invariants.sql` ;
- ajout de `002` au registre ordonné et allowlisté B02 ;
- postcondition spécifique aux cinq invariants ;
- tests fresh, existing `001`, replay, checksum, rollback, schéma et données ;
- copies temporaires et fixtures SQLite uniquement ;
- artefacts documentaires B03.

## Hors périmètre

- modification de `001` ;
- migration du seed ou d'un runtime utilisateur ;
- règle `resource_ref` ;
- sémantique `ACTIVE/CANONICAL` autre que le default historique requis ;
- `ContextOrigin` ;
- API, provider, secret ou Phase 12.17.6.

Les fichiers techniques attendus sont le SQL `002`, le catalogue et ses postconditions strictement nécessaires, les tests ciblés et le présent dossier de preuves. B04 reste non démarré.
