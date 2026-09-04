# Phase 12.17.4E-B01 — Binding ADR-P12-068

## Identité

```text
ADR_ID = ADR-P12-068
ADR_TITLE = Séparation runtime actif / preuves historiques de calibration
ADR_STATUS = ACCEPTED
ADR_PATH = architecture/adr/ADR-P12-068-active-calibration-tooling-boundary.md
ADR_SHA256 = 4cac693a66d09bf5708b050eceeb82f9e249dbd1f32537d6b312cba8c4a6ffbd
```

## Décision centrale

```text
ACTIVE_RUNTIME != HISTORICAL_CALIBRATION_EVIDENCE
```

L'ADR fixe les invariants demandés : aucun import actif vers les preuves
protégées, aucune implémentation active exclusivement sous `tests/`, aucun
fichier historique modifié, une génération runner/parser active cible,
`MYPY-001` résolu par isolation et Phase 12.16 non réouverte.

## Limite

Le statut `ACCEPTED` approuve une frontière et un ordre d'exécution. Il ne crée
aucun package actif et n'autorise pas B02. Le hash ci-dessus est inclus dans le
manifest B01 et devra être fourni comme entrée du prochain lot.

```text
ADR_P12_068_BINDING = PASS
```
