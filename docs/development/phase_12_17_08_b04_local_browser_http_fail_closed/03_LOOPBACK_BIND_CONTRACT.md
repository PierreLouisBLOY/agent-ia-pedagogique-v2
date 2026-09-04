# Contrat de bind loopback

```text
EXECUTION_MODE = LOCAL_BROWSER
DEFAULT_BIND = 127.0.0.1
ALLOWED_BIND_OVERRIDES = 127.0.0.1; ::1
PORT_POLICY = EXPLICIT_REQUIRED_NO_DEFAULT
PUBLIC_NETWORK_EXPOSURE = FALSE
```

`LocalBrowserHttpConfiguration` n'accepte que les adresses numériques loopback IPv4 et IPv6. Les binds wildcard, LAN, publics et hostnames sont rejetés avec un code fermé sans répéter la valeur reçue. Le port doit être fourni explicitement et appartenir à `1..65535`; B04 n'invente pas de port produit.

La configuration est un contrat immuable. Elle ne crée ni socket, ni serveur, ni thread et n'effectue aucune résolution DNS. Toute future composition devra consommer ce DTO et ne pourra pas activer silencieusement un bind public.
