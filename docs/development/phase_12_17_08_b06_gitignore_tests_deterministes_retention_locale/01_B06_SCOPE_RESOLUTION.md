# 12.17.8-B06 — Scope canonique résolu

B06_CANONICAL_TITLE = .gitignore, tests déterministes et rétention locale
B06_FINDINGS = CF-TEMP-LOCAL-001, CF-GITIGNORE-001

Entrée vérifiée : HEAD `313d574cc0aca15529978db622939ed648d0c1c7`, worktree clean, B05 PASS et B06 READY dans le handoff B05. Le bundle reçu est lié au SHA-256 `a3be892def79c73833244fb1ccbc6fbc7e9d65224d1941d66b19ad723e4572dd` ; ses sept fichiers manifestés ont été vérifiés, 7/7.

## Autorités lues

Les fichiers 09_12_17_8_BATCH_EXECUTION_PLAN.md, 10_12_17_8_FINAL_GATES.md, 02_CANONICAL_FINDINGS_REGISTER.json, 07_REPOSITORY_HYGIENE_DISPOSITION_PLAN.md et 08_HISTORICAL_AND_LOCAL_DEBT_DISPOSITION.md du dossier phase_12_17_07_prioritized_rationalization_plan, ainsi que le handoff final B05.

## Causes et périmètre

CF-TEMP-LOCAL-001 : anciennes racines de tests/output ignorées sans procédure bornée de rétention, parcours de dépôt entrant dans des copies imbriquées.
CF-GITIGNORE-001 : quatre familles de fichiers générés hors des racines dédiées restent visibles.

Implémentation : sept patterns correspondant exactement aux quatre familles ; remplacement des deux parcours globaux de tests par un inventaire Git déterministe ; garde de placement du temp pytest ; dry-run de métadonnées uniquement ; isolation en temp système du test historique d'écriture R1 ; tests de non-régression et documentation de maintenance.

Fichiers attendus : .gitignore, helpers/tests de parcours et hygiène Git, ENVIRONMENT.md, paquet de preuves B06. Aucun module backend ou calibration runtime ne change.

Hors scope : suppression de temporaires, lecture du contenu des artefacts locaux, réécriture de preuves historiques, SQLite externe, providers, réseau B05, dépendances, routes, migrations, B07 et 12.18.

## Gates et commit

Gates : quatre familles ignorées sans masquer les preuves, parcours déterministes, temp externe, disposition complète sans destruction, historique intact, tests ciblés et architecture, mypy actif/backend, Ruff, compileall, diff et secrets. Suite globale hors seed exécutée car les parcours de test sont transverses. La gate seed réelle reste explicitement exclue de B06.

Politique : un seul commit hygiène code/tests/docs, staging littéral limité à B06, aucun push, aucune suppression, aucun merge. Rollback éventuel par revert explicite, non exécuté.

B07_CANONICAL_TITLE = Ré-audit transverse et clôture
B07_ENTRY_CONDITIONS = B01 à B06 PASS, worktree conforme et absence de dérive.
B07 n'est pas démarrée par ce lot.
