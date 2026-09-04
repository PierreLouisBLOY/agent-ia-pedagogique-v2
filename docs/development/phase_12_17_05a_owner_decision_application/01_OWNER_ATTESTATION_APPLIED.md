# Phase 12.17.5A — Attestation propriétaire appliquée

## Attestation vérifiée

```text
OWNER_DECISION_RESOLUTION_12_17_05A = APPROVED
BASELINE_COMMIT = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
OWNER_DECISION_REGISTER_SHA256 = f987ce8a601275630bf2ec0298eb2c868d38411b3fad88d6e44082e3102551d1

DM-01 = OPTION_A
DM-02 = OPTION_A
DM-03 = OPTION_B

OWNER_NAME_OR_ROLE = PROJECT_OWNER
OWNER_ATTESTATION = APPROVED
OWNER_ATTESTATION_TIMESTAMP = 2026-09-03T21:08:17+02:00
```

## Résolution appliquée

- `DM-01 / OPTION_A` : conserver `001` immuable, généraliser le runner ordonné puis créer une migration corrective `002`.
- `DM-02 / OPTION_A` : adopter un `resource_ref` opaque sûr conforme à `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`.
- `DM-03 / OPTION_B` : séparer disponibilité opérationnelle et canonicalité, sans backfill inventé et avec toute migration éventuelle distincte de `002`.

Les trois choix existent dans le registre lié et correspondent aux recommandations enregistrées. Le timestamp est un ISO-8601 avec offset valide; il se normalise en `2026-09-03T19:08:17Z`.

## Limites d'autorité

Cette attestation autorise la sélection des trois options et l'ouverture de la gate d'entrée 12.17.5B. Elle n'autorise pas, à elle seule :

- l'exécution de `002` ou d'une autre migration ;
- une écriture sur le seed ou le runtime SQLite ;
- un backfill `ACTIVE/CANONICAL` ;
- une migration `ContextOrigin` ;
- l'implémentation d'un endpoint ;
- un appel fournisseur ;
- le démarrage de 12.17.6.

```text
OWNER_DECISION_RESOLUTION = APPROVED
OWNER_DECISION_RESOLUTION_APPLIED = TRUE
OWNER_DECISIONS_RESOLVED = 3/3
```
