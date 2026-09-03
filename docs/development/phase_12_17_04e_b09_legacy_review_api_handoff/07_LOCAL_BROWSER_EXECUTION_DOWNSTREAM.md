# Phase 12.17.4E-B09 — Contrainte navigateur local aval

```text
V2_EXECUTION_MODE = LOCAL_BROWSER
BACKEND_BIND_DEFAULT = LOOPBACK_ONLY
GOOGLE_DRIVE_RUNTIME_DEPENDENCY = NONE
WINDOWS_EXE_REQUIRED_FOR_V2 = FALSE
PACKAGING_IMPLEMENTED_IN_B09 = FALSE
```

12.17.5 devra conserver une composition backend locale et un bind loopback par
défaut. Un frontend local pourra consommer `/api/v2`; ni Google Drive ni un
EXE/MSI ne constituent une gate produit V2. B09 n'implémente ni serveur,
frontend, packaging, installateur, ni aucun élément de 12.18.
