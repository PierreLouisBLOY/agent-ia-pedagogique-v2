# Phase 12.15 G — Clôture de la suite pédagogique canonique

## 1. Parent F

Le parent exact de G est `87569bfb257c18da89d2e9a54e4d01d5dd6def47`, commit
`test: close transversal security recovery observability e2e`, sur la branche
`phase12/12-15-canonical-pedagogical-e2e`.

## 2. État A à F

La chaîne fonctionnelle antérieure est linéaire depuis `main` :

- A : audit/scénarios pédagogiques E2E, intégré dans le corpus B ;
- B : `37aeffd`, corpus pédagogique golden canonique ;
- C0 : `af4a924`, persistance SQLite et migration runtime ;
- C1 : `3fb936c`, recherche/evidence SQLite ;
- C2 : `512a595`, lecture de ressource via Application et SQLite ;
- D : `67503cf`, génération/transformation pédagogique ;
- E : `01f8792`, assessment/correction/QCM ;
- F : `87569bf`, sécurité/recovery/observabilité transverses.

## 3. Composite reuse map

La façade test-only `tests/e2e/core/full_suite_adapters.py` délègue sans logique
métier nouvelle : SCN-01 à C2, SCN-02 à C1, SCN-03 à SCN-05 à D, et SCN-06
à SCN-08 à E. Les factories d'input et de fixture routent par `case_id`, les
invariants par préfixe canonique et l'executor par cible. Toute clé inconnue
échoue en mode fermé. Le cleanup de fixture reste délégué à son propriétaire.

## 4. SQLite wiring

Chaque run authentifie le seed, provisionne un runtime frais par
`database/migrations/001_document_sha256_check.sql`, puis ouvre cinq ressources
indépendantes : resource store C2, search/content C1 et search/content D-SCN04.
C2 traverse `GetResourceQuery`, `ResourceLibraryUseCaseInbound`, le wrapper de
comptage et `UseCaseRouter`. C1 et D construisent chacun leur propre
`EvidenceAgent`. Toutes les connexions sont fermées avant suppression du
runtime, de son WAL et de son SHM. Le seed reste inchangé avant/après.

Seed authentifié : 105 553 920 octets, SHA-256
`38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`.

## 5. Huit scénarios

Un unique `EvaluationRunner.run_suite()` consomme
`CANONICAL_PEDAGOGICAL_SUITE` dans l'ordre SCN-01 à SCN-08. Les huit verdicts
de cas et le verdict de suite sont `PASS`, sans erreur d'infrastructure.

## 6. Matrice des 37 assertions

La cardinalité par scénario est `(4, 5, 4, 3, 4, 5, 6, 6)`, total 37. Les 37
assertions hard sont `PASS`. Tous les `score_results` et `rubric_results` sont
vides ; aucune calibration 12.16 n'est anticipée.

## 7. Couverture exacte des workflows

| Workflow | Scénarios |
|---|---|
| WF-0 | SCN-01, SCN-07 |
| WF-1 | SCN-02, SCN-07 |
| WF-2 | SCN-03 |
| WF-3 | SCN-08 |
| WF-4 | SCN-04 |
| WF-5 | SCN-05 |
| WF-6 | SCN-06 |
| WF-7 | SCN-07 |
| WF-8 | SCN-06 |
| WF-9 | SCN-08 |
| WF-10 | SCN-05 |
| WF-11 | SCN-08 |

## 8. Witness cross-check

- SCN-01 : une route Application, OP-03, ressource logique préservée ;
- SCN-02 : retrieval dégradé borné, `notion:absence`, matérialisation réelle ;
- SCN-03 : candidat généré, état `candidate` ;
- SCN-04 : evidence `notion:tva`, ordre AG-02 puis AG-03, lineage préservée ;
- SCN-05 : revue unique puis gate externe approuvée ;
- SCN-06 : fan-out evidence, join, génération, validation et revue ;
- SCN-07 : correction `v2`, re-review, lecture Application finale réussie ;
- SCN-08 : deux variantes, sélection/revue indépendante, promotion unique.

