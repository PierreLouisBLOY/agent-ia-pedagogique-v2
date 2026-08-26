# Phase 12.9 — Livrable complet canonique final

## 1. Objet et périmètre

Ce document clôt la Phase 12.9 consacrée à AG-04 Reviewer/Critic. Il consolide
l'audit d'ouverture, les lots B à G, l'audit pré-merge H1, l'intégration
fast-forward H2 et l'audit post-merge H3. La phase livre une frontière de review
provider-neutral, sa coordination, CAP-V01, CAP-V02, le hardening sécurité et les
preuves de compatibilité workflow.

La Phase 12.9 ne livre ni moteur de routing, ni gate engine, ni sandbox, ni
promotion. Aucun travail de Phase 12.10 n'est inclus.

## 2. Baseline d'entrée Phase 12.9

La baseline canonique d'entrée est le commit `79731a745b58b80d30e06e292c1eec9353ca46b3`
(`docs: close phase 12.8 canonical delivery`). La branche de travail était
`phase12/12-9-reviewer-critic` et son merge-base avec `main` est resté cette
baseline jusqu'à l'intégration H2.

Le périmètre intégré entre cette baseline et la tête validée comporte exactement
42 fichiers changés, 10 648 insertions et aucune suppression cumulative.

## 3. Audit A — ouverture

L'audit d'ouverture a confirmé la topologie canonique à quatre agents, AG-04
comme Reviewer/Critic, et l'existence exclusive de `CAP-V01 semantic_review` et
`CAP-V02 assess_findings` pour cet agent. Il a aussi confirmé l'absence de
`CAP-V03` et le refus d'accès direct d'AG-04 aux familles CAP-E, CAP-G, CAP-A et
CAP-O.

Les contrats C-09/C-10/C-11 existaient déjà et devaient être réutilisés sans
duplication. Les frontières validées en Phases 6 et 11 ont été conservées.

## 4. Lot B — ReviewPort

Le lot B a créé l'unique `ReviewPort`, protocole synchrone et provider-neutral à
un seul appel `review(request)`. `ReviewPortRequest` reçoit exclusivement des
données déjà résolues par l'appelant. `ReviewPortResult` reste un résultat
technique non canonique avec les statuts fermés `SUCCEEDED`, `PARTIAL`,
`REFUSED` et `FAILED`.

Aucun provider concret, SDK, dispatcher, retry, accès réseau ou accès aux
données n'a été ajouté.

## 5. Lot C — ReviewCoordinator

Le lot C a créé l'unique `ReviewCoordinator`. Il transforme C-09 et une cible
résolue caller-supplied en snapshot immuable, lie la capability à une opération
fermée, exécute exactement un appel `ReviewPort.review()` et revalide la lineage
du résultat technique.

Le coordinator ne crée ni `Finding`, ni C-10, ni C-11. Il ne route aucun agent,
ne consulte aucun registry et ne réessaie pas localement.

## 6. Lot D — ReviewerAgent / CAP-V01

Le lot D a créé l'unique `ReviewerAgent` et la matérialisation CAP-V01 :
C-09 + cible résolue -> appel technique unique -> findings -> C-10. Le
`review_id` et la metadata C-10 sont fournis par l'appelant et ne peuvent pas
être imposés par le provider.

Le mapping de statut est fermé : `SUCCEEDED -> COMPLETED` et
`PARTIAL -> INCOMPLETE`. `REFUSED` et `FAILED` ne sont pas matérialisables.

## 7. Lot E — CAP-V02

Le lot E a ajouté `assess_findings()` sur C-10 et produit l'unique
`ReviewAssessmentSignal`. Le snapshot des findings est profondément immuable ;
CAP-V02 ne peut ajouter, retirer ou requalifier un finding.

Les IDs assessed, blocking et correction sont recalculés à partir de C-10. Tout
blocking doit rester visible et être inclus dans les corrections. Un handoff
optionnel et non canonique est émis exclusivement vers AG-01.

## 8. Lot F — sécurité

Le lot F a créé l'unique `ReviewSecurityGuard`, une policy fermée, la validation
des locators et les fingerprints de lineage. La cible, les evidence et les
sorties provider sont traitées comme données non fiables.

