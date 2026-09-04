# Phase 12.17.8-B02 — Durcissement symlink, junction et courses

Chaque composant existant est lu par `lstat`. Un symlink POSIX ou l'attribut Windows `FILE_ATTRIBUTE_REPARSE_POINT` ferme l'opération avant ouverture et est revérifié avant publication.

| Cas | Résultat |
|---|---|
| Traversal hors racine | DENY `OUTSIDE_ALLOWED_ROOT` |
| Symlink fichier/parent | test présent; SKIP Windows lorsque la création est interdite |
| Junction Windows | PASS réel |
| Hardlink seed/runtime | DENY `PATH_COLLISION` |
| Remplacement entre snapshot et open | DENY `PATH_CHANGED` |
| Changement in-place avant post-inspection | DENY `PATH_CHANGED` |
| Course sur destination fraîche | gagnant préservé; aucune écriture par-dessus |
| Changement de destination avant replace | DENY `PATH_CHANGED` |

La publication ne supprime une destination de rollback que si son identité est encore celle publiée par l'opération courante. Les sidecars ou fichiers historiques ne sont jamais supprimés sur une identité ambiguë.

```text
TRAVERSAL_GUARD = PASS
SYMLINK_GUARD = PASS_WITH_PLATFORM_SKIP
WINDOWS_JUNCTION_GUARD = PASS
TOCTOU_SIMULATION = PASS
ATOMIC_PUBLICATION = PASS
```