## 9. Full suite run A

Le run A utilise un runtime SQLite frais, exécute les huit cas et les 37
assertions avec verdict `PASS`, puis supprime runtime/WAL/SHM.

## 10. Full suite run B

Le run B utilise un second runtime SQLite frais et isolé. Il produit les mêmes
verdicts, cardinalités, rapports et preuves de nettoyage que le run A.

Gate dédiée A/B : 1 test `PASS`, 0 skip, 129,16 s.

## 11. Reproductibilité

Les contenus JSON A/B sont identiques byte à byte. Les contenus Markdown A/B
sont identiques byte à byte. Les deux contenus régénérés sont également
identiques byte à byte aux artefacts suivis. La gate SQLite cumulée G +
C0/C1/C2/D donne 21 `PASS`, 0 skip, en 464,36 s.

## 12. Rapport JSON

`PHASE_12_15_G_CANONICAL_SUITE_REPORT.json` est un output exclusif de
`EvaluationArtifactFactory` : 7 015 octets, SHA-256
`7244dc1c362d6e0d9c9d0ee8f29522b8273479067f6353e0fda27d63ad21e1d8`.

## 13. Rapport Markdown

`PHASE_12_15_G_CANONICAL_SUITE_REPORT.md` est un output exclusif de
`EvaluationArtifactFactory` : 5 061 octets, SHA-256
`0dc93478bd7f32284fb802876f7fcaed3b3b18f158ecaecbd871ec6615651c6d`.

## 14. Minimisation du contenu brut

La projection est allowlistée. Les fragments evidence, sources de fixtures,
contenus générés, chemins locaux, chemin du seed, URLs fournisseur et fichiers
SQLite ne figurent dans aucun rapport. Les tests croisent explicitement chaque
texte brut collecté contre les octets JSON et Markdown.

## 15. Régression transverse F

La sélection F imposée donne 57 `PASS` en 2,23 s : intégration
sécurité/recovery/observabilité, bindings unitaires et fitness architecture.

## 16. Delta backend, corpus et harness

Delta `backend/` : zéro. Delta `evaluation_harness/` : zéro. Delta du corpus,
des fixtures, du catalogue d'assertions et des registries : zéro. G ajoute
uniquement une façade et des tests de consolidation, deux rapports et cette
baseline.

## 17. Neutralité fournisseur

Aucun SDK, réseau, provider, modèle, embedding, scorer ou judge n'est ajouté.
La façade ne contient aucun SQL direct et n'accorde aucune autorité métier aux
agents. `[project].dependencies = []` reste exact.

## 18. Gates globales et statiques

- sélection cumulative 12.15 : 230 `PASS`, 21 skips historiques, 24,68 s ;
- suite globale : 3 894 `PASS`, 21 skips historiques, 182,95 s ;
- Python : 3.12.13 ;
- Ruff : PASS ;
- mypy `backend evaluation_harness` : PASS, 668 fichiers ;
- compileall `backend evaluation_harness tests` : PASS ;
- `git diff --check` : PASS.

## 19. Dettes explicitement différées

```text
EXISTING_RUNTIME_REOPEN_POLICY = DEFERRED
Phase7 repository provenance mismatch = 12.17
READ-15 version_ref/include = DEFERRED
R02/A01/A02 concrete business Application implementations = NOT CLAIMED
REAL_BUSINESS_PROMOTION_PERSISTENCE = NOT IMPLEMENTED
provider/model calibration = 12.16
quality rubrics = 12.16
```

Ces dettes ne bloquent pas la suite fonctionnelle fermée. Aucun ADR n'est
requis : `ADR_REQUIRED = NO`.

## 20. Handoff H1

G est le dernier lot fonctionnel 12.15. La suite canonique est prête pour
l'audit/gate pré-merge H1. H1 n'est ni commencé ni revendiqué dans ce lot.
