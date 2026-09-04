# État HTTP PRE

```text
HEAD_PRE = 2650ae7616fc7067e6c6341f854a10efee633d6f
HTTP_FRAMEWORK = NONE
APP_SERVER_FACTORY = NONE
HTTP_SERVER = NONE
ROUTES = 0
BIND_DEFAULT = NOT_CONFIGURED_NO_SERVER
PORT = NOT_CONFIGURED_NO_SERVER
CORS = NOT_APPLICABLE_NO_SERVER
ALLOWED_HOSTS = NOT_APPLICABLE_NO_SERVER
DEBUG_RELOAD = NO_HTTP_EXPOSURE
EXCEPTION_HANDLER = NONE
DOCS_OPENAPI = NONE
FRONTEND = NONE
PROVIDER_CALLS = 0
```

B03 fournissait déjà une fabrique de correlation id, les événements HTTP completed/failed/validation et les rejets de frontière. B04 devait les réutiliser sans créer un second système de request id.

| Élément protégé | Taille | SHA-256 PRE |
|---|---:|---|
| seed canonique externe read-only | 105553920 | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` |
| runtime utilisateur non ouvert | 105553920 | `de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1` |

Les sidecars WAL/SHM préexistants étaient présents et les journaux rollback absents pour les deux fichiers.
