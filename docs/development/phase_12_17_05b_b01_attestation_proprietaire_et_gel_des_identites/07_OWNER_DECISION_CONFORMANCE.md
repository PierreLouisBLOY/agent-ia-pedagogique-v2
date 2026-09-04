# Phase 12.17.5B-B01 — Conformité aux décisions propriétaire

## Binding

```text
DECISION_REGISTER_SHA256 = f987ce8a601275630bf2ec0298eb2c868d38411b3fad88d6e44082e3102551d1
OWNER_ATTESTATION_SHA256 = 224c2de87e75ce7c1aa50df246a9d7aa0b76edb053e91bfca6ff86a90d939b1e
OWNER_DECISIONS_RESOLVED = 3/3
```

## Conformité B01

| Décision | Choix | Effet dans B01 | Anticipation interdite vérifiée |
|---|---|---|---|
| `DM-01` | `OPTION_A` | gel de `001` immuable et de la séquence runner B02 / corrective B03 | runner inchangé, `002` absente |
| `DM-02` | `OPTION_A` | gel du contrat regex pour exécution B05 | aucune règle de code ajoutée |
| `DM-03` | `OPTION_B` | gel de la séparation disponibilité/canonicalité pour B06 | aucun backfill, colonne ou migration |

`ContextOrigin` reste hors des trois décisions :

```text
CONTEXT_ORIGIN = UNKNOWN
CONTEXT_ORIGIN_MIGRATION_AUTHORIZED = FALSE
```

Les 1 399 ressources `ACTIVE` ne sont ni relues ni modifiées dans B01. Aucune décision n'est étendue au-delà de son périmètre approuvé.
