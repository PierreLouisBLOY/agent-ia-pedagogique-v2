# Politique host, origin et CORS

Hosts locaux autorisés par défaut :

- `localhost` ;
- `127.0.0.1` ;
- `[::1]` pour le Host HTTP IPv6.

Un suffixe de port est accepté uniquement s'il égale le port explicitement configuré. URL complète, userinfo, host LAN/public, wildcard, Host malformé, IPv6 non bracketé et port différent sont rejetés.

Same-origin est la politique par défaut : Origin absent ou exactement égal au host local courant. Un CORS local peut être déclaré uniquement par une allowlist d'origins canoniques `http` correspondant aux hosts locaux et au port configuré. `*`, credentials, cookies/sessions et headers Authorization/Cookie sont interdits. Les méthodes CORS sont bornées à GET/HEAD et les headers au sous-ensemble explicitement déclaré. OPTIONS n'est accepté que comme preflight complet et allowlisté.

```text
NON_LOCAL_HOST = REJECTED
NON_LOCAL_ORIGIN = REJECTED
CORS_WILDCARD = REJECTED
CROSS_ORIGIN_CREDENTIALS = REJECTED
DEFAULT_CORS = SAME_ORIGIN_ONLY
```
