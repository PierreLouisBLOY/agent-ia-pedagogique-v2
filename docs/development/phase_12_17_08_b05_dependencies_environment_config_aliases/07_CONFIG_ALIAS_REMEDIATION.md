# Remédiation des alias de configuration

La fenêtre de compatibilité est close. Les noms acceptés sont désormais uniquement :

- `PROJET_V2_DATA_DIR` ;
- `PROJET_V2_CANONICAL_DB` ;
- `PROJET_V2_RUNTIME_DB`.

La présence de l'un des deux anciens noms est détectée avant toute résolution de
chemin et lève `LEGACY_SETTING_FORBIDDEN`. Le message ne contient ni nom de fichier ni
valeur locale. Les constantes publiques `SEED_PATH_ENV` et `RUNTIME_PATH_ENV` pointent
sur les noms V2. La gate réelle du lifecycle SQLite ne consulte plus l'ancien nom.

Les chaînes legacy restent uniquement comme sentinelles de rejet et comme documentation
de migration ; elles ne sont plus des sources de configuration.

```text
ACCEPTED_LEGACY_ALIAS_COUNT_PRE = 2
ACCEPTED_LEGACY_ALIAS_COUNT_POST = 0
RUNTIME_PRIVATE_PATH_ALIAS_LEAKS = 0
PRIVATE_PATH_LITERAL_FINDINGS_ACTIVE = 0
LEGACY_ONLY = REJECTED
LEGACY_PLUS_V2 = REJECTED
V2_ONLY = ACCEPTED
```
