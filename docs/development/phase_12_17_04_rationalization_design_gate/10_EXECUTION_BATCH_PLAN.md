# Phase 12.17.4 — Plan d'exécution atomique

## Séquencement

```text
EXECUTION_BATCH_COUNT = 9
B01 -> B02 -> B03 -> B04 -> B05
B01 -----------------> B06 -> B07 -> B08
B01 -------------------------------> B09
FINAL_GATE requires B05 + B08 + B09
```

Les chemins sont prévisionnels. Toute différence de périmètre, nouveau package
ou migration déclenche une nouvelle revue du batch avant écriture.

## B01 — Frontière et lock historique (`RC-02`)

- **Scope** : ADR du package `calibration_tooling`, registre machine-readable
  des 40 hashes de baseline et tests de frontière.
- **Fichiers prévus** : `architecture/adr/ADR-P12-068-active-calibration-tooling-boundary.md`,
  `tests/architecture/test_calibration_tooling_boundary.py`, un manifest de
  hashes sous `docs/development/phase_12_17_04_execution/`.
- **Diagnostics fermés** : aucun directement ; empêche leur correction dans les
  fichiers historiques.
- **Tests** : hash guard 40/40, manifests 12.16 inchangés, imports interdits.
- **Risque** : figer une mauvaise baseline ; les sept deltas 12.17.2A doivent
  être explicitement enregistrés.
- **Rollback** : retirer uniquement les nouveaux documents/tests.
- **Invariants** : zéro octet modifié sous les 40 chemins.
- **Commit séparé** : TRUE.

## B02 — Contrats et runner unique (`RC-03`, partie `RC-05`)

- **Scope** : package, modèles discriminés, policy durable, budget et runner
  offline sans adapter réel.
- **Fichiers prévus** : `calibration_tooling/contracts/*.py`,
  `calibration_tooling/application/{ports,service}.py`,
  `calibration_tooling/runtime/{authorization,budget,ledger,runner}.py`.
- **Diagnostics fermés** : conception active de `MYPY-007/008/009/017/018/019/021/022/033`.
- **Tests** : cardinalité, budget, dispatch absolu/pairwise, auth one-shot,
  ambiguity ledger, strong-only/no-threshold.
- **Risque** : recopier une mécanique incidente V4/V5.
- **Rollback** : suppression du nouveau package non composé.
- **Invariants** : provider-neutral, zéro réseau, zéro autorité métier.
- **Commit séparé** : TRUE.

## B03 — Adapter Anthropic actif (`RC-01`)

- **Scope** : nouveau mapping/parser/transport/scorer contre client injecté.
- **Fichiers prévus** : `calibration_tooling/adapters/anthropic/*.py`, tests
  unitaires dédiés.
- **Diagnostics fermés** : `MYPY-001` à `MYPY-005` dans le graphe actif.
- **Tests** : structured output, `NoReturn` narrowing, redaction, zéro retry,
  max-tokens, response invalide, provider indisponible.
- **Risque** : divergence avec ADR-P12-064 ou fuite de secret.
- **Rollback** : retirer l'adapter ; B02 reste testable avec fake.
- **Invariants** : aucun import depuis `tests`, aucun appel live.
- **Commit séparé** : TRUE.

## B04 — Composition, imports et CLI (`RC-04`)

- **Scope** : composition explicite, télémétrie sûre et point d'entrée unique.
- **Fichiers prévus** : `calibration_tooling/runtime/{configuration,composition,cli}.py`,
  `calibration_tooling/observability/*.py`, tests d'intégration offline.
- **Diagnostics fermés** : `MYPY-001` à `MYPY-023` disparaissent de la
  traversée active ; aucun root actif ne traverse V4/V5.x.
- **Tests** : import graph, fake client, fail-closed, allowlist/budget/ledger.
- **Risque** : lecture implicite d'env ou activation accidentelle.
- **Rollback** : retirer composition/CLI, conserver les composants isolés.
- **Invariants** : configuration injectée, live désactivé par défaut.
- **Commit séparé** : TRUE.

## B05 — Fermeture typing et dépréciation active (`RC-05`)

- **Scope** : tests de parité, documentation `HISTORICAL_ONLY`, suppression des
  derniers imports actifs vers les anciens roots.
