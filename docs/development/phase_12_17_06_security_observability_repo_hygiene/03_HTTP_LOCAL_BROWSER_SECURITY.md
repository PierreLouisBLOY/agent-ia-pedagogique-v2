# Phase 12.17.6 — Sécurité HTTP / navigateur local

## Constat factuel

Aucun usage de FastAPI, Flask, Uvicorn, Hypercorn, aiohttp, `http.server` ou `HTTPServer` n'est présent dans `backend/`. `backend/adapters/inbound/api/__init__.py` est uniquement structurel. Il n'existe ni route, ni serveur, ni configuration de port, ni middleware CORS, ni cookie/session, ni OpenAPI/docs ni mode debug HTTP.

| Contrôle | Statut actuel |
|---|---|
| Bind par défaut | `NOT_APPLICABLE_NO_HTTP_SERVER` |
| Port | `NOT_CONFIGURED_NO_HTTP_SERVER` |
| CORS / allowed origins | `NOT_APPLICABLE_NO_HTTP_SERVER` |
| Cookies / credentials | `NONE` |
| CSRF | `NOT_APPLICABLE_NO_STATEFUL_HTTP` |
| Debug / stack trace HTTP | `NO_HTTP_EXPOSURE` |
| Docs / OpenAPI | `NONE` |
| Host header | `NOT_APPLICABLE_NO_HTTP_SERVER` |
| Endpoint fournisseur public | `NONE` |

La cible `LOCAL_BROWSER / LOOPBACK_ONLY_BY_DEFAULT` n'est donc ni violée ni encore encodée. `HTTP-001` exige qu'avant toute matérialisation HTTP, le plan définisse et teste le bind loopback, les origines exactes, l'absence de debug, la politique de cookies/CSRF, les headers et la non-exposition des adaptateurs fournisseurs.
