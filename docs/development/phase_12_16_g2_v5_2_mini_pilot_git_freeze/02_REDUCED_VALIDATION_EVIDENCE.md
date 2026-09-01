# Phase 12.16-G2-V5.2 — Validation réduite du gel

## Contrôles exécutés

| Contrôle | Résultat |
|---|---|
| Hashes approuvés parser/scorer/matrice/pricing/gate/scope | `PASS` |
| Manifeste correction V5.2, 14 entrées | `PASS` |
| Manifeste owner review, 13 entrées | `PASS` |
| Strong carry-forward, score 4 | `PASS` |
| Mixed carry-forward, score 0 | `PASS` |
| Allowlist exacte, 3 appels et 3 projections | `PASS` |
| Cardinalités logique/carry/new | `PASS — 5/2/3` |
| Somme exacte des plafonds | `PASS — 0.156800 USD` |
| Gate contract V5.2 | `PASS` |
| Binding fail-closed | `PASS` |
| `git diff --cached --check` avant commit | `FAIL — 14 blank-at-eof` |
| Provider calls | `0` |

## Allowlist vérifiée

| Call ID | Call-spec SHA-256 | Projection SHA-256 | Plafond |
|---|---|---|---:|
| `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1` | `a3646f66bd0d274cf30daf3024bbad5d204bb0d8182963460107243a0d81b707` | `8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc` | `0.045600 USD` |
| `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1` | `691794a224c1f440225dca29dddf34aff90c6556210c583263b006607509c196` | `e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8` | `0.055600 USD` |
| `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1` | `d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca` | `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d` | `0.055600 USD` |

```text
0.045600 + 0.055600 + 0.055600 = 0.156800 USD
```

## Outils Python

Le module et son test n'ont pas changé depuis l'approbation propriétaire ; leurs
hashes correspondent aux manifestes approuvés.

```text
RUFF = NOT_REQUIRED_NO_PYTHON_CHANGE
MYPY = NOT_REQUIRED_NO_PYTHON_CHANGE
COMPILEALL = NOT_REQUIRED_NO_PYTHON_CHANGE
GLOBAL_TEST_SUITE = NOT_RUN_BY_DESIGN
```

## Blocage

Les 14 constats concernent sept documents V5.1 de l'analyse de divergence et sept
documents de correction V5.2. Une normalisation modifierait des hashes déjà liés
par le manifeste propriétaire. La validation réduite est donc globalement `FAIL`
pour le gel Git, sans remettre en cause les validations sémantiques hors ligne.