- **Fichiers prévus** : tests sous `tests/unit/calibration_tooling/`,
  `tests/integration/calibration_tooling/` et docs d'exploitation.
- **Diagnostics fermés** : 15/15 par isolation du graphe actif.
- **Tests** : mypy backend 0, mypy active import-driven 0, ancien root reproduit
  séparément à 15/10, Ruff, compileall.
- **Risque** : annoncer les sources historiques comme corrigées.
- **Rollback** : revenir aux imports de B04 sans toucher aux historiques.
- **Invariants** : aucun ignore/stub/exclude ; hashes 40/40.
- **Commit séparé** : TRUE.

## B06 — Vocabulaires et mappings owners (`RC-06`)

- **Scope** : types par bounded context puis traduction explicite des dix
  familles ; pas de migration.
- **Fichiers prévus** : modules Domain/Application owners, mappers SQLite et
  tests de conformance. Les chemins exacts sont confirmés owner par owner avant
  le batch.
- **Diagnostics fermés** : aucun mypy historique ; prévention de nouveaux
  littéraux non typés.
- **Tests** : 10/10 mappings, transitions, valeurs inconnues, absence de type
  métier dans shared kernel.
- **Risque** : confondre default technique et état métier.
- **Rollback** : un owner à la fois ; mappers antérieurs conservés jusqu'au test
  de parité.
- **Invariants** : pas de SQL hors adapters, pas d'owner infrastructure.
- **Commit séparé** : TRUE, avec commits owner-scopés si le diff dépasse un lot
  minimal.

## B07 — Configuration de chemins (`RC-07`)

- **Scope** : `PROJET_V2_DATA_DIR`, `PROJET_V2_CANONICAL_DB`,
  `PROJET_V2_RUNTIME_DB`, defaults OS et compat stricte des anciens noms.
- **Fichiers prévus** : schemas/loaders SQLite, composition et tests unitaires.
- **Diagnostics fermés** : aucun résiduel ; contrôle portable futur.
- **Tests** : Windows/non-Windows simulé, conflits, chemin nominatif absent,
  symlink/junction, redaction.
- **Risque** : fallback silencieux vers un mauvais seed.
- **Rollback** : conserver les anciens noms comme source unique.
- **Invariants** : aucune découverte globale du disque, aucun chemin privé Git.
- **Commit séparé** : TRUE.

## B08 — Cycle seed/runtime et sidecars (`RC-08`)

- **Scope** : snapshots PRE/POST, copie atomique, runtime-only WAL/migrations et
  backup runtime.
- **Fichiers prévus** : provisioning/composition SQLite, tests unitaires et gate
  réelle conditionnée au seed local exact.
- **Diagnostics fermés** : finding sidecar contrôlé ; deux candidats migration
  restent exclus.
- **Tests** : hash/size/98-20-7-2, integrity/quick/FK, destination distincte,
  PRE/POST sidecars, migration runtime, backup/restore frais.
- **Risque** : toucher le seed ou supprimer un sidecar non attribuable.
- **Rollback** : supprimer uniquement la runtime fraîche de test après fermeture
  vérifiée ; ne jamais supprimer un sidecar seed.
- **Invariants** : seed inchangé, migrations seed = 0.
- **Commit séparé** : TRUE.

## B09 — Legacy review et handoff API (`RC-09`)

- **Scope** : matérialiser la trace rétrospective OD-02 et publier les contraintes
  OD-03/04/07 pour 12.17.5.
- **Fichiers prévus** : `docs/legacy-review/{README,phase_7_sqlite_runtime_reuse}.md`,
  test documentaire et handoff 12.17.5.
- **Diagnostics fermés** : aucun mypy ; ferme `EX-01` documentaire.
- **Tests** : liens/identités, marqueur non rétroactif, API scope Resource seul.
- **Risque** : inventer une approbation passée.
- **Rollback** : retirer la nouvelle trace ; aucune histoire existante modifiée.
- **Invariants** : `RETROACTIVE_APPROVAL=FALSE`, API non implémentée ici.
- **Commit séparé** : TRUE.

## Gate finale

Une suite globale est justifiée après les tests ciblés : les batches touchent
un nouveau package top-level, les imports, la configuration, plusieurs adapters
SQLite et des frontières d'architecture. Elle ne démarre qu'après passage de
toutes les gates de `11_EXECUTION_GATES.md`.
