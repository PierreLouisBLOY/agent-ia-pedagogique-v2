# Phase 12.8 — Livrable complet canonique final AG-03

## 1. Objet et périmètre

La Phase 12.8 ferme la frontière AG-03 de génération, transformation et
correction provider-neutral. Elle couvre les capabilities `CAP-G01`, `CAP-G02`
et `CAP-G03`, la préparation déterministe, l'appel technique borné, la
matérialisation non canonique, la correction versionnée, le guard de sortie et
les preuves de compatibilité avec les topologies 12.6.

La phase ne contient aucune intégration provider, recherche d'evidence,
validation métier, review AG-04 réelle, promotion, persistance ou connexion
automatique entre un `StepSpec` et AG-03.

## 2. Baseline d'entrée

La baseline d'entrée de la Phase 12.8 est le commit :

```text
a395f1331ed8773e2c41c47129e761f330bcecfb
test: execute independent multi-branch retrieval
```

Cette baseline ferme la Phase 12.7 et laisse `backend/agent_runtime/agents/`
avec la frontière evidence existante, sans héritage implicite de V1.

## 3. Lots B à G

| Lot | Résultat canonique |
| --- | --- |
| B | Frontière technique `GenerationPort`, opérations et résultats provider-neutral |
| C | Coordination déterministe, snapshots de préparation et one-call/no-retry |
| C correctif | Lineage exact du contexte pédagogique |
| D | `GeneratorAgent` et matérialisation C-08 pour G01/G02 |
| D correctif | Refus du metadata authority-smuggling |
| E | Correction CAP-G03 bornée et versionnée |
| E correctifs | Lineage de préparation correction puis G01/G02 lié aux inputs caller |
| F | Grounding structurel, structured-output guard et signaux de sécurité |
| G | Preuves cumulatives, pipelines réels avec fakes et compatibilité workflows |

H1 a audité la branche avant merge. H2 l'a intégrée dans `main` par
fast-forward strict. H3 a réexécuté l'audit et les validations sur `main`.

## 4. Architecture AG-03

AG-03 est l'unique owner des trois capabilities de classe
`GENERATE_TRANSFORM` :

```text
AG-03 -> CAP-G01 / CAP-G02 / CAP-G03
```

La matrice interdit à AG-03 les appels directs CAP-E, CAP-V, CAP-A et CAP-O.
Le package génération n'importe ni runtime ni orchestration, et la dépendance
inverse n'existe pas davantage.

## 5. CAP-G01 — génération

`CAP-G01` reçoit un `ProductionRequest` C-07 sans cible, prépare une opération
`GENERATE`, appelle une fois le port et peut matérialiser un
`ProductionCandidate` C-08 si le résultat et le guard l'autorisent.

Le brief, le contexte pédagogique, les contraintes, les evidence refs, les
sections attendues, les inputs résolus et l'output contract sont liés au
snapshot exact. Le candidat reste toujours `CANDIDATE`.

## 6. CAP-G02 — transformation

`CAP-G02` exige un `target_ref` C-07 exact et prépare une opération `TRANSFORM`.
La cible est conservée dans la requête technique et le lineage du candidat. La
production source n'est ni chargée par AG-03, ni mutée. La nouvelle
`production_id` est fournie par le caller.

## 7. CAP-G03 — correction

`CAP-G03` reçoit une C-11 et un `ResolvedCorrectionTarget` déjà résolu dont la
référence doit correspondre exactement. Il prépare une opération `CORRECT` avec
le mandat fermé C-11 : review, findings, changements permis/interdits,
contraintes de préservation et delta attendu.

Le résultat technique doit répartir exactement les findings entre
`addressed_findings` et `unresolved_findings`, ensembles uniques et disjoints,
avec un `change_summary` non vide.

## 8. GenerationPort

`GenerationPort` est l'unique Protocol outbound de la phase. Il expose un seul
appel `generate(request=GenerationPortRequest)`. Aucun provider concret, SDK,
HTTP, SQL, vector store, filesystem métier, retry ou fallback n'est présent.

Le port est partagé par G01, G02 et G03. Les tests utilisent
`RecordingGenerationPort`, un double explicite provider-neutral qui enregistre
les appels et retourne ou lève uniquement des résultats configurés.

## 9. Coordinator

`GenerationCoordinator` est l'unique coordinateur. Il prépare puis revalide les
snapshots avant tout appel outbound, et revalide le `GenerationPortResult` après
l'appel : source step, opération et evidence utilisée doivent rester dans le
périmètre préparé.

