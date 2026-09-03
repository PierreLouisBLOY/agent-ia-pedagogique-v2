# Phase 12.17.4 — Preuve de clôture de la gate globale

```text
GLOBAL_SUITE_BEFORE_REMEDIATION = 4717 PASS, 25 SKIP, 7 FAIL
GLOBAL_SUITE_AFTER_REMEDIATION = 4725 PASS, 24 SKIP, 0 FAIL
GLOBAL_GATE = PASS
```

La preuve complète est figée dans
`phase_12_17_04_global_gate_remediation/07_GLOBAL_SUITE_REPLAY.md` et son
manifest 11/11. Elle est suffisante ; la clôture documentaire ne rejoue pas les
4 749 résultats.

La variation est comptable : sept échecs deviennent PASS et la gate seed B08,
désormais détectée par `PROJET_V2_CANONICAL_DB`, ajoute un PASS et retire un
skip. Les 21 anciennes gates SQLite ne lisant que l'alias legacy et les trois
gates explicitement opt-in restent conditionnelles. Aucun skip ou xfail n'a été
ajouté pour masquer un échec.

Contrôles de clôture rejoués sur HEAD :

```text
TARGETED_ARCHITECTURE = 17/17 PASS
ACTIVE_MYPY = 0/42 PASS
BACKEND_MYPY = 0/671 PASS
HISTORICAL_MYPY = 15 errors/10 files STABLE
RUFF_TARGETED = PASS
```

Les commits de remediation et B09 existent, et
`325ea3397507c0f3d94b9c1ef75c20ca47592d80` est le parent direct de
`68522d135bb36af98e5cbf44a8e4d3f1d595565f`, HEAD d'entrée de la clôture.
