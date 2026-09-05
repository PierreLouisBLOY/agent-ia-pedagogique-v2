# B07 — Addendum correctif du test seed (avant commit)

## Autorité et état antérieur

Autorisation propriétaire reçue dans la conversation le 2026-09-05 : correction limitée du test seed identifié, non-régression ciblée, configuration de processus seulement, aucun code applicatif ou donnée utilisateur modifié ; commit local borné après succès ciblé, puis reprise B07. Aucun horodatage de signature n'est inventé.

Baseline de référence : `0404852a3be77381bf7b7c903ee6309e2547487e`.

Le nouveau bundle `PROJET_V2_B07_CORRECTIF_TEST_SEED_ET_REPRISE.zip` précise le même enchaînement ; SHA-256 `a800457b1fb42e5ec0f18c49240b723eb9e3ec51f6c4ab76b2cf60f9f8500869`, quatre entrées de manifeste vérifiées. Le texte d'autorisation préparé dans le bundle n'est pas la source de permission : celle-ci est le message explicite du propriétaire.

L'ancien état B07 reste conservé : 14/16 gates, run global interrompu et non PASS, manifeste `8d16ea5340d792c9123dfec1b5c4f0ba0c7ff8f6eca720c9a80002597dda3f8d`. Les douze documents existants sont distincts du commit correctif, non supprimés et non indexés avec lui.

## Cause et correctif exact

Nodeid : `tests/integration/test_sqlite_runtime_real_gate.py::test_seed_gate_is_exact_and_read_only`.

L'ancienne ligne 162 appelait `connect_sqlite(seed_path, readonly=True)`, sans immutable. La fixture autouse inspectait déjà le seed ; elle doit également vérifier son identité de fichier avant sa première connexion.

Le correctif, exclusivement dans ce fichier de test :

- authentifie présence, taille et SHA-256 via le snapshot de fichiers avant toute ouverture test-side ;
- appelle explicitement `connect_sqlite(..., readonly=True, immutable=True)` ;
- ferme la connexion avec closing ;
- conserve le CREATE TABLE refusé et toutes les assertions antérieures ;
- contrôle le principal et les sidecars dans un finally, y compris à la sortie de la fixture.

Le helper applicatif n'est pas modifié. Les lecteurs runtime restent non immutable et compatibles avec WAL. L'inspection des autres ouvertures directes seed dans le périmètre repris n'identifie pas une autre omission : le test lifecycle utilise déjà mode=ro&immutable=1 ; les autres parcours utilisent l'inspection/provisionnement authentifiés. Aucun autre test n'est remédié.

## Non-régression et validations réellement exécutées

`tests/unit/test_seed_read_only_gate_regression.py` contient huit cas : présence/taille/hash invalides bloquent toute connexion ; read-only et immutable explicites ; fermeture unique ; dérive de chacun des trois sidecars détectée ; URI réellement échappée avec mode=ro&immutable=1, query_only et refus d'écriture sur fixture système temporaire. Provisionnement/migration sont interdits par interception pendant le test seed.

| Contrôle | Résultat |
|---|---|
| Non-régression + guards lifecycle/persistence/calibration boundary | 20 passed, 9.85 s |
| Test seed réel corrigé avec fixture complète | 1 passed, 177.47 s |
| Mypy des deux fichiers de test | 0 diagnostic / 2 fichiers |
| Ruff ciblé | PASS |
| Compileall ciblé, bytecode externe | PASS |
| Freeze historique / références séparées | 40/40 et 2/2 |
| Identités protégées, migrations, locks, preuve locale | 48/48 inchangées |
| Seed et principal/sidecars PRE/POST | Identiques, y compris taille/mtime/identité et fichiers vides |
| Diff-check | PASS |

Commandes exécutées (tous les chemins temporaires sont hors dépôt) :

```text
python -m pytest -q -p no:cacheprovider tests/unit/test_seed_read_only_gate_regression.py tests/architecture/test_sqlite_seed_runtime_lifecycle_fitness.py tests/architecture/test_sqlite_runtime_persistence_fitness.py tests/architecture/test_calibration_tooling_boundary.py --basetemp <CORRECTIVE_TEMP>/targeted-final --tb=short
python -m pytest -q -p no:cacheprovider tests/integration/test_sqlite_runtime_real_gate.py::test_seed_gate_is_exact_and_read_only --basetemp <CORRECTIVE_TEMP>/real-targeted --tb=short
python -m mypy --explicit-package-bases tests/unit/test_seed_read_only_gate_regression.py tests/integration/test_sqlite_runtime_real_gate.py --cache-dir <CORRECTIVE_TEMP>/mypy-targeted
python -m ruff check --no-cache tests/integration/test_sqlite_runtime_real_gate.py tests/unit/test_seed_read_only_gate_regression.py
python -m compileall -q tests/integration/test_sqlite_runtime_real_gate.py tests/unit/test_seed_read_only_gate_regression.py
git diff --check
```

Une première version de la non-régression avait quatre diagnostics mypy d'import non ré-exporté ; les constantes sont maintenant importées directement depuis leur module propriétaire. Ce diagnostic n'est pas présenté PASS et n'a nécessité aucun changement applicatif.

## Identités et commit autorisé

- Test PRE : `f62f11f7a44a5c11bd4b5844b9bf43b703be6449c8dacc55b84e673a549836f0`.
- Test POST : `ab7bfe37360c70449e4032116fa236962eee8d1b1ec5105066643215e9e4c902`.
- Non-régression : `e63e22dfd6b9731144650193f43315696b6370eb43bed70cfe1fc8b31789b662`.
- Test hors registre des 40 protégés ; aucun rebind historique requis.

Allowlist littérale du commit correctif : ces deux tests, le présent addendum et `12_SEED_TEST_CORRECTIVE_EVIDENCE.json`. Aucun autre document B07, base, log, cache ou fichier applicatif.

Le SHA du commit correctif ne peut figurer dans son propre contenu ; il est rapporté après création et lié dans la reprise B07. Ce succès ciblé n'est ni une réussite globale ni la clôture B07. Aucun push, merge, provider, résolution réseau, migration utilisateur ou configuration persistante.
