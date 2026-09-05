# Staging et commit B06

HEAD_PRE = 313d574cc0aca15529978db622939ed648d0c1c7
HEAD_POST = CREATED_AFTER_MANIFEST_FREEZE
B06_COMMIT_POLICY = ONE_HYGIENE_CODE_TESTS_DOCS_COMMIT
COMMIT_SUBJECT = test(hygiene): isolate repository validation and local retention
TECHNICAL_PATH_COUNT = 8
EVIDENCE_PATH_COUNT = 12
EXACT_STAGING_ALLOWLIST_COUNT = 20
PUSH = NONE
MERGE = NONE

## Allowlist littérale

- .gitignore
- docs/development/ENVIRONMENT.md
- tests/architecture/test_repository_baseline.py
- tests/architecture/test_sqlite_runtime_persistence_fitness.py
- tests/architecture/test_repository_hygiene_b06.py
- tests/conftest.py
- tests/support/repository_hygiene.py
- tests/unit/test_pedagogical_calibration_r4_r3_r1.py

Les douze fichiers de ce répertoire, nommés dans 01 à 11 et MANIFEST_SHA256.txt, complètent cette liste. Aucun autre chemin n'est admis. Aucun fichier n'est supprimé.

Avant commit : comparer l'index à ces 20 chemins, exécuter git diff --cached --check, vérifier zéro binaire/DB/sidecar/backup/config privée candidat et zéro signature de secret. Le contenu suivi préexistant ne change que dans les cinq chemins prévus ; aucun manifest historique, lock, backend ou migration ne diffère.

Le commit doit conserver pour parent exact la baseline PRE. Son SHA ne peut figurer dans son propre manifeste sans circularité : le résultat final de la session fournit le SHA réel. Il est également résolu par :
`git log -1 --format=%H -- docs/development/phase_12_17_08_b06_gitignore_tests_deterministes_retention_locale/11_FINAL_HANDOFF.md`.

La propreté POST est vérifiée après commit, sans amend de ces preuves. Aucun push ni merge. Aucun ancien temporaire n'est effacé. Un rollback ultérieur nécessite une action explicite de revert, non exécutée dans B06.
