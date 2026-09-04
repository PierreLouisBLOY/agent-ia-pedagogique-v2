# Phase 12.17.7 — Plan de durcissement SQLite

Le socle actuel est conservé : chemins absolus injectés, seed authentifié en `mode=ro&immutable=1`, lectures runtime `query_only`, migrations allowlistées/checksummées, backup authentifié et publication atomique. Le lot ne réécrit ni migration `001`/`002`, ni seed, ni donnée utilisateur.

```text
SQLITE_HARDENING_ITEMS_COUNT = 7
TARGET_BATCH = 12.17.8-B02
SQLITE_WRITE_DURING_12_17_7 = 0
```

| # | Contrôle planifié | Implémentation minimale | Tests requis | Preuve de clôture |
|---:|---|---|---|---|
| 1 | Permissions runtime et seed | Pour les fichiers créés par V2, créer parent/fichier avec droits utilisateur courant uniquement; vérifier le seed externe en lecture et avertir/refuser selon une policy fermée si ses ACL sont excessives, sans jamais le chmod. | création temp least-privilege; seed non modifié; ACL/permission excessive classifiée | mode/ACL effectif enregistré sous forme de statut, jamais de chemin |
| 2 | Symlink/junction/reparse-point | Rejeter tout composant de chemin résolu vers symlink, junction ou reparse point avant ouverture et juste avant publication; utiliser un helper infrastructure unique. | symlink fichier/parent; junction Windows si supportée; remplacement entre contrôle et publication | toutes les redirections échouent avec code fermé |
| 3 | Canonicalisation et identité | Résoudre lexicalement puis physiquement, imposer chemin absolu, destination dans le data root approuvé et distinction seed/runtime/index/backup par identité réelle. | alias relatifs, casse Windows, `..`, samefile/hardlink lorsque détectable, collision de rôles | aucune collision ou sortie du data root n'est acceptée |
| 4 | Protection du seed | Centraliser l'ouverture seed read-only/immutable, snapshotter fichier et sidecars PRE/POST, interdire toute factory mutable visant le seed. | write probe refusé; hash PRE=POST; factories de migration/backup refusent seed comme cible | seed SHA256 `38ca8b3f…35134` inchangé dans la gate finale |
| 5 | Sécurité backup/restore | Exiger destination fraîche sous data root, permissions privées, temp de même volume, checksum+manifest authentifiés et publication atomique; restauration vers cible fraîche uniquement. | backup authentique, checksum faux, cible existante, collision source/destination, interruption avant replace | aucun backup partiel publié; restore incorrect fail-closed |
| 6 | Politique WAL/SHM | Documenter que runtime mutable peut créer WAL/SHM, que le seed ne doit pas en créer; inventorier PRE/POST et attribuer uniquement les sidecars nouveaux; inclure les sidecars cohérents dans backup/recovery. | runtime WAL légitime; seed sidecars inchangés; recovery avec WAL; sidecar inattendu | attribution PRE/POST et aucune suppression automatique des sidecars historiques |
| 7 | Emplacement temporaire | Utiliser un sous-répertoire privé du data root ou le temp système validé, jamais le dépôt; même volume pour publication atomique; nettoyage best-effort borné après échec. | temp hors repo, même volume, collision, cleanup d'échec, aucun scan Git contaminé | zéro fichier `.tmp`/`.building` adjacent non maîtrisé dans le dépôt |

## Frontières et rollback

Les helpers restent en infrastructure/adapters; Domain et Application ne reçoivent ni `Path`, ni type SQLite. Les tests utilisent exclusivement des répertoires temporaires et des copies synthétiques. Le seed canonique n'est ouvert qu'en lecture stricte pour la preuve finale.

Rollback du futur lot : revert du commit B02, puis réexécution des tests sur fixtures temporaires. Aucune restauration de base utilisateur n'est nécessaire puisque la remédiation ne doit jamais migrer une base utilisateur.

`SQLITE_HARDENING_PLAN = READY_FOR_IMPLEMENTATION_AFTER_12_17_8_ENTRY`