Les tentatives d'escalade, d'exfiltration, d'action tool/file et d'autorité
injectée sont refusées ou bornées selon la policy. Les URLs et instructions
présentes dans le contenu ne sont jamais suivies ni exécutées.

## 9. Lot G — workflows et fitness

Le lot G a ajouté uniquement des preuves de test et de documentation. Il couvre
WF-3, WF-5, WF-6, WF-7, WF-10 et WF-11, ainsi que la fermeture architecturale
AG-04. Aucun fichier de production n'a été ajouté ou modifié par G.

Les scénarios prouvent les variantes acceptable, réserves, correction,
blocking et partial, la correction/re-review versionnée, les arrêts no-progress
et cycle, le gate humain explicite et la promotion séparée.

## 10. Contrats canoniques réutilisés

Les contrats `ReviewRequest` (C-09), `ReviewResult` (C-10), `Finding` et
`CorrectionRequest` (C-11) restent chacun définis une seule fois sous
`backend/agent_runtime/contracts/review/`. Aucun type HTTP, ORM ou SDK fournisseur
n'entre dans ces contrats.

C-11 est seulement réutilisé dans les preuves de workflow sous l'autorité
appropriée ; AG-04 ne le construit jamais.

## 11. Architecture AG-04 finale

La production réelle de Phase 12.9 réside dans
`backend/agent_runtime/agents/review/`. Elle contient un port, un coordinator,
un agent, les modèles techniques et canoniques de review/assessment, ainsi que
la sécurité dédiée.

L'audit AST exécuté sur `main` confirme une instance de chacune des surfaces
`ReviewPort`, `ReviewCoordinator`, `ReviewerAgent`, `ReviewSecurityGuard`,
`ReviewAssessmentSignal` et `CorrectionHandoffSignal`. Les dépendances
`review -> runtime/orchestration` et `runtime/orchestration -> review` sont nulles.

## 12. CAP-V01

CAP-V01 cible une version exacte portée par C-09 et un `ResolvedReviewTarget`
caller-supplied lié au même `ObjectVersionRef`. La requête technique conserve
les dimensions, critères, evidence autorisées, inputs résolus, contrat de sortie
et budget.

Les findings suivent un schéma fermé à dix champs, avec dimensions et sévérités
canoniques, IDs uniques, evidence bornées et locators revalidés contre la cible
exacte. C-10 exprime une opinion de review ; il ne vaut ni validation ni
promotion.

## 13. CAP-V02

CAP-V02 consomme exactement C-10, son `review_ref` caller-supplied et le même
snapshot cible. Le provider reçoit un snapshot immuable et ne retourne aucun
nouveau finding technique.

Les agrégats `assessed_finding_ids`, `blocking_finding_ids` et
`correction_finding_ids` doivent être identiques aux valeurs recalculées. Un
résultat partiel reste `INCOMPLETE` et ne peut masquer aucun finding blocking ou
de correction.

## 14. ReviewPort

`ReviewPort` constitue la seule frontière outbound de review. Son contrat est
provider-neutral, synchrone et limité à un appel par exécution coordonnée. Les
mappings entrants et sortants sont gelés et contrôlés par un vocabulaire
agent-safe.

Le fake `RecordingReviewPort` est exclusivement test-only ; aucun adaptateur
provider réel n'est livré dans cette phase.

## 15. ReviewCoordinator

`prepare()` réalise le binding déterministe et produit `PreparedReviewCall`.
`execute()` revalide ce prepared, effectue l'appel unique et borne le step,
l'opération ainsi que `evidence_refs_used`.

Une erreur de port est propagée sans retry, fallback, repair ou traduction
provider. Le résultat reste technique jusqu'à sa matérialisation explicite par
le reviewer.

## 16. ReviewerAgent

L'API publique de `ReviewerAgent` est limitée à `semantic_review`,
`build_review_result` et `assess_findings`. Elle ne contient aucune opération de
search, correction, validation, promotion, persistance ou gate.

L'agent n'appelle ni AG-03 ni CAP-G03, ne possède pas `PromotionPolicy`, ne
construit pas `GateDecision`, `ValidationResult` ou C-11 et ne route aucun
workflow.

## 17. Findings et C-10

