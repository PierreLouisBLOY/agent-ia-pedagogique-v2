# Politique debug, erreurs et documentation

```text
DEBUG_DEFAULT = FALSE
RELOAD_DEFAULT = FALSE
DOCS_OPENAPI_DEFAULT = DISABLED
STATEFUL_SESSIONS = FALSE
TRACEBACK_EXPOSURE = 0
```

Les valeurs `True` sont rejetées à la construction de la configuration, plutôt que tolérées comme override implicite. B04 n'expose aucune page docs/OpenAPI.

Les erreurs client sont des enveloppes fermées contenant uniquement un statut, un code stable et le correlation id. Le contrat n'accepte pas d'objet exception et ne sérialise ni message, détail, path, traceback, locals ou payload. Une erreur interne devient uniquement `INTERNAL_ERROR` avec un statut 500.

L'absence d'état HTTP, de cookie et de credentials rend CSRF non applicable dans B04. Toute future introduction d'état exigera un nouveau contrat et ses gates dédiées.
