# Phase 12.15-D — Baseline génération, transformation et revue E2E

## 1. Parent, portée et décision ADR

D a pour parent exact `512a595ee11eafdfa9a9ff13e6aa3228fd43cd35`
(C2). Le lot ferme uniquement SCN-03, SCN-04 et SCN-05. Il ne commence ni
SCN-06/07/08, ni les lots E/F/G.

`ADR_REQUIRED = NO`. D assemble les owners et décisions déjà canoniques :
WorkflowSelector/PlanCompiler, AG-02 Evidence, AG-03 génération/transformation,
AG-04 revue et GateEngine. Aucun owner, capability, workflow, contrat durable ou
stockage n'est créé.

## 2. Audit M04/M05 et matrice des owners

L'audit de `backend/modules/pedagogical_design` (M04) et
`backend/modules/transformation_assembly` (M05) constate des frontières de
module sans use case Application concret réutilisable pour cette slice. Les hard
assertions D portent sur les productions candidates AG-03, pas sur une mutation
métier ou une identité patrimoniale. Aucun seam parallèle IP-04/IP-05 et aucune
persistance M08 ne sont donc ajoutés.

| Responsabilité | Owner réel exercé | Port/double test-only |
| --- | --- | --- |
| sélection et compilation | WorkflowSelector / PlanCompiler | aucun |
| Evidence SCN-04 | AG-02 EvidenceAgent / RetrievalCoordinator | aucun : adapters SQLite C1 réels |
| génération/transformation | AG-03 GeneratorAgent / GenerationCoordinator / GenerationOutputGuard | RecordingGenerationPort |
| revue sémantique | AG-04 ReviewerAgent / ReviewCoordinator | RecordingReviewPort |
| autorité de gate | GateEngine | RecordingGateDecisionSource, décision humaine externe |
| continuation témoin | aucune responsabilité métier | compteur test-only, sans effet |

Le principe appliqué est `FAKE_PORT != FAKE_OWNER`. Les doubles fournissent
seulement des résultats techniques courts et déterministes. Aucun provider,
modèle, SDK ou réseau n'est appelé.

## 3. SCN-03 — cours via WF-2

```text
production_required = true
-> WorkflowSelector -> WF-2
-> PlanCompiler -> AG-03 / CAP-G01
-> ProductionRequest(target_ref=None, evidence_refs=())
-> GeneratorAgent -> GenerationCoordinator -> RecordingGenerationPort
-> GenerationOutputGuard -> ProductionCandidate(CANDIDATE)
```

Le plan ne contient ni AG-02, ni AG-04, ni gate. Le port est appelé une fois avec
l'opération `GENERATE`. La candidate conserve la lineage `CAP-G01` et les quatre
sections exactes du corpus : `objective`, `concept`, `example`, `summary`. Elle
ne porte aucun statut validated/promoted. Les quatre assertions hard `workflow`,
`generation-path`, `required-sections` et `authority-smuggling` passent dans le
harness réel.

## 4. SCN-04 — Evidence réelle puis transformation via WF-4

Les termes `tva`, `franchise` et `taxe` ont été audités en lecture seule. `tva`
est le seul choix stable et cohérent avec BTS CG : la recherche structurée et
lexicale converge sur `notion:tva`. `franchise` est ambigu et `taxe` trop large.
La décision est donc `SCN04_REAL_DB_EVIDENCE = TRUE`, query `tva`.

```text
external_evidence_required = true + production_required = true
-> WF-4
-> AG-02 / CAP-E01 / EvidenceAgent / adapters SQLite C1
-> EvidenceSet matérialisé
-> evidence_id uniquement
-> AG-03 / CAP-G02 / TRANSFORM
-> ProductionCandidate(CANDIDATE)
```

