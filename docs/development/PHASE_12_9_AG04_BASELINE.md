# Phase 12.9 — baseline AG-04 après clôture G

## Statut et portée

Cette baseline clôt les lots 12.9-B à 12.9-G consacrés à AG-04 reviewer/critic. Elle
documente le résultat pré-H ; elle ne constitue ni le livrable 12.9-H, ni une autorisation
de merge ou de promotion.

Baseline d'entrée G : `33b2d0004dbe1a4b38cb6d7fbd20b40ad2c01dde` sur
`phase12/12-9-reviewer-critic`, avec `main` et merge-base à
`79731a745b58b80d30e06e292c1eec9353ca46b3`.

## Lots B à F

- B a fixé la frontière provider-neutral : un `ReviewPort`, ses requêtes/résultats
  techniques fermés et l'absence de provider concret.
- C a introduit l'unique `ReviewCoordinator`, responsable de préparer un snapshot
  borné et d'effectuer un unique appel outbound sans retry local.
- D a livré `ReviewerAgent` CAP-V01 et la matérialisation C-09 -> C-10. Le reviewer
  produit une opinion de review ; il ne valide, ne persiste et ne promeut rien.
- E a livré CAP-V02, `ReviewAssessmentSignal` et le signal non canonique
  `CorrectionHandoffSignal` exclusivement destiné à AG-01. AG-04 ne construit jamais
  C-11 et n'appelle jamais AG-03.
- F a ajouté l'unique `ReviewSecurityGuard`, les locators fermés `text_span` et
  `json_path`, les fingerprints de cible/finding, la propagation bornée des signaux de
  sécurité evidence et les refus fail-closed.

## Architecture V01/V02 et sécurité

CAP-V01 consomme C-09 et un `ResolvedReviewTarget` fourni par l'appelant, prépare un
appel provider-neutral, puis matérialise C-10 seulement après validation de lineage,
scope, statut, findings et locators. CAP-V02 relit C-10 et le même snapshot résolu,
revalide les fingerprints et émet une information d'assessment et, si nécessaire, un
handoff vers AG-01.

La sécurité traite cible, evidence et résultat provider comme données non fiables. Elle
ne suit aucune URL, n'exécute aucun outil/fichier, refuse l'exfiltration, l'escalade de
privilège, les actions activables, les locators hors cible, les scopes evidence forgés et
l'authority-smuggling imbriqué. Les warnings restent descriptifs et non autoritatifs ;
les erreurs restent agent-safe sans recopier les contenus bruts.

## Matrice de preuve G

| ID | Workflow | Chaîne prouvée | Invariant principal |
|---|---|---|---|
| G1 | WF-3 | C-09 -> V01 -> C-10 | variantes acceptable, réserves, correction, blocking et partial réelles |
| G2 | WF-3 | C-10 -> V02 | signal borné et handoff AG-01 optionnel |
| G3 | WF-5 | AG-03 -> AG-04 | C-09 cible exactement la version C-08 résolue |
| G4 | WF-5 | AG-03 -> A01 -> AG-04 | validation Application test-only séparée et non mutante |
| G5 | WF-6 | AG-02 -> AG-03 -> A01 -> AG-04 | refs evidence explicites, conflit et sécurité conservés |
| G6 | WF-7 | C-10/V02 -> AG-01 -> C-11 -> AG-03 -> AG-04 | correction et re-review réelles, aucune boucle locale |
| G7 | WF-7 | deux C-11, deux reviews, plans v1/v2 | bornage et arrêts no-progress/cycle par primitives existantes |
| G8 | WF-10 | WF-3/WF-5 -> gate humaine | overlay explicite après review, décision jamais déduite |
| G9 | WF-11 | A01 -> O05 -> A02 | Application/Runtime/Application ; AG-04 absent |
| G10 | sécurité | hostile, locators et objets forgés | fail-closed, aucune action externe |

Les preuves exécutables sont dans
`tests/integration/test_ag04_review_pipeline.py`,
`tests/integration/test_ag04_workflow_compatibility.py` et
`tests/architecture/test_phase_12_9_ag04_closure.py`.

## Production et test-only

G n'ajoute et ne modifie aucun fichier sous `backend/`. Les composants réels
`EvidenceAgent`, `GeneratorAgent`, `ReviewerAgent`, les contrats C-07/C-08/C-09/C-10/C-11,
le sélecteur/compiler de workflows et `PlanRevisionEngine` sont exercés directement.

Les seuls doubles ajoutés sont confinés à `tests/support/review_workflow_fakes.py` :
validation Application, décision AG-01 post-review, gate humaine et promotion probe.
Les ports outbound réutilisent les fakes provider-neutral existants. Ce code est
strictement test-only et ne définit aucun dispatcher, router, handler ou artifact store
de production.

## Responsabilités différées

Le dispatch réel `StepSpec -> agent/use case`, la policy de replan applicative, la
résolution/persistance des artefacts, la décision humaine et la promotion restent hors
du package review et hors du lot G. La promotion exige toujours WF-11 et sa policy ;
`promotion_blocked_by_review=True` est un signal, tandis que `ACCEPTABLE` ne déclenche
aucune promotion.

## Rationalisation B à G

L'audit cumulatif des modèles, ports, coordinator, agent, materializers, assessment,
sécurité, locators, validateurs evidence, scanners d'autorité, erreurs, fakes, ADR et
documentation ne trouve aucune duplication partageant simultanément sémantique,
invariants et frontière d'autorité. Les scanners evidence et review restent distincts
par conception ; les fakes restent hors production.

`RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED`

## Validations de clôture

Validations exécutées avant commit :

- pipeline G : 15 tests PASS ;
- workflows G : 6 tests PASS ;
- fitness de clôture G : 10 tests PASS ;
- régression AG-04 B-G : 276 tests PASS ;
- suite globale : 2 356 tests PASS ;
- Python 3.12.13, `compileall backend`, Ruff global et mypy sur 526 fichiers : PASS ;
- `git diff --check`, audit secrets/I-O et absence de diff `backend/` : PASS ;
- `project.dependencies == []` : PASS.

Le contrôle `git diff --check 79731a745...HEAD`, la propreté du worktree et
l'identité local/distant sont exécutés après création/push du commit G, car ils dépendent
du SHA final.

SHA final G : le commit immuable contenant cette baseline, résolu par
`git rev-parse HEAD` après le commit `test: close phase 12.9 AG-04 fitness` et vérifié
identique à `origin/phase12/12-9-reviewer-critic` après push. Cette forme symbolique évite
une référence SHA auto-référentielle impossible à encoder dans son propre objet Git.
