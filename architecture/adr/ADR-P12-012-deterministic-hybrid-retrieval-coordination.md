# ADR P12-012 - Coordination déterministe du retrieval hybride

## Statut

Accepté.

## Contexte

La frontière 12.7-B expose des requêtes, candidats, résultats mono-canal et un
`EvidenceSearchPort` provider-neutral. Elle ne définit volontairement ni
l'ordre des canaux ni la règle d'admissibilité, de déduplication ou de ranking
multi-canal requise par la Phase 9.4.

Les scores structurés, lexicaux, relationnels et sémantiques ne partagent pas
une échelle canonique. Les additionner directement fabriquerait une mesure sans
autorité. De même, une forte similarité ne doit jamais contourner les filtres
durs, fusionner des versions incompatibles ou transformer un candidat en preuve.

## Décision

`RetrievalCoordinator` exécute une coordination pure, bornée et déterministe
derrière `EvidenceSearchPort`. L'ordre d'appel est fermé : `STRUCTURED`,
`LEXICAL`, puis `RELATIONAL` et `SEMANTIC` lorsqu'ils sont activés. `DOCUMENT`
n'est jamais admis par la policy 12.7-C et reste différé au pipeline d'accès
contrôlé ultérieur.

La réponse `STRUCTURED` construit l'allowlist d'identités admissibles avant
toute compétition de pertinence. Un candidat lexical, relationnel ou sémantique
dont l'identité n'appartient pas à cette allowlist est écarté. Un résultat
structuré vide impose donc un résultat final vide.

Une identité utilise l'objet canonique et la version/checksum lorsque
`canonical_object_ref` existe ; source et locator ne participent alors pas à la
clé. Sans objet canonique, le fallback exact utilise source, locator et
version/checksum. Les références typées sont normalisées par leurs champs
publics, jamais par `repr`. Des versions différentes restent des identités
distinctes et aucune similarité ne les fusionne.

Les occurrences d'une identité admissible sont toutes conservées. Leur rang de
canal est leur position base 1 dans le résultat du port ; leurs scores bruts ne
sont ni recalibrés ni additionnés. La fusion utilise Reciprocal Rank Fusion :

```text
somme(1 / (rrf_k + rang_canal))
```

Le calcul est exclusivement en `Decimal`, sans pondération. Le tri final suit
le score RRF décroissant, puis les rangs `STRUCTURED`, `LEXICAL`, `RELATIONAL`,
`SEMANTIC` croissants, puis la clé d'identité déterministe. Les rangs techniques
finaux sont contigus.

La baseline active les quatre canaux de recherche, exige `STRUCTURED` et
`LEXICAL`, et fixe `channel_limit=20`, `final_limit=10`, `rrf_k=60`. Ces trois
nombres sont des defaults techniques remplaçables. La Phase 9 laisse top-K,
paramètre RRF, pondérations, seuils et calibration ouverts ; ils ne sont pas des
invariants métier.

Une indisponibilité de `STRUCTURED` ou `LEXICAL` échoue explicitement sans
résultat partiel. L'indisponibilité d'un canal optionnel produit le mode
`DEGRADED` et une limitation stable. Le coordinator ne retry pas et ne cherche
aucun provider alternatif.

## Conséquences

- l'admissibilité structurée précède toujours la pertinence ;
- le mode dégradé canonique conserve `STRUCTURED + LEXICAL` ;
- la déduplication est explicable et isolée par version ;
- aucun reranker, query expansion ou recalcul sémantique n'est introduit ;
- aucun contenu documentaire n'est récupéré ;
- aucun `EvidenceItem` ou `EvidenceSet` n'est construit ;
- l'assemblage par `EvidenceAgent` et l'accès documentaire restent différés à
  12.7-D ;
- l'expansion et le durcissement sécurité restent différés à 12.7-E ;
- l'intégration Search/RAG reste différée à 12.7-F.