La source test-only transformée possède la référence stable
`synthetic:scn-04.tva-note`. CAP-G02 reçoit cette `target_ref`, conserve la
lineage de target, borne `evidence_refs_used` aux références demandées et ne mute
pas la fixture source. Le witness réel observe l'ordre
`AG-02:CAP-E01 -> AG-03:CAP-G02`. Les trois assertions hard `workflow`,
`evidence-generation-order` et `transformation-lineage` passent.

## 5. SCN-05 — exercice, revue et gate humaine

Le selector conserve WF-5 comme base et WF-10 comme overlay ; aucun WorkflowKind
composite n'est ajouté. Le plan compilé impose :

```text
AG-03 / CAP-G01
-> AG-04 / CAP-V01
-> RUNTIME / CAP-O05 (gate après revue)
```

AG-03 matérialise une candidate exercice avec `context`, `questions` et
`correction-link`. AG-04 revoit exactement la référence/version de cette
candidate, appelle son port une fois et produit une revue `COMPLETED`,
`ACCEPTABLE`, sans correction requise.

GateEngine reconstruit et valide la requête et la décision externe : acteur USER
autorisé, même gate/run/step/correlation, référence de décision valide. Le chemin
approuvé observe exactement `review-complete -> gate-request ->
external-APPROVED -> continuation`, avec `matrix_gate_satisfied = true` et une
seule continuation. La régression rejetée retourne `REJECTED`,
`matrix_gate_satisfied = false` et zéro continuation. Les quatre assertions hard
`workflow`, `generation-review-order`, `gate-before-downstream` et
`review-performed` passent.

## 6. Minimisation et rubrics

Les snapshots contiennent uniquement codes de workflow/capability, ordres,
codes de sections, booléens, faits de lineage et statuts de gate. Les textes de
fixture, contenus générés et extraits Evidence restent en mémoire transitoire ;
les tests vérifient leur absence octet pour octet des artefacts JSON et Markdown.
Aucun texte de revue ni payload technique n'est projeté.

Les rubrics pédagogiques B restent déclaratives. D ne fournit ni scoring plan ni
scorer et ne prétend mesurer ni clarté, ni adaptation de niveau, ni fidélité, ni
difficulté. Cette calibration reste réservée à 12.16.

## 7. Cycle de vie SQLite

Le gate SCN-04 authentifie le seed Phase 3, crée une runtime fraîche hors Git,
applique la migration C0, ouvre les adapters C1 en lecture seule, ferme toutes
les connexions, supprime DB/WAL/SHM puis réauthentifie le seed. La comparaison
avant/après prouve que le seed est inchangé. Le chemin privé du seed n'est pas
inscrit dans les sources.

## 8. Fitness et validations

Les fitness tests verrouillent : backend sans dépendance vers `tests/e2e`,
agents sans SQLite/repository ni dépendance inter-agent, décision de gate jamais
produite par un agent, doubles limités aux tests, absence de provider/réseau et
réutilisation exacte de CAP-E01/G01/G02/V01/O05 et WF-2/4/5/10. Les tests E2E
vérifient en plus l'exclusion du contenu brut des reports.

Le gate réel SCN-04 isolé a exécuté `1 passed`, `0 skipped` en 59,08 s. La
relance combinée C0+C1+C2+D sur le seed réel a exécuté `20 passed`, `0 skipped`
en 333,87 s. La régression ciblée owners/topologies/harness a exécuté
`730 passed`. La globale finale hors variable locale de seed a exécuté
`3818 passed` et `20 skipped` conditionnels en 183,83 s ; ces gates SQLite sont
rejoués sans skip dans la relance réelle ci-dessus.

Python 3.12.13, Ruff global, mypy sur les `638` sources backend et les `30`
sources du harness, ainsi que compileall backend/harness/tests passent. Les
dépendances projet restent `[]` et `git diff --check` est propre.

## 9. Handoff E

D livre des candidats en mémoire, sans promotion en Resource et sans vérité de
qualité. Le handoff suivant peut démarrer à 12.15-E uniquement après fermeture
et push de ce lot. Aucun travail E n'est inclus ici.
