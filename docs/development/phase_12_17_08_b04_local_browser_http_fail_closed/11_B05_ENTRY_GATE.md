# Gate d'entrée B05

```text
B05_CANONICAL_TITLE = Dépendances, environnement et alias de configuration
B05_ENTRY_REQUIRES_B01 = PASS
B05_ENTRY_REQUIRES = NETWORK_RESOLUTION_EXPLICITLY_AUTHORIZED_OR_APPROVED_WHEELHOUSE
NETWORK_RESOLUTION_AUTHORIZATION = ABSENT
APPROVED_WHEELHOUSE = ABSENT
B05_ENTRY_GATE = BLOCKED
B05_STARTED = FALSE
```

Le plan canonique exige une autorisation réseau explicite au moment de l'exécution B05 ou un wheelhouse approuvé. Aucun de ces éléments n'est présent dans la baseline B04 ; la gate reste donc fail-closed. B04 ne sollicite, n'infère et ne consomme aucune autorisation B05.
