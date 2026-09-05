# Validations finales B07 après correctif

Baseline : `f28b29f0964d2642b74eb7098f90359d15fb4f0c`. Python 3.12.14, pytest 9.1.1, mypy 2.3.1, Ruff 0.16.4.

| Validation reprise | Résultat réellement obtenu |
|---|---|
| Correctif : régressions et guards ciblés | 20 passed, 9.85 s |
| Test seed réel corrigé seul | 1 passed, 177.47 s |
| Typecheck des deux tests concernés | 0 diagnostic / 2 fichiers |
| Collecte globale sans exclusion | 4952 = 4944 initiaux + 8 nouveaux cas |
| Suite globale complète | **4947 passed, 5 skipped, 0 failed, 0 error ; 1617.21 s ; exit 0** |
| Architecture, incluse dans le global | 872/872 PASS |
| Seed réel, inclus dans le global | 24/24 PASS, y compris retrieval précédemment exclu en B06 |
| Mypy actif | 0/42, exit 0 |
| Mypy backend | 0/683, exit 0 |
| Mypy historique | 15 diagnostics / 10 fichiers, exit 1 attendu ; aucune prétention de PASS |
| Ruff, compileall, pip check | PASS, bytecode/caches externes, aucune installation |

Commande globale : `python -m pytest -q -p no:cacheprovider --basetemp <B07_REPAIR_TEMP>/global-final --tb=short -rs --junitxml=<B07_REPAIR_TEMP>/global-final.xml`. Aucun `--ignore`, `-k`, `-m` ni skip nouveau. Le JUnit complet est conservé hors dépôt ; SHA `673d1133b7010ae76f7f86b29201d9613fdc6244bcc9eaeab3fb8b707219ed1c`. Sa durée de suite est 1616.979 s ; le résumé pytest annonce 1617.21 s. Les 378.824 s architecture sont une somme des durées de cas JUnit, pas une autre exécution.

Les cinq skips existants : trois opt-ins désactivés (calibration live, benchmark sémantique live, offline R1) et deux tests de symlinks non supportés dans ce contexte Windows. Aucun test seed obligatoire n'est skippé. Les nodeids et raisons exacts, sans chemin privé, sont en 13.

Les commandes mypy, ruff et compileall canoniques du premier passage ci-dessous ont été reprises avec caches sous `<B07_REPAIR_TEMP>`. Compileall inclut aussi les deux fichiers de test corrigés. Aucune dépendance n'a été résolue ni installée. Les caches et runtimes de tests sont hors dépôt ; les providers restent désactivés.

## Archive explicite du premier passage — non finale

Le contenu suivant décrit exclusivement la baseline `0404852a3be77381bf7b7c903ee6309e2547487e` et l'arrêt préventif initial. Son résultat incomplet reste incomplet ; la reprise autorisée ci-dessus est une exécution distincte, pas un reclassement rétroactif.

## Collecte, validations et limites de couverture

### Environnement

Python 3.12.14, pytest 9.1.1, mypy 2.3.1, Ruff 0.16.4 ; venv existant, Windows. `pip check` : `No broken requirements found.` Aucun téléchargement ou installation B07.

`PYTHONDONTWRITEBYTECODE=1`, pytest `-p no:cacheprovider`, caches mypy, basetemp, JUnit et bytecode sous `<B07_TEMP>`, hors dépôt. Ruff `--no-cache`. Aucun chemin privé n'est versionné.

