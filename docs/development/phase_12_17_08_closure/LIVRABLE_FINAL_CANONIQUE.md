# Projet V2 — Clôture 12.17.8-B07

## Verdict

**B07 PASS — 16/16 gates ; 12.17.8 clôturée**, effectif après le commit documentaire local et son postcontrôle propre décrits en 14. Baseline technique testée : `f28b29f0964d2642b74eb7098f90359d15fb4f0c`.

Le correctif autorisé protège l'ouverture du seed par authentification SHA puis read-only + immutable, sans changer le code applicatif ni les lecteurs runtime. Le premier passage interrompu reste tracé comme tel.

## Résultats vérifiés

- Suite complète : **4947 passed, 5 skipped, aucun échec**, 1617.21 s.
- **24/24 tests seed réels** et **872/872 architecture** passent, inclus dans ce total.
- Huit nouvelles régressions ; 20 tests ciblés et le test seed réel corrigé réussis avant le commit correctif.
- Mypy actif 0/42, backend 0/683 ; dette historique inchangée à 15 diagnostics/10 fichiers.
- Seed et sidecars PRE/POST strictement identiques ; aucun accès à la runtime utilisateur.
- 40/40 fichiers gelés, deux références séparées et 23 manifestes sources conformes.
- 203 ensembles locaux conservés sans drift, suppression ni pollution du dépôt.
- Aucun appel fournisseur, credential résolu, réseau de résolution, push ou merge.

Les cinq skips sont les trois opt-ins existants désactivés et deux tests de symlinks indisponibles sous Windows ; aucun skip de masquage ajouté.

## Limites et arrêt

Migration 002 non déclarée déployée chez l'utilisateur ; configuration persistante inchangée. Les quatre findings historiques et quatre différés restent explicites. Les contrats HTTP ne prouvent pas une application utilisable. RELEASE_THRESHOLD reste NONE.

**12.18 n'est pas démarrée.** La clôture de toute la Phase 12.17 n'est pas déduite de B07. Revue explicite requise avant merge.

## Dossier

- [Périmètre et autorité](01_SCOPE_BASELINE_AUTHORITY.md) ; [sept lots](02_SEVEN_BATCH_MATRIX.md).
- [Seize gates](03_FINAL_GATES.md) et [JSON](04_FINAL_GATES.json).
- [Tests](05_TEST_COLLECTION_AND_EVIDENCE.md) ; [seed/runtime](06_SEED_RUNTIME_002_BOUNDARY.md) ; [Git/rétention](07_GIT_MANIFESTS_AND_RETENTION.md).
- [Snapshot historique du passage interrompu — non final](08_MACHINE_EVIDENCE.json).
- [Résiduels](09_RESIDUAL_REGISTER.json) ; [handoff](10_CLOSURE_DECISION_AND_HANDOFF.md).
- [Correctif autorisé](11_SEED_TEST_CORRECTIVE_ADDENDUM.md) et [preuve ciblée](12_SEED_TEST_CORRECTIVE_EVIDENCE.json).
- [Preuves de la reprise complète](13_RESUMED_GLOBAL_EVIDENCE.json) ; [transaction et postconditions](14_FINAL_RECONCILIATION_ADDENDUM.md).
- [Manifeste final](MANIFEST_SHA256.txt).
