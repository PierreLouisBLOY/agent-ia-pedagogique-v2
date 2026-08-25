# Coordination hybride du retrieval AG-02

## Pipeline RQ-03 à RQ-09

`RetrievalCoordinator` transforme un `EvidenceRequest` C-05 en résultat
technique multi-canal, sans produire de preuve C-06. Le pipeline matérialise :

1. RQ-03/RQ-04 : filtres et admissibilité via `STRUCTURED` ;
2. RQ-05 : signal et ordre `LEXICAL` ;
3. RQ-06 : signal `SEMANTIC` optionnel ;
4. RQ-07 : fusion des rangs par identité ;
5. RQ-08 : déduplication exacte, isolée par version ;
6. RQ-09 : ranking technique et top-K final.

RQ-10 `DocumentContentAccess` et RQ-11 Evidence sont différés à 12.7-D.

## Narrowing de la requête

Le coordinator dérive d'abord une `RetrievalQuery` sans modifier
`search_goal`, `scope`, `source_policy`, `filters` ou `required_authority`.
Seule la borne est réduite :

```text
channel_max = min(policy.channel_limit, request.max_items ou channel_limit)
```

`max_items=0` retourne immédiatement un résultat `FULL` vide, sans appeler le
port. La limite finale vaut le minimum de `policy.final_limit` et de la borne du
caller lorsqu'elle existe. Aucun candidat synthétique ne complète le top-K.

## Ordre et admissibilité

L'ordre d'exécution ne dépend pas de l'ordre déclaré dans la policy :

1. `STRUCTURED` ;
2. `LEXICAL` ;
3. `RELATIONAL` si activé ;
4. `SEMANTIC` si activé.

`DOCUMENT` est interdit en 12.7-C.

Le résultat `STRUCTURED` forme l'allowlist absolue des identités admissibles.
Les signaux lexicaux, relationnels et sémantiques ne sont pas autoritatifs : une
occurrence absente de l'allowlist est rejetée, quel que soit son score. Si
`STRUCTURED` ne retourne rien, aucun autre canal ne peut repeupler le résultat.

## Identité, déduplication et versions

Avec `canonical_object_ref`, l'identité est l'objet canonique plus
`version_or_checksum`; source et locator n'interviennent pas. Sans référence
canonique, le fallback est l'égalité exacte de `source_ref`, `locator` et
version/checksum. Les références `TypedEntityRef` et `ObjectVersionRef` sont
normalisées depuis leurs champs publics afin d'éviter toute stringification
instable.

Seules les occurrences de même identité sont fusionnées, et aucune occurrence
n'est perdue. Deux versions/checksums restent séparées. Deux locators fallback
restent séparés. Similarité, alias supposé ou redirect non résolu n'autorisent
aucune fusion.

Le représentant suit l'ordre `STRUCTURED`, `LEXICAL`, `RELATIONAL`, `SEMANTIC`,
puis la position dans le résultat du canal et l'identifiant stable. Une
occurrence structurée est toujours requise.

## RRF et ranking

Le rang d'un canal est la position base 1 fournie par son résultat. Les scores
bruts restent dans les occurrences et ne sont jamais convertis, calibrés ou
additionnés.

La fusion technique configurable est :

```text
fusion_score = somme(Decimal(1) / Decimal(rrf_k + channel_rank))
```

La baseline non pondérée utilise `rrf_k=60`. Les tie-breaks sont, dans l'ordre :

1. score RRF décroissant ;
2. rang structuré croissant ;
3. rang lexical croissant ;
4. rang relationnel croissant ;
5. rang sémantique croissant ;
6. clé d'identité déterministe croissante.

Les rangs finaux `technical_rank` sont contigus. `rrf_k=60`,
`channel_limit=20` et `final_limit=10` sont des defaults techniques
remplaçables, pas des règles métier. Top-K, pondérations, seuils, calibration et
reranking restent ouverts par la Phase 9 ; aucun reranker n'est introduit ici.

## FULL, DEGRADED et échecs requis

La policy baseline active `STRUCTURED`, `LEXICAL`, `RELATIONAL`, `SEMANTIC` et
exige `STRUCTURED` plus `LEXICAL`.

- `FULL` signifie que tous les canaux activés ont répondu ;
- `DEGRADED` signifie qu'au moins un canal optionnel activé est indisponible ;
- l'indisponibilité d'un canal requis lève
  `REQUIRED_CHANNEL_UNAVAILABLE`, sans faux résultat partiel.

Les limitations utilisent des codes stables tels que
`CHANNEL_UNAVAILABLE:SEMANTIC` ou
`INADMISSIBLE_CANDIDATES_DROPPED:RELATIONAL`. Aucune exception externe brute,
aucun retry, backoff ou fallback vers un autre provider n'est effectué.

## Hors périmètre

12.7-C ne récupère aucun contenu documentaire, ne construit aucun
`EvidenceItem`/`EvidenceSet`, ne fait aucun appel SQL/HTTP/vector store et
n'introduit aucun adapter concret. `EvidenceAgent` et l'accès documentaire sont
prévus en 12.7-D, l'expansion et la sécurité en 12.7-E, puis l'intégration
Search/RAG et ses scénarios en 12.7-F.
