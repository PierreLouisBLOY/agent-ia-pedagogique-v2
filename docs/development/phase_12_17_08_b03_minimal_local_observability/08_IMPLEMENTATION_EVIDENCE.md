# Preuves d'implémentation

Les éléments principaux sont :

- `backend/infrastructure/observability/operational.py` : schéma fermé, serializer et sink failure-isolated ;
- `backend/infrastructure/observability/local.py` : writer privé local, rotation, rétention et flush ;
- `backend/infrastructure/composition/bootstrap/observability.py` : lifecycle et douze familles de signaux ;
- factory SQLite : bootstrap, migrations, backup et recovery observables par injection ;
- `calibration_tooling/observability/` et runtime : événements par appel fournisseur, usage et coût minimisés ;
- `docs/development/ENVIRONMENT.md` : configuration et exclusions documentées ;
- tests unitaires, intégration et architecture dédiés.

Le code Domain/Application métier ne dépend pas du sink concret. Le sink n'importe ni fournisseur, ni module métier, ni bibliothèque réseau. Aucun serveur HTTP et aucune dépendance runtime ne sont ajoutés.

```text
IMPLEMENTED_SIGNAL_FAMILIES = 12/12
SPECIFIC_EVENT_CODES = 21
SINK_LOCAL_ONLY = TRUE
SINK_FAILURE_ISOLATED = TRUE
CONFIGURATION_DOCUMENTED = TRUE
```
