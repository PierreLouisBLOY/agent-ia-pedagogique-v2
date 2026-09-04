# Phase 12.17.4E-B01 — Registre des dérives préexistantes

Les sept écarts ci-dessous existaient avant B01. Ils proviennent du lot de
remédiation de typage 12.17.2A. Leur hash courant est la baseline protégée par
B01 ; le hash historique demeure une référence de provenance et ne doit pas
être restauré rétroactivement.

| ID | Chemin | SHA-256 de référence historique | SHA-256 courant figé | Origine | Réparation rétroactive |
|---|---|---|---|---|---|
| HIST-014 | `tests/calibration/pedagogical/protocol.py` | `13c52073886016a564d36a5a942ce8c8bd21615530b222910375b713669a69e3` | `ab01dfdd6b1b0e704d8465d56a30e686f40f4b5a054780710db3cd55cce6e887` | 12.17.2A typing remediation | FORBIDDEN |
| HIST-020 | `tests/calibration/pedagogical/repair_tranche_v4_2.py` | `35e8598a6fedaac79d0f4ffba9db47a84056900db3f36aceb837b6eb8c4897a1` | `d1e5b40dd1437aad38f5da0db4797e2670da953ee554f09f4aa1b1f078e9a6b6` | 12.17.2A typing remediation | FORBIDDEN |
| HIST-022 | `tests/calibration/pedagogical/review_contract_v4_2.py` | `60cc9e407fe1010f089ee38a7ef06719e15fc4ad84e6f3c7c568fa66859aaba5` | `81cc15e087169290133c7ecd79ba7c7043935673522229a1d861e86e28ef1a9e` | 12.17.2A typing remediation | FORBIDDEN |
| HIST-024 | `tests/calibration/pedagogical/semantic_gate_v5_2.py` | `e7cf1c4b0386f0b5134de5f9647616e972c1e6dcccf4c887a0ecf35bb9a20a15` | `f4eaddf64eb255edcfdd011a763cefe83afe96c97a47f90519952ae2bfe02bb3` | 12.17.2A typing remediation | FORBIDDEN |
| HIST-025 | `tests/calibration/pedagogical/semantic_integration_v5.py` | `2e4a7539cc92765421293068f5d621ed05e6e8855cd66e66ff9332579938c011` | `4347094a9fa31787ca8fc7eb31c848151506a5197457e1ffc4d6e114031b8ca4` | 12.17.2A typing remediation | FORBIDDEN |
| HIST-027 | `tests/calibration/pedagogical/semantic_mini_pilot_v5_1.py` | `0c9db6612b2995291d294593906ba8c1361b7c73068d3a60da8fcc7dc2d1280b` | `33eb2a9e085238f88f7f36ae3ca3f51d08301e4accbc4eafad4fc5aaf6c19a1c` | 12.17.2A typing remediation | FORBIDDEN |
| HIST-029 | `tests/calibration/pedagogical/semantic_pilot_freeze_v5.py` | `49288def5b1d0a512a544c222fa85941a979e4693671090318b2c926191c627b` | `eaed483486a00a7937832795f26b29b1adbc344c4578385fcab33189c5c4a2c1` | 12.17.2A typing remediation | FORBIDDEN |

Invariants :

- `PREEXISTING_DRIFT_COUNT = 7` ;
- aucune dérive n'a été créée ou corrigée dans B01 ;
- aucune modification silencieuse des fichiers historiques n'est permise ;
- toute évolution future exige un lot versionné distinct et une nouvelle
  décision explicite ;
- `RETROACTIVE_REPAIR = FORBIDDEN` pour les sept entrées.
