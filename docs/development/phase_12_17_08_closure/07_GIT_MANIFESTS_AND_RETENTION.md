# Git, provenance, manifestes et rétention finale

Baseline corrigée : `f28b29f0964d2642b74eb7098f90359d15fb4f0c`. Les 2243 fichiers suivis à cette baseline ont le même SHA avant/après la suite complète. Aucun diff applicatif, migration, dépendance ou input de lock depuis la référence `0404852a3be77381bf7b7c903ee6309e2547487e`. Le seul diff technique autorisé est le correctif de test déjà commité.

## Preuves inchangées

- 48/48 identités hashées préservées : freeze effectif 40, deux références séparées, migrations, locks et preuve locale. Les métadonnées disponibles sont inchangées pour 47 ; la photographie initiale de 001 n'avait qu'un SHA et n'autorise donc pas une comparaison mtime inventée.
- Freeze 40/40 ; sept drifts historiques connus inchangés ; zéro nouveau drift. `catalog.py` et `anchor_corpus_v3.py` restent contrôlés séparément, pas ajoutés aux 40.
- 23 manifestes sources / 254 entrées vérifiés de nouveau ; aucun manifeste historique réécrit.
- 126 preuves historiques + 11 preuves 05C présentes dans B01 et inchangées ; allowlist B01 de 209 chemins préservée.
- Six minimisations autorisées et 18 reconstitutions EOF conservées. Le libellé historique FIVE/165 n'est pas réécrit.
- Le manifeste du présent paquet s'exclut lui-même. Les preuves correctives 11/12 déjà commitées sont inchangées.

## Conservation sans nettoyage

207 dispositions B06 ; 203 ensembles locaux observés avant/après ; 20664 fichiers, 2994 répertoires. Sous .tmp : 41 éléments immédiats, 4587 fichiers et 1673 répertoires descendants. Métadonnées de 200 racines en contexte restreint et trois complémentaires en lecture seule ; aucun contenu lu, lien suivi ou permission modifiée.

PRE/POST : zéro ensemble ajouté/supprimé, zéro dérive de métadonnées, zéro suppression, zéro pollution temporaire. Les 16 chemins DB/sidecar/backup B06 restent ignorés. Ce relevé ne certifie pas leur supprimabilité.

La différence ancienne de mtime de `artifacts` entre l'inventaire initial B06 et son état final avait déjà été documentée par B06/04. Elle n'est ni masquée ni attribuée à B07 : les snapshots initial B07, correctif et reprise sont stables.

## Transaction documentaire et confidentialité

Seuls les quatorze documents B07 encore non suivis sont candidats au commit documentaire final ; les deux preuves correctives sont déjà suivies. Aucun fichier brut, SQLite, log, JUnit, contenu runtime, credential, locateur personnel ou archive n'entre dans Git.

Scan borné des candidats/suivis : quatre familles de signatures sensibles et paths interdits, sans affichage de valeur. Ce contrôle ne prétend pas détecter tout secret possible. Le manifeste final, UTF-8/LF, les liens, JSON et le diff sont vérifiés avant commit.

La gate 14 est la postcondition du commit local documentaire et du status vide, selon 14. Aucun push/merge. Le graphe de code testé est celui de la baseline corrigée ; seul ce paquet documentaire lui succède.
