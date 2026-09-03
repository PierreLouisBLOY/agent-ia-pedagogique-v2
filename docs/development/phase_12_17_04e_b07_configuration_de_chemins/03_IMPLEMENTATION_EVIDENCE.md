# Phase 12.17.4E-B07 — Preuves d'implémentation

La configuration est résolue à partir d'un mapping injecté. La composition
appelle ce loader, mais ne lit jamais directement l'environnement.

| Élément | Résultat |
|---|---|
| Schéma typé | chemins absolus résolus, dataclass immuable, erreurs codées et expurgées |
| Loader | nouveaux noms, defaults OS, aliases legacy et conflits fail-closed |
| Composition | nouvelle factory configurée déléguant à la factory SQLite existante |
| Compatibilité | constructeur historique à deux chemins conservé |
| Identité fichier | collision de chemin résolu ou d'identité physique refusée |
| Répertoires | `imports`, `exports`, `logs`, `backups`, `runtime` dérivés du data dir |

Les defaults sont `%LOCALAPPDATA%/ProjetV2` sous Windows,
`$XDG_DATA_HOME/ProjetV2` ou `$HOME/.local/share/ProjetV2` sous Unix, et
`$HOME/Library/Application Support/ProjetV2` sous macOS. Ces racines sont
injectées dans les tests ; aucune recherche globale de disque ni expansion
implicite du home n'est utilisée.

```text
MIGRATIONS = 0
BUSINESS_RULE_CHANGES = 0
PROVIDER_DEPENDENCIES = 0
```
