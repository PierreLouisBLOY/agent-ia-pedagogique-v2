# Phase 12.17.8-B02 — État PRE filesystem et SQLite

Les localisateurs privés sont volontairement remplacés par des rôles stables.

| Élément | État PRE |
|---|---|
| HEAD | `d20428d2c3060546a2c40fc59f0e8b7026be707f` |
| Worktree | propre |
| Seed | `<OWNER_SUPPLIED_CANONICAL_SEED>`, présent |
| Seed SHA-256 / taille | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` / `105553920` |
| Sidecars seed | WAL présent; SHM présent; journal absent; tous préexistants |
| Permission seed | ACL Windows externe héritée, inspectée; jamais modifiée par B02 |
| Runtime utilisateur | `<LOCAL_APP_DATA_RUNTIME>`, présent, distinct du seed, volume local `C:` |
| Runtime SHA-256 / taille | `de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1` / `105553920` |
| Sidecars runtime | WAL présent; SHM présent; journal absent |
| Configuration seed | alias historique seed injecté; valeur non enregistrée |
| Configuration runtime | alias runtime V2 et historique non définis |
| Fallback runtime Drive/OneDrive/G: | absent |
| Temp de validation | temp système, hors dépôt |

Le runtime utilisateur et ses ACL sont seulement inventoriés. Toutes les preuves mutantes sont exécutées sur des copies temporaires privées.

```text
SEED_WRITES_PRE = 0
USER_RUNTIME_DESTRUCTIVE_WRITES_PRE = 0
PROVIDER_CALLS_PRE = 0
```