Pour le processus global explicitement autorisé : noms V2 injectés, seed identique à la valeur legacy, data/runtime dans le temporaire externe. Les deux noms legacy, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` et les trois flags opt-in sont retirés du processus sans afficher de valeur. Aucun credential n'est résolu.

### Résultats réellement obtenus B07

| Contrôle | Résultat | Code |
|---|---|---:|
| Collecte seule, aucun filtre | 4 944 nodeids uniques, 13.92 s | 0 |
| Ciblés frontières/hygiène/observabilité/HTTP/calibration | 122 passed, 2 skipped, 55.17 s | 0 |
| Mypy actif strict de référence | 0 diagnostic / 42 fichiers | 0 |
| Mypy backend | 0 / 683 fichiers | 0 |
| Dette mypy historique, deux racines exactes | 15 erreurs / 10 fichiers, stable | 1 attendu ; pas un mypy vert |
| Ruff global | All checks passed! | 0 |
| Compileall backend/calibration/supports | PASS, bytecode externe | 0 |
| Freeze historique et références séparées | 40/40, 7 drifts connus préservés ; 2/2 références baseline | 0 |
| Suite globale autoritative | INTERRUPTED_PREVENTIVELY ; aucun bilan final/JUnit | 1 à l'interruption |

Les deux skips ciblés sont `tests/unit/test_local_filesystem_security.py:59` et `tests/unit/test_sqlite_local_boundary.py:94` : création de symlink indisponible dans le contexte Windows utilisé. Les guards complémentaires de rejet des liens/jonctions et les simulations restent présents. Aucun skip n'a été ajouté.

### Commandes

```text
python -m pytest -q -p no:cacheprovider tests/architecture/test_repository_hygiene_b06.py tests/architecture/test_dependency_reproducibility_fitness.py tests/architecture/test_calibration_tooling_boundary.py tests/architecture/test_calibration_tooling_imports.py tests/architecture/test_local_browser_http_boundary_fitness.py tests/architecture/test_minimal_local_observability_fitness.py tests/unit/test_local_filesystem_security.py tests/unit/test_sqlite_local_boundary.py tests/unit/test_local_browser_http_contract.py tests/unit/test_minimal_local_observability.py tests/integration/test_local_browser_http_observability.py tests/integration/test_minimal_local_observability_signals.py --basetemp <B07_TEMP>/pytest-targeted --tb=short -rs
python -m pytest --collect-only -q -p no:cacheprovider --basetemp <B07_TEMP>/pytest-collection
python -m pytest -q -p no:cacheprovider --basetemp <B07_TEMP>/pytest-global --tb=short -rs --junitxml=<B07_TEMP>/global-results.xml
python -m mypy --explicit-package-bases calibration_tooling tests/unit/calibration_tooling tests/integration/calibration_tooling tests/architecture/test_calibration_tooling_imports.py --cache-dir <B07_TEMP>/mypy-active
python -m mypy backend --cache-dir <B07_TEMP>/mypy-backend
python -m mypy --strict --explicit-package-bases --no-pretty --no-color-output --show-error-codes tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py tests/unit/test_pairwise_output_contract_v5_2_4.py --cache-dir <B07_TEMP>/mypy-historical
python -m ruff check --no-cache .
python -m compileall -q backend calibration_tooling tests/support/repository_hygiene.py tests/conftest.py
git diff --check
```

La collecte a été appelée par pytest.main avec un observateur qui relève uniquement les nodeids ; aucun item, marqueur ou critère n'a été modifié. Son hash trié est `1549f3caf56cc11e7ed1bb13fb266c84ce534c0838d0293a91631388d4cb56a1`.

### B06 n'est pas la suite seed complète

Commande B06 : `python -m pytest -q -p no:cacheprovider --ignore=tests/non_functional/test_retrieval_quality_real_gate.py --basetemp <temp-externe> --tb=short`, variables de seed et credentials absentes.

Preuve réutilisée : **4 915 passed, 28 skipped, 0 failed, 436.91 s**. Les 28 skips sont 23 cas SQLite sans seed configuré, trois gates opt-in désactivées et deux symlinks Windows. Un test supplémentaire était entièrement exclu de la collecte : `test_retrieval_quality_real_gate_is_reproducible_on_two_fresh_runtimes`.

La collecte B07 contient 4 944 tests : les 4 943 éléments B06 plus ce test exclu. Elle retrouve 24 tests seed réels, tous listés dans `08_MACHINE_EVIDENCE.json`. Aucune réussite de ces 24 tests n'est revendiquée pour le run interrompu.

Les 872 tests architecture sont inclus dans les 4 944, pas ajoutés au total. Leur résultat complet réutilisé est **872 passed en 214.77 s**, B06 sur le graphe technique identique. Le run global interrompu ne crée pas une nouvelle preuve architecture complète. Les 122 ciblés se recouvrent eux aussi avec le global ; ils ne sont pas additionnés.

Les trois opt-ins désactivés sont `RUN_PEDAGOGICAL_LIVE_CALIBRATION`, `RUN_F2B_LIVE_SEMANTIC_BENCHMARK` et `RUN_F2B_OFFLINE_R1`. Leur non-exécution n'est pas une validation fournisseur/semantic et ne doit pas masquer le test seed obligatoire.

### Arrêt préventif et diagnostic non transformé en PASS

Un seul run global a été lancé, sans exclusion. Pendant le ré-audit, l'appel seed `connect_sqlite(seed_path, readonly=True)` de `tests/integration/test_sqlite_runtime_real_gate.py:162` a été identifié. Le paramètre `immutable` vaut False par défaut ; une lecture WAL non immutable peut toucher les sidecars. Le mode immutable doit rester réservé au seed authentifié, pas aux lecteurs runtime.

Arrêt volontaire par interruption du processus avant de poursuivre la validation de ce point. Aucun échec d'assertion n'est présenté comme diagnostic acquis ; le risque n'a pas été reproduit sur le seed pour le prouver. La progression partielle n'est ni un bilan de succès ni une preuve des tests réels. Aucun JUnit final n'a été produit. Aucun rerun n'a été lancé.

La première sonde de configuration avait échoué `LEGACY_SETTING_FORBIDDEN` ; la première sonde physique avait été refusée par les permissions du contexte. Ces prérequis ont ensuite été levés par l'accord de processus et le contrôle de fichiers autorisé, sans fallback ni correction persistante. Les erreurs de syntaxe/localisation des commandes préparatoires ne sont pas des résultats de test.
