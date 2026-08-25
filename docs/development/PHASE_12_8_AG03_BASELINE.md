# Baseline Phase 12.8 — AG-03 génération et transformation

## Périmètre fermé B à G

La Phase 12.8 établit la frontière provider-neutral d'AG-03 pour les trois
capabilities canoniques :

| Capability | Opération | Entrée canonique | Sortie non canonique |
| --- | --- | --- | --- |
| `CAP-G01` | `GENERATE` | `ProductionRequest` C-07 | `ProductionCandidate` C-08 |
| `CAP-G02` | `TRANSFORM` | C-07 avec `target_ref` exact | C-08 avec cible dans le lineage |
| `CAP-G03` | `CORRECT` | `CorrectionRequest` C-11 et cible résolue | C-08 et `CorrectionResult` versionné |

La frontière `GenerationPort` ne connaît aucun fournisseur. Le caller prépare
les inputs résolus et l'output contract. Le `GenerationCoordinator` les capture
dans un snapshot immuable, construit la requête technique et revalide le
résultat. Chaque opération effectue exactement un appel au port : AG-03 ne
contient ni retry, fallback, boucle locale, recherche ou résolution d'artifact.

## Matérialisation et autorité

`GeneratorAgent` matérialise uniquement des `ProductionCandidate` dans l'état
`CANDIDATE`. Il ne valide, ne promeut, ne persiste et ne rend rien canonique. Les
identités de production, metadata de résultat et versions sont fournies par le
caller puis revalidées.

La correction conserve l'identité d'objet, exige une nouvelle version et couvre
exactement les findings de C-11 avec des ensembles addressed/unresolved
disjoints. Une seconde correction relève d'un nouveau plan et d'une nouvelle
C-11 ciblant la version précédente ; elle n'est jamais une boucle interne AG-03.

Les metadata d'exécution provider-supplied restent non autoritatives. Le contrôle
authority-free de D refuse le vocabulaire de validation, review, confiance,
promotion, gate ou permission au lieu de le filtrer silencieusement.

## Guard de sortie F

Avant toute matérialisation, le caller fournit une policy technique et des
attributions déclarées à `GenerationOutputGuard`. L'assessment déterministe est
recalculé par G01/G02/G03. Seules les dispositions `ALLOW` et
`ALLOW_WITH_WARNINGS` autorisent une sortie ; `REPAIR_REQUIRED`, `ABSTAIN` et
`REJECT` ne produisent aucun contrat.

Le grounding est structurel seulement : aucune claim `GROUNDED` ne peut citer
une evidence absente du résultat technique et un grounding obligatoire sans
evidence conduit à l'abstention. La présence d'une référence n'établit pas son
adéquation sémantique : `SOURCE_MATCH` reste différé aux mécanismes de review et
validation.

Le scanner analyse des patterns fermés FR/EN dans le contenu et les feuilles
structurées, sans conserver le texte, suivre une URL, lire un fichier ou appeler
un outil. Ses signaux sont des warnings non autoritatifs. Une
`GenerationRepairProposal` est descriptive uniquement : elle ne contient ni
prompt, provider, retry ni surface d'exécution.

Le contrôle authority-free des metadata et le scanner du contenu restent
séparés : le premier bloque une tentative de franchissement d'autorité dans les
metadata techniques, le second signale du contenu sans déclarer celui-ci sûr ou
malveillant.

## Compatibilité workflows 12.6

Les preuves G compilent et exécutent avec `WorkflowSelector`, `PlanCompiler`,
`DeterministicScheduler`, `PlanExecutor` et `OrchestrationCoordinator` :

| Workflow | Topologie démontrée |
| --- | --- |
| `WF-2` | AG-03 `CAP-G01` ou `CAP-G02`, puis `CAP-A01` seulement si demandé |
| `WF-4` | AG-02 `CAP-E01` → AG-03 `CAP-G01` |
| `WF-5` | AG-03 `CAP-G01` → AG-04 `CAP-V01`, avec validation optionnelle |
| `WF-6` | AG-02 `CAP-E01` → AG-03 `CAP-G01` → Application `CAP-A01` → AG-04 `CAP-V01` |
| `WF-7` | AG-03 `CAP-G03` → re-review optionnelle AG-04 `CAP-V01` |
| `WF-9` | cinq variantes AG-03 → JOIN runtime `CAP-O04` → sélection runtime opaque |

Pour `WF-9`, `max_parallel_steps=4` produit déterministement les cycles
`4 variantes → 1 variante → JOIN → sélection`. Les cinq pipelines AG-03 sont
appelés explicitement par le test et publient cinq candidats distincts dans une
association d'artifacts test-only. Le `RecordingStepRunner` reste opaque et ne
route aucune capability vers AG-03. Si une variante est bloquée par le guard,
elle n'est pas publiée ; la failure/replan policy production reste une
responsabilité ultérieure.

## Topologie et dispatch

`topology compatibility != production capability dispatch`

Un `StepSpec` AG-03 prouve l'intention, l'ownership, les dépendances et
l'ordonnancement. Il ne transporte pas automatiquement C-07/C-11, ne résout pas
les refs, n'injecte pas une guard policy, ne construit pas une
`AgentInvocation` et ne persiste pas de candidat. Aucun `GenerationStepRunner`,
`AgentCapabilityRouter`, `AG03Handler` ou `ArtifactStore` production n'est
introduit en G.

## Responsabilités différées

- provider, modèle, renderer de prompt et budget : Phase 12.16 ;
- AG-04 réel : Phase 12.9 ;
- routing, permissions runtime et gates : Phase 12.10 ;
- résilience, retry orchestré et replan : Phase 12.11 ;
- hardening global : Phase 12.12 ;
- observabilité : Phase 12.13 ;
- E2E production : Phase 12.15.

G n'ajoute aucun provider, réseau, SQL, vector store, filesystem métier,
persistance, validation, promotion ou dispatcher runtime.

## Rationalisation

Audit cumulatif : B définit l'unique frontière `GenerationPort` ; C l'unique
coordinator et les snapshots de préparation ; D l'agent et la matérialisation
C-08 ; E la correction versionnée ; F l'unique output guard ; G apporte seulement
les preuves cumulatives et d'intégration.

Il n'existe aucun modèle dupliqué, second coordinator, second port, second guard
ou scanner AG-03 concurrent. Les chemins G01/G02 partagent le même coordinator et
le même modèle de préparation ; G03 réutilise le même port tout en conservant ses
invariants C-11. Aucun workflow dispatcher caché n'est présent.

`NO_SAFE_CONSOLIDATION_REQUIRED`
