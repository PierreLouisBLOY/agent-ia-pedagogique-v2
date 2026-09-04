# Instrumentation runtime et HTTP

`LocalObservabilitySession` matérialise le point de composition injecté : construction du writer local, sink failure-isolated, événements de démarrage, arrêt et exception non gérée.

La surface HTTP reste un contrat pur, sans framework, serveur, route ni endpoint. Elle accepte un correlation id entrant uniquement s'il respecte le format opaque borné ; sinon elle génère un id local. Elle enregistre uniquement méthode, route template, classe de statut, durée, correlation id et outcome. URL brute, query, headers, cookies, body et adresse client sont absents du schéma.

La validation rejetée produit un code de règle et un code de champ fermés. Les exceptions non gérées ne conservent que la classe technique et une frontière fermée ; le message et la trace sont exclus.

```text
REQUEST_ID_SUPPORT = PASS
HTTP_SERVER_ADDED = FALSE
B04_STARTED = FALSE
```
