# Implémentation minimale

- .gitignore : sept lignes, exactement quatre familles.
- tests/support/repository_hygiene.py : inventaire source trié/dédupliqué via git ls-files --cached --others --exclude-standard ; inclusion inconditionnelle de l'index ; échec Git propagé. Dry-run local par lstat/scandir, sans contenu, sans suivi de liens/jonctions, sans suppression.
- tests/conftest.py : refus des racines temporaires pytest situées dans le dépôt, avant création des fixtures.
- tests/architecture/test_repository_baseline.py et test_sqlite_runtime_persistence_fitness.py : les deux scans globaux non bornés sont remplacés par les candidats Git ; les autres règles d'architecture restent intactes.
- tests/architecture/test_repository_hygiene_b06.py : tests nouveaux d'exclusion, non-masquage, clone de test ignoré, fichiers force-added, échec Git, temp externe, dry-run sans lecture/destruction, erreur d'accès, preuves suivies et historique.
- tests/unit/test_pedagogical_calibration_r4_r3_r1.py : le test d'écriture R1 travaille désormais sur une copie locale temporaire de ses quatre répertoires de preuves, vérifie toujours les hashes protégés, et ajoute l'invariance contenu + mtime des originaux. Aucune modification du moteur historique, des checksums ou des assertions métier.
- ENVIRONMENT.md : procédure de maintenance et isolation du temp/cache.

Aucune dépendance runtime n'est ajoutée. Les tests de fixtures créent leurs faux dépôts/bases uniquement dans le temp système. Le helper ne fait partie d'aucun flux applicatif.

Le refus concret `pytest --basetemp .tmp/b06-must-not-create` retourne 4 avec le message générique prévu ; le répertoire reste absent. Le typecheck du helper utilise --explicit-package-bases, adapté au namespace tests existant ; aucun __init__.py artificiel n'est introduit.

ARCHITECTURAL_DEVIATION = NONE
BACKEND_CHANGE = NONE
NETWORK_USED_BY_B06 = FALSE
PROVIDER_CALLS = 0
CANONICAL_SEED_ACCESS_WRITES = 0/0
USER_RUNTIME_ACCESS_WRITES = 0/0
