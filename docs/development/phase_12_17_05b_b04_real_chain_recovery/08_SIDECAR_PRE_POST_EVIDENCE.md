# Phase 12.17.5B-B04 — Sidecars PRE/POST

## Seed canonique

Le snapshot POST est strictement identique au snapshot PRE : main, WAL vide,
SHM et absence de journal conservent taille, mtime et SHA-256.

```text
SEED_MAIN_PRE_POST = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134 -> SAME
SEED_WAL_PRE_POST = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 -> SAME
SEED_SHM_PRE_POST = fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb -> SAME
SEED_JOURNAL_PRE_POST = ABSENT -> ABSENT
SEED_MODIFIED = FALSE
```

## Runtime utilisateur

Le snapshot POST est lui aussi strictement identique au snapshot PRE.

```text
USER_RUNTIME_MAIN_PRE_POST = de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1 -> SAME
USER_RUNTIME_WAL_PRE_POST = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 -> SAME
USER_RUNTIME_SHM_PRE_POST = fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb -> SAME
USER_RUNTIME_JOURNAL_PRE_POST = ABSENT -> ABSENT
USER_RUNTIME_MODIFIED = FALSE
```

## Copie contrôlée

Le mode de journal observé est `delete`. Juste avant le replay, aucun sidecar
n'est présent. Après le replay, le main reste byte-identique, le journal reste
absent, mais SQLite a matérialisé :

- un WAL vide de 0 octet, SHA-256 `e3b0c442...b855` ;
- un SHM de 32768 octets, SHA-256 `fd4c9fda...89eb`.

Ces fichiers sont confinés au répertoire temporaire et exclus de Git.
