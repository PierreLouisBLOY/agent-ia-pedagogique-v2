# Tests exécutés et gates B06

Outils réellement exécutés : Python 3.12.14, pytest 9.1.1, mypy 2.3.1, Ruff 0.16.4. Aucun téléchargement ni installation de dépendance B06.

| Contrôle | Résultat observé |
|---|---|
| Hygiène, baseline et fitness SQLite ciblées | 46 passed, 8.21 s au dernier passage |
| Test d'écriture R1 isolé et invariance des originaux | 1 passed, 38.03 s |
| Guards architecture complets | 872 passed, 214.77 s |
| Suite globale finale hors seed | 4915 passed, 28 skipped, 0 failed, 436.91 s |
| Mypy backend | 0 diagnostic / 683 fichiers |
| Mypy backend + calibration_tooling | 0 / 710 fichiers |
| Mypy actif strict de référence | 0 / 42 fichiers |
| Mypy des deux nouveaux supports | 0 / 2 fichiers |
| Mypy historique, deux racines exactes | 15 erreurs / 10 fichiers, stable ; sortie 1 attendue, pas un mypy vert |
| Ruff global | PASS |
| Compileall backend, calibration et supports/tests B06 | PASS |
| git diff --check | PASS |
| Temp pytest dans le dépôt | Refus 4 attendu, aucun dossier créé |
| Freeze historique | 40/40, sept dérives connues préservées |
| Scan signatures de secrets | 0 candidat détecté, valeurs jamais affichées |

## Commandes et isolation

Toutes les validations utilisent le venv existant et PYTHONDONTWRITEBYTECODE=1. Les basetemp pytest, caches mypy et PYTHONPYCACHEPREFIX de compileall sont des chemins uniques sous le temp système, hors dépôt. Ruff utilise --no-cache et pytest -p no:cacheprovider.

Les sept variables PEDAGOGICAL_CANONICAL_SEED_PATH, PEDAGOGICAL_RUNTIME_DATABASE_PATH, PROJET_V2_CANONICAL_DB, PROJET_V2_RUNTIME_DB, PROJET_V2_DATA_DIR, OPENAI_API_KEY, ANTHROPIC_API_KEY sont retirées du processus de validation avec Remove-Item Env:<nom>. Une assertion Python de présence vérifie OFFLINE_ENV_ABSENT_7_OF_7 sans lire/afficher de valeur. Les flags live ne sont pas activés.

```text
python -m pytest -q -p no:cacheprovider tests/architecture/test_repository_hygiene_b06.py tests/architecture/test_repository_baseline.py tests/architecture/test_sqlite_runtime_persistence_fitness.py --basetemp <temp-systeme-cible>
python -m pytest -q -p no:cacheprovider tests/unit/test_pedagogical_calibration_r4_r3_r1.py::test_writing_r1_outputs_does_not_mutate_historical_proofs --basetemp <temp-systeme-isole>
python -m pytest -q -p no:cacheprovider tests/architecture --basetemp <temp-systeme-architecture>
python -m pytest -q -p no:cacheprovider --ignore=tests/non_functional/test_retrieval_quality_real_gate.py --basetemp <temp-systeme-global-final> --tb=short
python -m mypy backend --cache-dir <cache-externe>
python -m mypy backend calibration_tooling --cache-dir <cache-externe>
python -m mypy --explicit-package-bases calibration_tooling tests/unit/calibration_tooling tests/integration/calibration_tooling tests/architecture/test_calibration_tooling_imports.py --cache-dir <cache-externe-actif>
python -m mypy --explicit-package-bases tests/support/repository_hygiene.py tests/conftest.py --cache-dir <cache-externe-hygiene>
python -m mypy --strict --explicit-package-bases --no-pretty --no-color-output --show-error-codes tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py tests/unit/test_pairwise_output_contract_v5_2_4.py --cache-dir <cache-externe-historique>
python -m ruff check --no-cache .
python -m compileall -q backend calibration_tooling tests/support/repository_hygiene.py tests/conftest.py tests/architecture/test_repository_hygiene_b06.py tests/unit/test_pedagogical_calibration_r4_r3_r1.py
git diff --check
```

Les 42 fichiers actifs sont les 27 de calibration_tooling, 10 tests unitaires actifs, quatre tests d'intégration actifs et le guard test_calibration_tooling_imports.py. Aucune exclusion mypy ou échappatoire de typing n'est ajoutée.

Les 28 skips correspondent à 23 gates SQLite réelles sans seed configuré, trois gates provider/semantic explicitement non activées, et deux tests symlink indisponibles sous Windows. Le fichier explicitement ignoré exige le seed réel : il reste dû à B07 et n'est pas annoncé PASS.

## Essais diagnostiques non retenus comme réussite

Le premier passage global retourne 5 failed, 4915 passed, 5 skipped, 18 errors en 444.19 s. SetEnvironmentVariable(nom, null) avait laissé des chaînes vides dans le processus ; les guards SQLite ont refusé le chemin relatif résultant avant tout accès au seed. Une expérience de présence (sans valeur) a confirmé la différence entre null et Remove-Item Env:.

Une première relance correctement isolée de l'environnement a été interrompue après identification du test préexistant qui écrivait dans le dépôt. Elle n'est pas comptée comme réussite. Le test a ensuite été isolé en temp système et la suite entière a été rejouée avec succès sur le code final. L'anomalie de mtime diagnostique est conservée dans 04_TMP_AND_CACHE_DISPOSITION.md.

L'invocation initiale mypy du helper sans --explicit-package-bases signalait une double identité de module dans le namespace tests ; le drapeau approprié a résolu la commande, sans changer les packages. Une sonde historique à une seule racine donnait 14/9 ; la commande canonique à deux racines reproduit exactement 15/10.

PROVIDER_CALLS = 0
CANONICAL_SEED_ACCESS = 0
CANONICAL_SEED_WRITES = 0
USER_RUNTIME_WRITES = 0
NETWORK_B06 = 0
