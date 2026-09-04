# Preuves de tests et gates

```text
TARGETED_B04_AND_SECURITY = 49 passed
ARCHITECTURE_EXPANDED_PRE_FINAL = 867 passed
GLOBAL_SUITE = 4899 passed, 5 skipped, 0 failed / 735.39 seconds
RUFF = PASS
MYPY_BACKEND_AND_CALIBRATION = PASS / 710 source files
COMPILEALL_BACKEND_AND_CALIBRATION = PASS
GIT_DIFF_CHECK = PASS
```

Les tests couvrent : bind par défaut, refus wildcard/LAN/public, IPv4/IPv6 loopback, port explicite, Host avec/sans suffixe, Host malformé, same-origin, non-local origin, allowlist CORS, wildcard/credentials interdits, preflight, debug/reload/docs/sessions, erreurs sans traceback, correlation id B03, événements acceptation/rejet/startup/shutdown, absence de framework, route, provider, SQLite, frontend, URL publique et dépendance Drive.

Les cinq skips globaux sont les trois gates conditionnelles non autorisées et les deux cas de liens symboliques indisponibles sous Windows. Aucun test B04 n'est ignoré.
