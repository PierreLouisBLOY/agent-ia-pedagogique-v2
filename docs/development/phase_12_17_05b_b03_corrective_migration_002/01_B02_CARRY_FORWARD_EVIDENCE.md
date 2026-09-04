# Phase 12.17.5B-B03 — Carry-forward B02

## Gate et classification

```text
PHASE_12_17_05B_B02 = PASS
B02_MANIFEST = 11/11 PASS
B03_ENTRY_GATE = READY
BASELINE_HEAD = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
CARRY_FORWARD_CLASSIFICATION = APPROVED_B02_CARRY_FORWARD
CARRY_FORWARD_FILE_COUNT = 17
```

B02 n'était pas commitée à l'entrée de B03. Les 17 fichiers suivants ont donc été identifiés et hachés avant toute modification B03.

| Fichier B02 | SHA-256 PRE B03 |
|---|---|
| `backend/adapters/outbound/persistence/migrations.py` | `c7aac0c2eb9b9e9d94925f9e2170878335373fabb13c297c67f663a2e1d744e2` |
| `backend/infrastructure/composition/factories/sqlite.py` | `1483ceff7efd901217bc281e231b5d10cfa154956170c41863ee21fd14c44571` |
| `tests/unit/test_sqlite_seed_runtime_lifecycle.py` | `a364f4ed1cb9f9b1471a747f75b65e97e2a2cbb2c120ffc4b3a8d55d3e7f776d` |
| `tests/unit/test_multi_version_migration_runner.py` | `c5cd87e2e2d0ddb04aaba55366356bf0dc3450c5ff009ade76a68c43b0aa3dc9` |
| `tests/architecture/test_multi_version_migration_runner_fitness.py` | `ef1cb5328584f6471d54defb5676004f06291f702fd868af7cc9e1d91ce466f6` |
| `01_B02_SCOPE_RESOLUTION.md` | `d61652180c513172d8444817408f811bb3b8bac2552a6ae77b2ed45d5934aa71` |
| `02_RUNNER_BEFORE_AFTER.md` | `d0c4a8227ed1a340352d4db2d99b16565fb5e7c570185ba8ca07d24097ce9107` |
| `03_MIGRATION_REGISTRY_AND_CHECKSUM_CONTRACT.md` | `aed0e3d8f3646a80d9362d60e3502d5d80d15269c7008e48eb4b241a35737bea` |
| `04_001_COMPATIBILITY_EVIDENCE.md` | `c7e64023514debd4a06f7512b171f0a0ccb7f703a8e1d8d61f451ab4dad30f2c` |
| `05_TRANSACTION_AND_IDEMPOTENCE_EVIDENCE.md` | `d9fccd3afb44ca0c82c9ebace309c0da40740255e023ffb923e08c06529e4ac0` |
| `06_TARGETED_TEST_EVIDENCE.md` | `6dde43aa83dea94942f75183a7aae2cd3f475cd001916f2d5bce8c5280dff660` |
| `07_TYPING_AND_ARCHITECTURE_EVIDENCE.md` | `173b2fe4d4b8c6206ac746fd8aaf7bd28b40bfd1d35f544c0a38ad031d85042b` |
| `08_OWNER_DECISION_CONFORMANCE.md` | `225d36986a6a267abb7f745ff2d7029a5eaac3b4716d554ab3072b47e98664af` |
| `09_DIFF_AND_COMMIT_EVIDENCE.md` | `5bdc82311c113de4b190b80d019c64fe3acc91b78691e6649e726658c13b0540` |
| `10_B03_ENTRY_GATE.md` | `3c659867d703d2d45af1eb48988a107214dfad572d3f687bd5139d19fb006479` |
| `11_FINAL_HANDOFF.md` | `a92f526f0cc1a0c15b1619a9bcc23db54f65ec200c15f4d6a1ada022fe3ef838` |
| `MANIFEST_SHA256.txt` | `085035b8a3fc637252bb918301f1bf6fe93efcfce1b95a97b641da0a06be1635` |

La migration `001` avait avant B03 le SHA-256 canonique `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102`. Les autres éléments non suivis du worktree préexistaient à B02 et restent hors de ce carry-forward.
