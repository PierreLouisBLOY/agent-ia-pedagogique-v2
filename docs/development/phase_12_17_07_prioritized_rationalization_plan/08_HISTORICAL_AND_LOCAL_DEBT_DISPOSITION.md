# Phase 12.17.7 — Dette historique et locale

## Dette mypy 15/10

Décision du plan : `HISTORICAL_IMMUTABLE`.

- les 15 diagnostics dans 10 fichiers sont hors graphe actif ;
- le graphe actif reste à `0/42` et le backend à `0/674` sur la dernière preuve globale ;
- rechercher artificiellement zéro global modifierait des sources de calibration gelées et leurs identités ;
- le code ne doit pas être supprimé : il constitue une preuve versionnée et des contrats historiques le référencent ;
- la dette n'est pas un risque de livraison tant qu'un guard interdit tout import actif.

Acceptation 12.17.8 : reproduire exactement `15 errors / 10 files`, `NEW_HISTORICAL_DRIFT = 0`, historique freeze `40/40`, active/backend mypy `0`.

## Autres findings historiques

| Finding canonique | Disposition | Motif |
|---|---|---|
| CF-SIDECAR-HIST-001 | HISTORICAL_IMMUTABLE | Le créateur passé des WAL/SHM ne peut être prouvé; préserver les bytes et la vérité `UNKNOWN`, appliquer PRE/POST seulement à l'avenir. |
| CF-B01-HIST-001 | HISTORICAL_IMMUTABLE | L'écart récit/machine B01 est explicitement accepté; aucune réécriture rétroactive. |
| CF-DOC-DUP-HIST-001 | DOCUMENT_AND_ACCEPT | Les doublons et hashes supersédés sont des preuves, non une autorité active. |

```text
HISTORICAL_CANONICAL_FINDINGS = 4
HISTORICAL_CODE_REMOVAL = NOT_ALLOWED
```

## Chemins privés, Drive et configuration locale

| Classe | Éléments | Nature | Action planifiée |
|---|---|---|---|
| Runtime bug | aucun chemin privé codé en dur sous `backend/` | none | aucune correction |
| Historical evidence | cinq fichiers contenant un profil utilisateur, `Desktop`, l'alias `G:`/Drive ou équivalent exact | preuve read-only du seed et du design | minimiser par tokens neutres si Option A; rebind de manifestes et équivalence |
| Test fixture | chemins temporaires, copies de seed et résultats dans `.tmp` | local-only/ignored | forcer le temp système ou une fixture dédiée hors repo; ne pas versionner |
| Local configuration | variables V2 injectées et anciens alias de chemins SQLite | configuration mono-utilisateur | conserver l'injection; appliquer la sortie de compatibilité legacy dans B05 |
| Backup/runtime | backups, WAL/SHM, DB, `.tmp`, `.building`, `.jsonl` | donnée générée | data root hors dépôt, permissions privées, ignores défensifs |

L'alias de lecteur `G:` et les emplacements Drive/OneDrive/Desktop/AppData ne doivent jamais devenir des defaults produit. Ils peuvent uniquement figurer comme faits historiques minimisés ou comme valeurs injectées localement non commitées.

## Dette locale unique

`CF-TEMP-LOCAL-001` est la seule entrée canonique `LOCAL_ONLY`. La fermeture avant 12.18 porte sur la déterminisation : exclusion des racines ignorées, temp hors repo, dry-run d'inventaire et procédure de rétention. Elle ne requiert pas d'effacer les fichiers existants. Une suppression reste hors scope sans autorisation explicite.

Les capacités `ContextOrigin`, CAP-R02, CAP-A01 et CAP-A02 représentent quatre findings `DEFERRED`, pas de la dette historique ni un prétexte à ajouter des placeholders en 12.17.8.

```text
LOCAL_ONLY_CANONICAL_FINDINGS = 1
DEFERRED_CANONICAL_FINDINGS = 4
PRIVATE_RUNTIME_PATH_BUGS = 0
PLANNED_DESTRUCTIVE_ACTIONS = 0
```
