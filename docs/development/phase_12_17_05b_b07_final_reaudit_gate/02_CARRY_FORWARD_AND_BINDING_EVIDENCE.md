# Phase 12.17.5B-B07 — Bindings et carry-forward

Les bindings d'entrée sont conformes :

| Binding | Valeur vérifiée |
|---|---|
| baseline | `576d6bd6dcf5082740c4192842b7c87ccbc1f246` |
| registre owner | `f987ce8a601275630bf2ec0298eb2c868d38411b3fad88d6e44082e3102551d1` |
| attestation owner | `224c2de87e75ce7c1aa50df246a9d7aa0b76edb053e91bfca6ff86a90d939b1e` |
| manifest B06 | `494ad2bfa766dee0a43ddd40eb08cb6289bb11aa32091074a5742998542a89e1` |
| seed | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` |

Les manifests B01→B06 totalisent 74 entrées, toutes vérifiées :

| Lot | Entrées | Écarts | SHA-256 manifest |
|---|---:|---:|---|
| B01 | 9 | 0 | `8cbda66b980d2486ce0a9bee74fe41084babe49412ea8ab3e31dae1154e904b4` |
| B02 | 11 | 0 | `085035b8a3fc637252bb918301f1bf6fe93efcfce1b95a97b641da0a06be1635` |
| B03 | 13 | 0 | `83b01fb534a591a3e4509cc35adfdf43cd9beff2a6ccff88566571ac8d33147c` |
| B04 | 14 | 0 | `ec27bac6cc1f3879b1db2fca7b1f1dc00535aff64ae3094970239bbdca0d3fb8` |
| B05 | 13 | 0 | `d8b26c52889da83ef4137f7b8b55956d5b12eaebccf0553e7bcc0cae80174c3a` |
| B06 | 14 | 0 | `494ad2bfa766dee0a43ddd40eb08cb6289bb11aa32091074a5742998542a89e1` |

Identités ré-auditées : `001=5b4c603d…b0102`,
`002=e43b6267…fe893`, `ResourceRef=f33c591d…634d`, modèle sémantique
B06 `4b3703d6…06e3`. Aucun drift n'est détecté.

```text
OWNER_DECISIONS_RESOLVED = 3/3
DM_01 = OPTION_A
DM_02 = OPTION_A
DM_03 = OPTION_B
CARRY_FORWARD_MANIFESTS = 6/6 PASS
CARRY_FORWARD_ENTRIES = 74/74 PASS
```
