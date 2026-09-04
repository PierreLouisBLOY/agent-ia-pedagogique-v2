# Phase 12.17.4 — Gates de l'exécution future

## Préconditions fail-closed

1. HEAD et diff de départ identifiés ; les modifications utilisateur sont
   préservées.
2. ADR de frontière `calibration_tooling` accepté avant le premier fichier code.
3. snapshot SHA-256 des 40 chemins historiques sur la baseline de départ.
4. les sept relations supersédées 12.16 -> 12.17.2A sont enregistrées comme
   telles, jamais comparées au mauvais hash.
5. aucune autorisation provider live n'est active ou consommée.
6. le seed réel n'est requis que pour la gate B08 ; son absence fait SKIP
   explicite des tests conditionnels, jamais PASS.

## Gates statiques

| Gate | Critère PASS |
|---|---|
| `G-STATIC-01` | `mypy backend` : 0 erreur / ensemble complet |
| `G-STATIC-02` | mypy strict import-driven sur `calibration_tooling` et ses tests : 0 erreur |
| `G-STATIC-03` | aucun nouveau diagnostic par rapport aux deux commandes |
| `G-STATIC-04` | Ruff sur tous les fichiers Python changés, puis `ruff check .` : PASS |
| `G-STATIC-05` | `compileall backend calibration_tooling` : PASS |
| `G-STATIC-06` | `git diff --check` : PASS |

Commandes de référence :

```powershell
.\.venv\Scripts\python.exe -m mypy backend --no-pretty --no-color-output --show-error-codes
.\.venv\Scripts\python.exe -m mypy --strict --explicit-package-bases --no-pretty --no-color-output --show-error-codes calibration_tooling tests/unit/calibration_tooling tests/integration/calibration_tooling
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q backend calibration_tooling
git diff --check
```

L'ancien root V5.2.4 est rejoué séparément et doit reproduire exactement la
dette historique attendue. Il ne fait pas partie de `G-STATIC-02` :

```powershell
.\.venv\Scripts\python.exe -m mypy --strict --explicit-package-bases --no-pretty --no-color-output --show-error-codes tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py tests/unit/test_pairwise_output_contract_v5_2_4.py
```

Résultat attendu tant que les sources restent immuables : `15 erreurs / 10
fichiers`, sans diagnostic nouveau. Tout autre résultat exige une analyse, pas
une mise à jour automatique de l'attendu.

## Gates d'architecture

| Gate | Critère PASS |
|---|---|
| `G-ARCH-01` | aucun import `tests` depuis `backend`, `evaluation_harness`, `calibration_tooling` |
| `G-ARCH-02` | aucun import `calibration_tooling` depuis `backend` ou `evaluation_harness` |
| `G-ARCH-03` | SDK/provider absent des contracts et de l'application |
| `G-ARCH-04` | SQL et `sqlite3.Row` confinés aux adapters/infrastructure |
| `G-ARCH-05` | API absente du lot 12.17.4E ; handoff 12.17.5 seulement |
| `G-ARCH-06` | les dix vocabulaires ont un owner, aucun dans shared kernel |
| `G-ARCH-07` | un seul CLI/runner actif ; les sept générations sont historiques |

## Tests ciblés

Les chemins exacts sont créés par les batches, puis exécutés ensemble :

```text
tests/architecture/test_calibration_tooling_boundary.py
tests/unit/calibration_tooling/
tests/integration/calibration_tooling/
tests/unit/test_sqlite_runtime_persistence.py
tests/architecture/test_sqlite_runtime_persistence_fitness.py
tests/architecture/test_resource_library_application_sqlite_fitness.py
tests/integration/test_sqlite_runtime_real_gate.py          [seed conditionnel]
tests/integration/test_sqlite_resource_application_e2e_real_gate.py [seed conditionnel]
```

Chaque batch doit publier la commande, le compte réellement exécuté et la
sortie. Un skip de seed est déclaré comme tel.

## Immutabilité calibration 12.16

- 40/40 chemins du registre conservent leur hash de départ 12.17.4E ;
- tous les `MANIFEST_SHA256.txt` 12.16 existants sont octet-identiques ;
- les identités finales V5.2.4 restent inchangées : parser `2037ce...`, scorer
  `a79928...`, matrice `3c3a9e...`, pricing `31f2a9...`, gate `8dc0bd...`, scope
  `c65e64...`, contrat `8a40ce...` ;
- aucun ledger, output ou artifact runtime historique n'est rappelé, déplacé ou
  ajouté à Git ;
- aucune réouverture, calibration ou nouvelle conclusion de Phase 12.16.

`HISTORICAL_HASHES_EXPECTED_UNCHANGED = 40`.

## Seed/runtime

Avant et après B08 :

```text
seed SHA-256 = 38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134
seed size = 105553920
inventory = 98 tables / 20 explicit indexes / 7 triggers / 2 views
integrity_check = ok
quick_check = ok
foreign_key_violations = 0
seed migrations = 0
```

La présence/taille/hash/mtime des sidecars est capturée PRE et POST. Toute
création ou modification inattendue bloque ; aucun sidecar seed n'est supprimé.
Les migrations, WAL, SHM et backups ne concernent que la runtime fraîche.

## Provider, secrets et données

```text
PROVIDER_CALLS = 0
OPENAI_CALLS = 0
ANTHROPIC_CALLS = 0
CREDENTIAL_RESOLUTIONS_IN_TESTS = 0
```

Tests par fake/client injecté uniquement. Aucun secret, base, chemin local,
document complet ou projection pédagogique n'est transféré. Les logs/artifacts
subissent un scan de valeurs sensibles avant PASS.

## Suite globale

Après toutes les gates ciblées, la suite globale de `ENVIRONMENT.md` est
obligatoire car le changement est transverse :

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Les gates réelles dépendant du seed sont exécutées dans un sous-run explicite
avec le chemin local fourni par environnement et un basetemp hors dépôt. Leur
résultat est séparé du run sans seed.

## Critère final

Le lot 12.17.4E est PASS uniquement si toutes les gates applicables sont vertes,
les skips sont explicités, les 40 hashes sont identiques à leur snapshot, le
seed est inchangé et les compteurs provider restent zéro. Sinon : arrêt, aucun
commit de succès, rapport du premier écart et rollback du batch fautif.
