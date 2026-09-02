# Phase 12.17.4E-B02 — Carry-forward B01

## Gate d'entrée

```text
PHASE_12_17_04E_B01 = PASS
B02_ENTRY_GATE = READY
B01_MANIFEST_SHA256 = de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e
B01_MANIFEST_ENTRIES = 8/8 PASS
B01_ARCHITECTURE_GUARD = 5/5 PASS
APPROVED_B01_CARRY_FORWARD_COUNT = 11
```

## Snapshot PRE-B02

| SHA-256 | Chemin |
|---|---|
| `4cac693a66d09bf5708b050eceeb82f9e249dbd1f32537d6b312cba8c4a6ffbd` | `architecture/adr/ADR-P12-068-active-calibration-tooling-boundary.md` |
| `43f91d0ea1d631588b76c9646edb8ddba16a771393694d4aa8cda95b2c2e2309` | `tests/architecture/test_calibration_tooling_boundary.py` |
| `8ab73e08612d75d1e13aa79b92c8d09f4099eb4aec45f6bb9bf1836f3dbb6c20` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/01_OWNER_DESIGN_APPROVAL_BINDING.md` |
| `cdcc93e1262a5b1eff48ad8657c37e59f6946c16a83a0af549b39265da5d1162` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/02_ADR_P12_068_BINDING.md` |
| `b3083ee1cc8bfdde863ba812eb10fa97d10a69863a49af8527ada8e9b818878b` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/03_HISTORICAL_HASH_FREEZE.json` |
| `b46fce19d1761d539b7d326899c04eca8094f8b6610e3dceaee30ef0d2bf7847` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/04_PRE_POST_HASH_EVIDENCE.md` |
| `eba2a9993fab5904a0fd7a75e4fe4e496c13f57a2c262723dc6a6478f2d6ef20` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/05_PREEXISTING_DRIFT_REGISTER.md` |
| `67eca7eab5bd9c443e721a028660a033dce3c1aa423592170e6134954a82f65e` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/06_B01_VALIDATION.md` |
| `1c9edc2f86e5c161644b7103d1bf603c42c0748db174d7c27458d417062172d7` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/07_B02_ENTRY_GATE.md` |
| `259eb63591a8fcdf20c6403c891626535eef2a5cc4407f6495d8ace7dbb80889` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/08_FINAL_HANDOFF.md` |
| `de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e` | `docs/development/phase_12_17_04e_b01_design_approval_hash_freeze/MANIFEST_SHA256.txt` |

Ces fichiers sont classés `APPROVED_B01_CARRY_FORWARD`. Les autres répertoires
12.17.3 et le design 12.17.4 déjà présents mais non suivis ont été recensés
comme état antérieur distinct ; ils ne font pas partie du diff B02.

La tentative de commit séparé B01 a été abandonnée sans commit : deux lignes
vides finales déjà incluses dans le manifeste approuvé étaient signalées par
`git diff --cached --check`. Les corriger aurait invalidé le hash d'entrée B02.
B01 est donc conservé octet-identique, hors index, et n'est pas mélangé au
commit B02.

`B01_CARRY_FORWARD_VERIFIED = TRUE`
