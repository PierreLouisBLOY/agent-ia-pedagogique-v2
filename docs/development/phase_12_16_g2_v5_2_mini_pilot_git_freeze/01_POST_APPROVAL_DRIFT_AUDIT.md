# Phase 12.16-G2-V5.2 — Audit de dérive post-approbation

## Point de référence

- Parent Git approuvé : `c534b488276eabfa9f82b379282a043cdc0f4b65`.
- Branche : `phase12/12-16-provider-model-calibration`.
- Manifeste de revue propriétaire attendu et observé :
  `2231e5e92c89e27eebc908dbf08c218b9d92c8b2f5397c6d272e1b937ba9edc6`.
- Manifeste de correction V5.2 observé :
  `407f53697218ef0281ddcb08eda4bab29b74147a988eeaa2871692fcf664c23e`.

## Comparaison technique

| Élément | Identité approuvée / observée | Verdict |
|---|---|---|
| Parser V5.1 | `2037ce91acdf3859408effbe6a5a70d4ac84e6cf58b812b8d3ac9772817f057b` | `UNCHANGED` |
| Scorer | `a79928ba0aa402ffa012f353bd1a633b50c95e34eae368885c462690ec0b3344` | `UNCHANGED` |
| Matrice | `3c3a9eb418cb21ac44b657a49f0a3932443a5ea5c427bf32e359d680e2bc2d7c` | `UNCHANGED` |
| Pricing | `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8` | `UNCHANGED` |
| Gate V5.2 | `8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea` | `UNCHANGED` |
| Scope de transfert | `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93` | `UNCHANGED` |
| Module V5.2 | `e7cf1c4b0386f0b5134de5f9647616e972c1e6dcccf4c887a0ecf35bb9a20a15` | `UNCHANGED` |
| Tests V5.2 | `746ca3ec6a86adb85137299d8e80dbdb865dda9586c01a2a87cd675979a7b839` | `UNCHANGED` |

Les trois call-specs, les trois projections, les deux carry-forward et le budget
sont liés par ces manifestes et ont été revérifiés hors ligne.

## Écart de validation pré-commit

`git diff --cached --check` signale `14` fichiers approuvés avec une ligne vide
supplémentaire en fin de fichier. Cet écart existait dans les contenus liés par les
manifestes approuvés ; il ne constitue donc pas une dérive post-approbation. Le
corriger maintenant changerait leurs SHA-256 et invaliderait l'approbation exacte.
Le commit est par conséquent interdit sans lot correctif et nouvelle liaison
propriétaire.

## Hygiène du lot

- Fichiers à figer observés : `40` avant création du présent paquet.
- Extensions observées : `.md`, `.txt`, `.py` uniquement.
- Scan de secrets en clair : `PASS`.
- Base SQLite, raw provider output, credential ou binaire ajouté : `NONE`.
- Python modifié depuis l'approbation : `NON`.

```text
POST_APPROVAL_TECHNICAL_DRIFT = FALSE
BASELINE_GIT_FREEZE = NO_GO_VALIDATION
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
```
