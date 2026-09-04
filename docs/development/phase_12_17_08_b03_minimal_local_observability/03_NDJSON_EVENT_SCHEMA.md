# Schéma d'événements NDJSON

Chaque ligne est un objet JSON complet, déterministe et borné à 65536 octets. Les cinq champs communs sont :

```text
ts        timestamp UTC ISO-8601
level     INFO | WARNING | ERROR
event     code fermé de l'événement
component application | http | validation | sqlite | provider | security
message   code fermé identique à event, jamais un texte libre
```

Les champs supplémentaires sont définis par une allowlist propre à chaque événement. Ils couvrent uniquement les identifiants opaques, correlation id validé, durée, outcome, classe de statut, versions/checksums, compteurs de tokens, coût borné et codes d'erreur fermés. Aucune conversion générique de dataclass, `repr`, message d'exception ou stack trace n'est admise.

Événements implémentés :

- `app.startup`, `app.shutdown`, `app.unhandled_exception` ;
- `http.request.completed`, `http.request.failed`, `http.validation.rejected` ;
- `sqlite.bootstrap.started`, `.completed`, `.failed` ;
- `sqlite.migration.started`, `.completed`, `.failed` ;
- `sqlite.backup.completed`, `.failed`, `sqlite.recovery.completed`, `.failed` ;
- `provider.call.started`, `.completed`, `.failed` ;
- `security.path.rejected`, `security.runtime_boundary.rejected`.

Toutes les familles minimales sont applicables et couvertes ; aucune n'est classée `NOT_APPLICABLE`.
