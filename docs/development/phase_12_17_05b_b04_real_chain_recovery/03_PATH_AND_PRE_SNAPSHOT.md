# Phase 12.17.5B-B04 — Chemins et snapshot PRE

La configuration canonique résout le seed propriétaire fourni et la runtime
logique `%LOCALAPPDATA%/ProjetV2/runtime/base_pedagogique_v2.runtime.sqlite`.
Sous l'hôte Codex Windows, `Path.resolve()` applique la redirection MSIX de
`LocalAppData`; les chemins configuré et observé convergent après cette
normalisation. Le seed et la runtime restent physiquement distincts.

Les chemins absolus nominatifs ne sont pas recopiés dans Git.

```text
SEED_PATH = OWNER_OVERRIDE_REDACTED
RUNTIME_PATH = %LOCALAPPDATA%/ProjetV2/runtime/base_pedagogique_v2.runtime.sqlite
PATH_RESOLUTION = PASS_WITH_WINDOWS_MSIX_NORMALIZATION
SEED_RUNTIME_DISTINCT = TRUE
```

## Seed PRE

| Fichier | Présence | Taille | mtime UTC | SHA-256 |
|---|---:|---:|---|---|
| main | oui | 105553920 | `2026-08-22T00:13:57.5500000Z` | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` |
| WAL | oui | 0 | `2026-08-28T09:32:55.5450000Z` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| SHM | oui | 32768 | `2026-09-01T09:50:02.0070000Z` | `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` |
| journal | non | — | — | — |

## Runtime utilisateur PRE

| Fichier | Présence | Taille | mtime UTC | SHA-256 |
|---|---:|---:|---|---|
| main | oui | 105553920 | `2026-09-03T16:13:23.2043306Z` | `de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1` |
| WAL | oui | 0 | `2026-09-03T16:13:25.3952193Z` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| SHM | oui | 32768 | `2026-09-03T16:13:25.3960933Z` | `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb` |
| journal | non | — | — | — |

L'introspection `mode=ro&immutable=1` constate `001` seule dans le ledger,
15 lignes `document`, `integrity_check=ok`, `quick_check=ok` et zéro violation
FK. Les cinq invariants ciblés sont absents après `001`, tandis que le CHECK
SHA-256 est présent.
