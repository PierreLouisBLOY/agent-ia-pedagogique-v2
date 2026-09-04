# Phase 12.17.8-B02 — Protection seed/runtime

`SQLiteDatabasePaths` impose désormais une data root locale, un runtime physiquement contenu dans cette racine, l'absence de composant reparse et la distinction physique seed/runtime. Les chemins runtime explicites vers `G:`, Drive, OneDrive ou une racine réseau sont refusés.

Le seed reste externe à la data root autorisée. Il est résolu sans lien, inspecté comme fichier régulier, classifié en permission sans `chmod`, authentifié par taille et SHA-256, puis ouvert par `mode=ro&immutable=1` et `query_only`. Les snapshots main/WAL/SHM/journal PRE/POST sont conservés.

Le runtime créé par V2 reçoit une racine/répertoire privés, un fichier owner-only, les migrations allowlistées, WAL, checkpoint et publication fraîche atomique. Un runtime existant est vérifié avant ouverture et reçoit la même politique de permissions lors d'une opération runtime autorisée. B02 n'a exécuté cette logique que sur des copies temporaires.

```text
SEED_RUNTIME_DISTINCT = PASS
SEED_READ_ONLY_IMMUTABLE = PASS
SEED_PRE_POST = SAME
RUNTIME_LOCAL_ONLY = PASS
RUNTIME_DRIVE_DEPENDENCY = NONE
SEED_WRITES = 0
USER_RUNTIME_DESTRUCTIVE_WRITES = 0
```