Il n'effectue aucune traduction d'erreur provider, aucune boucle, aucun retry et
aucune matérialisation de contrat agent.

## 10. Matérialisation du candidat

`GeneratorAgent.build_candidate()` exige une
`ProductionCandidateBuildRequest` complète : C-07, Prepared exact, résultat
technique exact, assessment du guard, metadata résultat AG-03 et
`production_id` caller-supplied.

Seuls les statuts techniques matérialisables et les dispositions `ALLOW` ou
`ALLOW_WITH_WARNINGS` produisent C-08. Le contrat ne peut représenter ni
validation, ni canonicalisation, ni promotion.

## 11. Correction versionnée

La correction matérialise conjointement une nouvelle `ProductionCandidate` et
un `CorrectionResult`. La référence parent est la cible C-11, l'identité d'objet
est conservée et la version nouvelle doit être différente.

Une répétition WF-7 n'est pas une boucle locale : elle crée une nouvelle C-11
ciblant la version précédente et un nouveau `Plan` versionné.

## 12. Output guard

`GenerationOutputGuard` est pur, stateless et déterministe. Il reçoit le
Prepared, le résultat technique, une policy caller-supplied et des attributions
de claims déclaratives. Son assessment est recomputé avant toute
matérialisation.

Ordre de priorité :

```text
REJECT > ABSTAIN > REPAIR_REQUIRED > ALLOW_WITH_WARNINGS > ALLOW
```

`REPAIR_REQUIRED`, `ABSTAIN` et `REJECT` ne produisent aucun candidat ni
`CorrectionResult`. Une `GenerationRepairProposal` reste descriptive et ne
possède aucune surface d'exécution.

## 13. Sécurité et anti-smuggling

Le contrôle authority-free des metadata refuse les clés réservées à la
validation, review, confiance, promotion, gate et permission, y compris dans les
structures imbriquées. Il ne filtre pas silencieusement les données.

Le scanner du guard analyse des patterns fermés FR/EN dans le contenu et les
feuilles structurées. Il signale instructions, élévation de privilège,
exfiltration, actions tool/fichier, URL et revendications d'autorité. Il ne
conserve aucun texte brut, ne suit aucune URL et n'exécute aucune action.

Ces deux contrôles restent distincts : l'un bloque l'authority-smuggling des
metadata techniques, l'autre produit des warnings de contenu non autoritatifs.

## 14. Lineage

Les snapshots lient exactement :

- capability et opération ;
- C-07 ou C-11 canonique ;
- source step et correlation ;
- contexte pédagogique et contraintes ;
- cible de transformation ou version de correction ;
- evidence refs autorisées et réellement utilisées ;
- resolved inputs et output contract caller-supplied ;
- assessment du guard au Prepared et résultat exacts.

Un Prepared, résultat ou assessment forgé échoue fail-closed avant sortie.

## 15. Compatibilité workflows WF-2/4/5/6/7/9

Les tests G prouvent les topologies suivantes avec les composants
d'orchestration 12.6 :

| Workflow | Topologie prouvée |
| --- | --- |
| WF-2 | AG-03 G01 ou G02 ; CAP-A01 seulement si demandé |
| WF-4 | AG-02 CAP-E01 -> AG-03 CAP-G01 |
| WF-5 | AG-03 -> validation optionnelle CAP-A01 -> AG-04 fake |
| WF-6 | AG-02 -> AG-03 -> Application CAP-A01 -> AG-04 fake |
| WF-7 | AG-03 CAP-G03 -> re-review AG-04 fake optionnelle |
| WF-9 | cinq variantes G01 -> JOIN runtime CAP-O04 -> sélection runtime |

Pour WF-9, la limite de parallélisme produit `4 + 1`, puis JOIN, puis sélection.
Cinq pipelines AG-03 explicites produisent cinq candidats distincts. Une
variante bloquée par le guard n'est pas publiée.

Cette section est une preuve test-only de compatibilité topologique, pas un
dispatcher production.

## 16. Frontières d'autorité

AG-03 ne recherche pas, ne review pas, ne valide pas, ne promeut pas et ne
persiste pas. Une evidence ref attribuée prouve uniquement son appartenance au
corpus technique déclaré ; elle ne prouve pas un `SOURCE_MATCH` sémantique.