Chaque `Finding` conserve son ID, sa dimension, sa sévérité, sa description, son
locator, sa rationale, son indicateur de correction, ses evidence, sa confiance
et son action suggérée. Les mappings hors schéma, valeurs enum invalides,
evidence hors scope et locators invalides échouent de manière fermée.

`overall_assessment` est une synthèse de review uniquement. `ACCEPTABLE` exige
l'absence de correction et de blocking, mais n'entraîne aucune promotion.

## 18. Assessment signal et handoff AG-01

`ReviewAssessmentSignal` est informatif et non canonique.
`promotion_blocked_by_review` vaut exactement la présence de findings blocking ;
ce champ n'est pas une décision de promotion.

`CorrectionHandoffSignal` est absent sans correction. Lorsqu'il existe, il cible
uniquement AG-01 et transporte les IDs, evidence, recommandations et diagnostics
sûrs nécessaires à une décision ultérieure. Il n'autorise ni mutation ni appel
direct d'AG-03.

## 19. Sécurité et locators

Les locators fermés sont `text_span` et `json_path`. `whole_target` n'est admis
que par opt-in explicite de policy et dans une représentation non ambiguë.
Indices, quotes, clés et indices JSON sont résolus contre la cible fournie ; les
wildcards, expressions, CSS, XPath et regex exécutables sont interdits.

Tout locator hors cible ou obsolète échoue avant matérialisation. Les erreurs,
warnings et limitations utilisent des codes et messages bornés sans recopier le
contenu cible ou evidence.

## 20. Evidence lineage

La lineage lie exactement la référence et le fingerprint de cible, le run, le
step, la correlation, la capability, l'opération, `review_id`, `review_ref`, les
fingerprints de findings et les evidence.

Les invariants sont : evidence finding incluse dans les evidence utilisées par
C-10, elles-mêmes incluses dans C-09 ; assessment evidence incluse dans C-09 ;
evidence du handoff égale à l'union déterministe des findings concernés. Les
objets C-10 ou V02 forgés et l'authority-smuggling récursif sont refusés.

## 21. Workflows WF-3/5/6/7/10/11

- WF-3 conserve une review indépendante.
- WF-5 relie AG-03 à AG-04 sur la version exacte, avec validation Application
  optionnelle et séparée.
- WF-6 conserve la chaîne AG-02 -> AG-03 -> A01 -> AG-04 et ses evidence.
- WF-7 passe par AG-01, C-11 et de nouvelles versions de Plan pour toute
  correction/re-review bornée.
- WF-10 ajoute une gate humaine explicite en overlay après review.
- WF-11 garde validation, gate et promotion hors AG-04.

Aucun moteur workflow, dispatcher ou runner spécifique à AG-04 n'a été créé.

## 22. Frontières d'autorité

AG-04 peut reviewer une version exacte, évaluer les findings, émettre des
signaux non canoniques et transmettre un handoff à AG-01. Il ne recherche pas,
ne corrige pas directement, ne valide pas canoniquement, ne promeut pas, ne
persiste pas, ne route pas et n'ouvre pas de gate.

`overall_assessment` reste review-only ; `promotion_blocked_by_review` reste
signal-only. La validation canonique, la décision humaine et la promotion
restent sous leurs autorités Application/Runtime dédiées.

## 23. Rationalisation

L'audit cumulatif a comparé ports, coordinators, agent, materializers,
assessment, sécurité, locators, safe-data, validateurs, scanners d'autorité,
enums d'erreur, helpers de test, documentation et ADR. Les ressemblances avec
les surfaces evidence et génération ne partagent pas simultanément la même
sémantique, les mêmes invariants et la même frontière d'autorité.

Aucune refactorisation cosmétique n'est justifiée pendant la clôture.

`RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED`

## 24. Validations post-merge

Toutes les validations suivantes ont été exécutées sur `main` à
`1f7a313f24d480290a8622c912b0d13e4267bb4e` avant création de ce document :

- Python 3.12.13 ;
- `compileall backend` : PASS ;
- pipeline G : 15 tests PASS ;
- compatibilité workflows G : 6 tests PASS ;
- fitness de clôture G : 10 tests PASS ;
- régression AG-04 : 276 tests PASS ;
- suite globale : 2 356 tests PASS ;
- Ruff global : PASS ;
- mypy : PASS, 526 fichiers source ;
- `git diff --check` : PASS ;
- `git diff --check 79731a745...HEAD` : PASS ;
- `project.dependencies` : `[]` ;
- worktree avant livrable : propre.

