# Preuves de tests et gates

```text
TARGETED_CORE = 63 passed
EXPANDED_OBSERVABILITY_CALIBRATION_SQLITE = 404 passed, 1 skipped
EXPANDED_SKIP_REASON = symbolic links unavailable on Windows
GLOBAL_SUITE = 4857 passed, 5 skipped, 0 failed / 813.07 seconds
RUFF = PASS
MYPY_BACKEND_AND_CALIBRATION = PASS / 708 source files
COMPILEALL_BACKEND_AND_CALIBRATION = PASS
GIT_DIFF_CHECK = PASS
```

Les tests prouvent : NDJSON valide et borné, champs communs exacts, refus des données sensibles, rotation à 5 MiB, cinq fichiers maximum, purge strictement après quatorze jours, permissions privées, racine hors dépôt, flush shutdown sous deux secondes, failure isolation, correlation id, tous les signaux runtime/HTTP/SQLite/provider/security et absence de fuite de message d'exception ou chemin.

L'unique écart rencontré pendant la régression élargie concernait l'appel monkeypatché historique de `build_sqlite_runtime` lorsque l'observabilité optionnelle valait `None`. La compatibilité d'appel historique a été restaurée ; la relance élargie a ensuite passé 404 tests.

Les cinq skips globaux sont justifiés : trois gates explicitement conditionnées par une autorisation d'exécution absente, et deux tests de liens symboliques non disponibles sur cette plateforme Windows.

Le contrôle des 36 chemins B03 ne trouve aucun log, NDJSON, SQLite, sidecar, fichier temporaire ou bytecode nouveau. Un scan physique plus large rencontre des arbres `.tmp` ignorés et préexistants, dont certains sont inaccessibles par ACL ; cette dette historique reste explicitement affectée à CF-TEMP-LOCAL-001/B06. Elle n'a été ni créée ni supprimée par B03.
