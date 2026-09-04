# Gate d'entrée B04

```text
B04_CANONICAL_TITLE = Contrat HTTP local-browser fail-closed
B04_FINDING = CF-HTTP-001
B04_ENTRY_REQUIRES_B01 = PASS
B04_ENTRY_REQUIRES_NO_CONCURRENT_HTTP_IMPLEMENTATION = PASS
B04_IMPLEMENTATION_STARTED = FALSE
B04_ENTRY_GATE = READY_ON_SUCCESSFUL_B03_COMMIT
```

B04 reste un lot distinct : il devra encoder un contrat loopback-only et ses tests d'architecture sans ajouter de serveur ni de framework. Aucun travail B04 ou 12.18 n'est effectué dans B03.
