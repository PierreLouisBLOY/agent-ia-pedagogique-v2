# Request ID et intégration B03

`LocalBrowserHttpSecurityContract` dépend d'un port structurel exposant exactement les opérations B03 : création/validation du correlation id, événement HTTP, validation rejetée et rejet de frontière sécurité.

Le contrat ne génère aucun UUID et n'implémente aucun second validateur de request id. Un id entrant valide est réutilisé par B03 ; sinon B03 en génère un. Le même id est placé dans la décision, l'enveloppe d'erreur et l'événement de fin de requête.

Les rejets host/origin/preflight émettent un code de sécurité fermé. Une méthode rejetée émet une validation fermée. Les hosts et origins non fiables ne sont jamais transmis au sink. Les tests d'intégration prouvent startup, requête acceptée, rejet, erreur HTTP, shutdown et absence de métadonnée hostile dans le NDJSON mémoire.

```text
REQUEST_CORRELATION_ID = B03_REUSED
SECOND_ID_SYSTEM = NONE
B03_LOGGING_INTEGRATION = PASS
```
