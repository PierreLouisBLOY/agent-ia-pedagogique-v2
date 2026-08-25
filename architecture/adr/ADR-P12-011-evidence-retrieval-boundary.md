# ADR P12-011 - Frontière provider-neutral de retrieval AG-02

## Statut

Accepté.

## Contexte

AG-02 porte la responsabilité Evidence/Retrieval en lecture seule. Les contrats
canoniques C-05 `EvidenceRequest` et C-06 `EvidenceItem`/`EvidenceSet` existent
déjà, mais ils ne définissent pas la frontière technique entre une intention de
recherche et les mécanismes structurés, lexicaux, sémantiques, relationnels ou
documentaires qui pourront la satisfaire.

La Phase 9 impose une architecture hybride, filtrée et evidence-first derrière
des ports et adapters. L'admissibilité structurée précède la pertinence ; le
signal sémantique n'est pas autoritatif. L'accès au contenu documentaire doit
rester contrôlé. Aucun modèle ou agent ne peut accéder directement à une base,
un store ou au filesystem métier.

Sans frontière dédiée, une implémentation future risquerait de confondre un
candidat trouvé avec une preuve, de transformer un score en autorité ou de
dupliquer les contrats publics de Phase 12.3.

## Décision

`backend/agent_runtime/agents/evidence/` définit exclusivement les modèles
techniques immutables et les ports injectables de retrieval.

`RetrievalChannel` ferme le vocabulaire à `STRUCTURED`, `LEXICAL`, `SEMANTIC`,
`RELATIONAL` et `DOCUMENT`. RAG décrit la composition de ces mécanismes et n'est
donc pas un canal de vérité.

`RetrievalQuery.from_evidence_request` dérive une requête technique du contrat
C-05 sans élargir son objectif, son scope, sa source policy, ses filtres, son
autorité requise ou sa borne. `source_policy` reste une donnée structurée : cette
frontière ne l'interprète ni en permission ni en décision ALLOW/DENY.

`RetrievalSignals` conserve séparément rang structuré et scores lexicaux,
sémantiques ou relationnels. Aucun score final, de vérité ou d'autorité n'est
calculé.

`RetrievalCandidate` représente uniquement un candidat brut d'un canal.
`RetrievalSearchResult` borne un résultat mono-canal et accepte explicitement un
résultat vide. Aucun candidat n'est automatiquement converti en `EvidenceItem`
ou assemblé en `EvidenceSet` C-06.

`DocumentContentRequest` transporte un locator opaque et la source policy
héritée. `DocumentContentResult` transporte le contenu récupéré comme donnée non
fiable, même si celui-ci ressemble à une instruction, une permission, une URL
ou un appel d'outil. La frontière ne détecte, ne parse et n'exécute rien dans ce
contenu. Les éventuels `security_warnings` descriptifs proviennent d'un futur
adapter.

`EvidenceSearchPort` et `EvidenceDocumentContentPort` sont des `Protocol`
runtime-checkable sans implémentation de production. Le caller choisit le canal ;
le port ne choisit pas le workflow. Aucun `SemanticPort` séparé n'est créé tant
qu'un besoin technique réel n'est pas établi.

Cette décision ne duplique pas la Phase 9 : elle en matérialise la frontière
provider-neutral dans le runtime agentique et laisse les implémentations dans de
futurs adapters. Aucun SQL, ORM, HTTP, SDK fournisseur, vector store, accès
filesystem, repository concret ou dépendance runtime n'est introduit.

## Conséquences

- candidat trouvé, contenu récupéré et preuve canonique restent trois états
  distincts ;
- score élevé ne signifie ni autorité ni vérité ;
- duplication ne signifie pas corroboration indépendante ;
- sortie d'agent ou de modèle n'est pas une preuve par défaut ;
- AG-02 ne gagne aucune autorité d'écriture, de correction ou de promotion ;
- le `RetrievalCoordinator` hybride est différé à 12.7-C ;
- l'`EvidenceAgent` est différé à 12.7-D ;
- le durcissement et l'expansion contrôlée de source policy sont différés à
  12.7-E ;
- l'intégration Search/RAG et les scénarios sont différés à 12.7-F.
