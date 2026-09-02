# Phase 12.17.4E-B06 — Entrée et carry-forward

```text
PHASE_12_17_04E_B05 = PASS
B06_ENTRY_GATE = READY
HEAD_PRE_B06 = 2069f0ad0cf532946021716fcbb45709f0d6134d
PARENT_B05 = cdbcb0457487594745becd9055ac6479127b4ed3
B05_MANIFEST_SHA256 = d40d57e3d9ab919ec9c6d9278520a894e817f317b5c33118f789e84690aa25a9
B04_MANIFEST_SHA256 = e9079caa4dc918d66cdba0a4efa6493617c4731c39a0af329a940ce9d11d389f
B03_COMMIT = 711ebec196d7a2ea2bb0acf1cfd23812fd56e0e7
B02_COMMIT = 16d1e90ea8629fa419a93759e4c30ff1c0cb96f0
B01_MANIFEST_SHA256 = de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e
B01_CARRY_FORWARD = 11/11 PASS
```

Le snapshot PRE vérifie les 40 fichiers historiques contre leur
`sha256_current`, avec 7/7 écarts préexistants inchangés et aucune dérive
nouvelle. Les artefacts non suivis B01 et antérieurs ont été séparés du diff
B06 et n'ont pas été modifiés.

```text
ACTIVE_MYPY_PRE = 0 / 41 files
BACKEND_MYPY_PRE = 0 / 659 files
HISTORICAL_MYPY_PRE = 15 errors / 10 files
PROVIDER_CALLS_PRE = 0
```
