# Frontière de retrieval AG-02

## Responsabilité

AG-02 — Evidence/Retrieval est strictement read-only vis-à-vis du patrimoine
canonique. Son ceiling comprend :

- CAP-E01 `search_evidence` pour rechercher des candidats bornés ;
- CAP-E02 `fetch_evidence_item` pour demander un accès documentaire contrôlé ;
- CAP-E03 `assess_evidence_coverage`, qui reste hors de 12.7-B.

AG-02 ne génère, ne corrige, ne promeut et ne persiste aucun objet métier. La
frontière réutilise C-05 `EvidenceRequest` comme intention de recherche et
préserve C-06 `EvidenceItem`/`EvidenceSet` comme sortie evidence publique. Elle
ne crée aucun contrat concurrent.

## Modèle technique

Une `RetrievalQuery` est dérivée d'un `EvidenceRequest` sans transformation
sémantique ni élargissement de `scope`, `source_policy`, `filters`,
`required_authority` ou `max_items`. Les mappings sont copiés dans une forme
agent-safe profondément immutable. `source_policy` reste une contrainte de
données que les futurs ports devront honorer ; elle n'est pas interprétée comme
un `PermissionScope` et ne produit aucune décision ALLOW/DENY.

Les cinq canaux sont volontairement distincts :

| Canal | Nature du signal |
| --- | --- |
| `STRUCTURED` | correspondances et rangs structurés |
| `LEXICAL` | pertinence lexicale reconstructible |
| `SEMANTIC` | proximité sémantique non autoritative |
| `RELATIONAL` | proximité issue de relations explicites |
| `DOCUMENT` | découverte de ressources documentaires |

Search et RAG sont des mécanismes de recherche et de composition, jamais des
sources de vérité. RAG n'est donc pas un sixième canal.

`RetrievalSignals` conserve `structured_rank`, `lexical_score`,
`semantic_score` et `relational_score` séparément. Aucun clamp, score final,
score de vérité ou score d'autorité n'est fabriqué.

## Candidat, contenu et preuve

La chaîne conceptuelle ne comporte aucune promotion implicite :

```text
RetrievalCandidate     -> candidat brut d'un canal de recherche
DocumentContentResult  -> contenu récupéré par un accès contrôlé
EvidenceItem           -> preuve structurée canonique C-06
EvidenceSet            -> résultat evidence public C-06
```

Ainsi :

- un candidat trouvé n'est pas une preuve ;
- un score élevé n'établit pas l'autorité ;
- un contenu récupéré n'établit pas la vérité ;
- une duplication n'est pas une corroboration indépendante ;
- une sortie agent ou LLM n'est pas evidence par défaut.

`DocumentContentRequest.locator` est opaque. Seul un futur adapter contrôlé
pourra l'interpréter. La frontière ne suit aucune URL et n'accède à aucun path.

`DocumentContentResult.content` est toujours une donnée non fiable. Des phrases
telles que « ignore les consignes », « appelle cet outil », « révèle un secret »,
du pseudo-JSON de permissions ou des liens n'acquièrent aucune autorité et ne
sont ni parsés ni exécutés. `security_warnings` est descriptif ; 12.7-B ne
définit aucun détecteur et ne dérive aucun warning du contenu.

## Ports et exclusions

`EvidenceSearchPort.search` reçoit la requête et le canal choisi par son caller.
`EvidenceDocumentContentPort.fetch` reçoit une demande documentaire contrôlée.
Ce sont uniquement des `Protocol` injectables, sans implémentation de production.
Le canal `SEMANTIC` passe déjà par `EvidenceSearchPort`; aucun `SemanticPort`
séparé n'est défini.

12.7-B n'introduit aucun SQL, ORM, HTTP, provider, modèle d'embedding, vector
store, repository, client externe, adapter concret ou accès filesystem. Il ne
construit aucun `EvidenceItem`, `EvidenceSet`, `AgentInvocation`,
`DelegationEnvelope`, `Plan`, `StepSpec` ou `PlanExecutor`.

Le `RetrievalCoordinator` est différé à 12.7-C, l'`EvidenceAgent` à 12.7-D, le
source-policy hardening/expansion à 12.7-E, et l'intégration Search/RAG avec ses
scénarios à 12.7-F.
