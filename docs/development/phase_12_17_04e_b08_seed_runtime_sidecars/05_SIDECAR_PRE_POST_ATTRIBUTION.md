# Phase 12.17.4E-B08 — Sidecars PRE/POST et attribution

## Seed

| Sidecar | PRE | POST | Identité |
|---|---|---|---|
| WAL | présent, 0 octet, SHA vide | identique | inchangée |
| SHM | présent, 32768 octets, SHA `fd4c9fda...9389eb` | identique | inchangée |
| journal | absent | absent | inchangée |

Les WAL/SHM seed préexistaient au snapshot B08. Leur origine historique n'est
pas réattribuée ; l'absence de création ou modification par B08 est en revanche
déterministe.

## Runtime

La runtime et ses sidecars étaient absents en PRE. Pendant le bootstrap en mode
WAL, un WAL vide et un SHM de 32768 octets ont été observés. Après checkpoint et
fermeture ils étaient absents ; les lectures de validation suivantes les ont
recréés à côté de la runtime, avec WAL vide et SHM de 32768 octets. Cette
création est attribuée au cycle B08 et constitue un comportement runtime prévu.

```text
SEED_SIDECAR_CREATED_BY_B08 = FALSE
SEED_SIDECAR_MODIFIED_BY_B08 = FALSE
RUNTIME_SIDECARS = EXPECTED_RUNTIME_BEHAVIOR
SQLITE_SIDECAR_ATTRIBUTION_UNDETERMINED = CLOSED
```
