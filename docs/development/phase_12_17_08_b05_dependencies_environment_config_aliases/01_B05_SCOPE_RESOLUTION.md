# Phase 12.17.8-B05 — Résolution du scope

```text
PHASE = 12.17.8-B05
B05_CANONICAL_TITLE = Dépendances, environnement et alias de configuration
HEAD_PRE_B05 = b63a1463046141512739e4c8f4618ab967002c78
B05_FINDINGS = CF-DEPENDENCY-001; CF-DOC-001; CF-LEGACY-001
```

Le lot couvre exclusivement trois locks Python 3.12/Windows AMD64, leur preuve de
réinstallation hashée, la documentation d'environnement et la fermeture des deux
anciens noms de configuration SQLite. `pyproject.toml` reste l'autorité des bornes et
`requirements-dev.txt` reste l'autorité des outils directs.

Sont hors scope : nouvelle dépendance directe, framework, route ou serveur, changement
provider/modèle/credential, appel provider, accès à une base canonique ou utilisateur,
écriture SQLite, dépendance réseau au runtime, B06 et 12.18.

```text
B05_COMMIT_POLICY = ONE_ENVIRONMENT_LOCKS_CONFIG_DOCS_TESTS_COMMIT
PROVIDER_CALLS = 0
CANONICAL_SEED_ACCESS = 0
CANONICAL_SEED_WRITES = 0
USER_RUNTIME_WRITES = 0
```
