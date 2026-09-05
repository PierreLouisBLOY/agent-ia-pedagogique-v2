# Gate d'entrée B06

```text
B06_CANONICAL_TITLE = .gitignore, tests déterministes et rétention locale
B06_ENTRY_REQUIRES_B01 = PASS
B01_STATUS = PASS
B06_ENTRY_GATE = READY
B06_STARTED = FALSE
```

B06 reste un lot séparé consacré à `CF-TEMP-LOCAL-001` et `CF-GITIGNORE-001`.
L'entrée est prête parce que la consolidation de provenance B01 est déjà close. B05 ne
modifie aucune règle `.gitignore`, ne supprime aucun fichier local et ne démarre ni B06
ni 12.18.