Le premier appel au nom générique `python` n'a lancé aucune validation car ce
nom n'était pas présent dans le PATH de la session Windows. Les commandes ont
été relancées avec l'interpréteur canonique du dépôt
`.venv/Scripts/python.exe`, Python 3.12.13 ; seuls ces résultats exécutés sont
comptabilisés ci-dessus.

## 25. Lignée Git, intégration et handoff 12.10

La lignée Phase 12.9 est linéaire :

1. `29e2aa64b80c35a9f2ab7fe9c997a38e883a06d1` — frontière ReviewPort ;
2. `cdbbd35f8af67c8eb2ed5060fba036b8abf5e209` — coordination ;
3. `0a09b4642bc7585c6ee1fc06ea788469a7381002` — CAP-V01 ;
4. `0ffedb1d5b9c59e71f04aeebb915c5a0e8db065d` — CAP-V02 ;
5. `33b2d0004dbe1a4b38cb6d7fbd20b40ad2c01dde` — sécurité et lineage ;
6. `1f7a313f24d480290a8622c912b0d13e4267bb4e` — workflows et fitness.

H2 a intégré cette lignée dans `main` en mode `FAST_FORWARD_ONLY`, sans merge
commit. Après H2, `main`, `origin/main`, la branche source locale et sa référence
distante pointaient toutes sur `1f7a313f...`, avec un ahead/behind de `0 / 0`.
Le commit H3 ajoute uniquement le présent document ; la branche source reste à
`1f7a313f...` et n'est ni déplacée ni supprimée.

`NEXT_PHASE = Phase 12.10 — tool/use-case routing, gates, sandbox`

La Phase 12.10 devra consommer concrètement les routes, matérialiser le routing
tool/use-case, introduire le gate engine / `GateDecision` et le sandbox sans
déplacer l'autorité canonique. Ce travail est explicitement différé et n'a pas
commencé en H3.

## 26. Production réelle, preuves test-only et responsabilités différées

### Production réelle

La production réelle comprend les composants sous
`backend/agent_runtime/agents/review/` : contrats techniques du port, modèles de
coordination, coordinator, reviewer, matérialisation, assessment et sécurité.
Elle réutilise les contrats canoniques existants sans les dupliquer.

### Preuves test-only

Les fakes provider-neutral, doubles de validation Application, décision AG-01,
gate humaine et promotion probe sont confinés à `tests/support/`. Les scénarios
G et fitness sont confinés à `tests/integration/` et `tests/architecture/`.
Aucun import pytest, unittest, mock ou fake n'est présent dans le package review
de production.

### Responsabilités différées

Le dispatch réel `StepSpec -> agent/use case`, la résolution et persistance des
artefacts, la policy de replan, le gate engine, la décision humaine, la
promotion et le sandbox appartiennent aux phases et autorités ultérieures. Ils
ne sont pas simulés comme production dans ce lot.

## 27. Audit I/O, dépendances et secrets

Les scans finaux sur le périmètre intégré n'ont trouvé aucun secret candidat,
artefact runtime, base, log ou export. Dans le package review, ils n'ont trouvé
aucun import Application/Domain/infrastructure, provider SDK, HTTP/network,
SQL/ORM, vector store ou subprocess ; aucun appel filesystem métier,
tool execution, `eval` ou `exec` ; aucune surface de log brut cible/evidence ;
aucune fuite de helper test-only.

Le projet conserve zéro dépendance runtime directe. Les erreurs restent
agent-safe et aucune donnée cible/evidence brute n'est ajoutée aux logs ou aux
messages d'erreur.

## 28. Décision de clôture

L'audit post-merge, les validations complètes, l'audit d'autorité, l'audit
sécurité, l'audit I/O/secrets et la rationalisation sont PASS. L'intégration est
identique à la branche validée et aucune branche n'a été supprimée.

```text
PHASE 12.9-H3 — PASS / CLOSED
PHASE 12.9 — CLOSED / MERGED
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
MERGE_MODE = FAST_FORWARD_ONLY
NEXT_PHASE = 12.10
```
