# Phase 12.17.5B-B04 — Carry-forward B02 et B03

## Gates d'entrée

```text
BASELINE_COMMIT = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
B03_STATUS = PASS
B04_ENTRY_GATE = READY
B04_CANONICAL_TITLE = Validation réelle de la chaîne et récupération
DM_01 = OPTION_A
DM_02 = OPTION_A
DM_03 = OPTION_B
DECISION_REGISTER_SHA256 = f987ce8a601275630bf2ec0298eb2c868d38411b3fad88d6e44082e3102551d1
OWNER_ATTESTATION_SHA256 = 224c2de87e75ce7c1aa50df246a9d7aa0b76edb053e91bfca6ff86a90d939b1e
```

Les manifests documentaires ont été recalculés avant toute action B04 :

| Carry-forward | Vérification | SHA-256 du manifest |
|---|---:|---|
| B02 | `11/11 PASS` | `085035b8a3fc637252bb918301f1bf6fe93efcfce1b95a97b641da0a06be1635` |
| B03 | `13/13 PASS` | `83b01fb534a591a3e4509cc35adfdf43cd9beff2a6ccff88566571ac8d33147c` |

Les identités techniques actives sont celles du carry-forward approuvé :

```text
MIGRATION_001_SHA256 = 5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
MIGRATION_002_SHA256 = e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893
RUNNER_SHA256 = 50ad9e858adfa9099226b36c82f640d964bda9aa5affdf68dc26d1154e5132c8
B02_B03_CARRY_FORWARD_VERIFIED = TRUE
```

B02 et B03 restent non commités. Ils ont été préservés sans réécriture
rétroactive ni confusion avec les preuves B04.