Le guard n'est pas AG-04. Les signaux ne déclarent aucun contenu safe, trusted,
validated ou canonical. L'autorité métier reste dans les use cases Application,
la review et les gates ultérieurs.

## 17. Responsabilités différées

- AG-04 réel : Phase 12.9 ;
- routing, permissions runtime et gates : Phase 12.10 ;
- résilience, retry orchestré et replan : Phase 12.11 ;
- hardening global : Phase 12.12 ;
- observabilité : Phase 12.13 ;
- E2E production : Phase 12.15 ;
- provider, modèle, prompt renderer et budget : Phase 12.16.

Aucun `GenerationStepRunner`, `AgentCapabilityRouter`, `AG03Handler` ou
`ArtifactStore` production n'est introduit par 12.8.

## 18. Rationalisation

L'audit cumulatif et post-merge confirme : un seul port, coordinator, guard,
scanner de sécurité, `ProductionCandidate` et `CorrectionResult`. G01/G02
partagent le même modèle de préparation ; G03 conserve un modèle distinct requis
par C-11 tout en réutilisant le même port et coordinator.

Les helpers G restent sous `tests/`. Aucune responsabilité test-only n'a glissé
dans le code production et aucun vocabulaire concurrent de capability,
opération ou port n'a été créé.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```

## 19. Validations

Validations H3 réexécutées sur `main` :

| Contrôle | Résultat |
| --- | --- |
| Python | `3.12.13` |
| `compileall backend` | PASS |
| Pytest | `2080 passed in 34.44s` |
| Ruff | PASS |
| mypy | PASS, 515 fichiers source |
| `git diff --check` | PASS |
| diff-check baseline vers HEAD | PASS |
| dépendances runtime projet | `[]` |

Les audits ciblés ont aussi produit 102 tests architecture génération, 28 tests
pipeline/workflow et 32 contrôles registre/accès PASS.

## 20. Lignée exacte des dix commits

```text
2153782 feat: establish AG-03 generation boundary
16a3895 feat: coordinate AG-03 generation requests deterministically
2a286a5 fix: preserve AG-03 pedagogical context lineage
087e4fc feat: materialize AG-03 production candidates
bd73cf3 fix: block AG-03 authority metadata smuggling
ea89676 feat: add bounded AG-03 versioned correction
11b1928 fix: bind AG-03 correction preparation lineage
5d4fe45 fix: bind AG-03 generation preparation lineage
1aa190f feat: harden AG-03 generation outputs
2e2936a test: close phase 12.8 AG-03 fitness
```

Aucun commit de merge n'existe dans cette lignée.

## 21. Mode d'intégration

La branche `phase12/12-8-generator-transformer` a été intégrée dans `main` par :

```text
FAST_FORWARD_ONLY
```

Aucun squash, rebase, force-push ou commit de merge n'a été utilisé.

## 22. SHA final fonctionnel

Le SHA fonctionnel audité et intégré avant le commit documentaire H3 est :

```text
2e2936abd3eb93cb51d8eec2ea5988bf18a8f680
```

Le commit documentaire H3 qui porte ce livrable devient le SHA de clôture de la
Phase 12.8 sans modifier le contenu fonctionnel validé.

## 23. État post-merge

Avant le commit documentaire H3, `HEAD`, `main`, `origin/main`, la branche source
locale et sa branche distante pointent tous sur `2e2936a`. Le merge-base est ce
même SHA, l'écart est `0/0`, le worktree est propre et le diff intégré correspond
exactement à 42 fichiers, 11 299 insertions et 1 suppression.

La branche source reste conservée sur le SHA fonctionnel `2e2936a` après le
commit documentaire, conformément à H3.

## 24. Décision de clôture

L'audit post-merge, la rationalisation et toutes les validations sont PASS.
Aucun finding bloquant n'est ouvert, aucune consolidation sûre ne reste et le
seul ajout H3 est ce livrable canonique.

Décision : Phase 12.8 éligible à `CLOSED / MERGED` après commit et push de ce
document unique.

## 25. Handoff vers la Phase 12.9

La Phase 12.9 pourra traiter AG-04 réel à partir d'un `ProductionCandidate`
explicitement non canonique et des frontières de review prévues. Elle ne doit
pas réinterpréter les signaux du guard comme une validation ni introduire
implicitement provider, dispatch runtime, promotion ou persistance.

Ce document constitue un handoff uniquement. Aucun code ou travail Phase 12.9
n'est commencé dans H3.
