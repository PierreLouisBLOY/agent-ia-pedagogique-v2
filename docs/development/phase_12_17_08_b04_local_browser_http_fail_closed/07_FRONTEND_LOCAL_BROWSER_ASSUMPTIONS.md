# Hypothèses frontend local-browser

```text
FRONTEND_IMPLEMENTED = FALSE
FRONTEND_ORIGIN = NOT_CONFIGURED
FRONTEND_BASE_URL = NOT_CONFIGURED
BACKEND_PORT = EXPLICIT_REQUIRED_AT_FUTURE_COMPOSITION
HARDCODED_LAN_OR_PUBLIC_URL = NONE
GOOGLE_DRIVE_RUNTIME_DEPENDENCY = NONE
```

B04 ne crée aucun frontend et ne choisit aucune base URL. Le contrat prépare un futur frontend servi same-origin. Une origine locale différente ne pourra être utilisée qu'après déclaration exacte dans la allowlist CORS locale, toujours sans credentials.

Aucun endpoint `/api/v2` n'est créé. Le handoff READ-15 et tout endpoint métier restent séparés de ce lot.
