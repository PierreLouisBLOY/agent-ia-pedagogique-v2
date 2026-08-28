# ADR-P12-057 — Intégration des ports Evidence AG-02 à SQLite

## Statut

Accepté pour la Phase 12.15-C1.

## Contexte

ADR-P12-056 ferme le seed/runtime SQLite et les opérations OP-11/OP-13, mais
ne fixe pas la traduction durable des canaux et identités SQLite vers les
protocols existants d'AG-02. Cette traduction doit permettre la fusion sans
attribuer au texte une autorité pédagogique ni simuler un provider sémantique.

## Décision

1. La composition injecte deux adaptateurs outbound dans les ports AG-02 sans
   modifier `EvidenceAgent`, `RetrievalCoordinator` ni leurs protocols.
2. STRUCTURED admet une notion seulement si `notion.identity_status` est
   `CANONICAL`, si son label correspond exactement à la requête, si elle est
   inscrite comme `NOTION` dans `object_registry` et si son chunk est `CURRENT`.
   Cette admissibilité ne dérive ni du contenu du chunk ni du rank FTS.
3. LEXICAL délègue à OP-11/FTS5. Son rank SQLite est converti par
   `Decimal(str(rank))`; il reste un signal technique et non un score
   d'autorité ou de qualité pédagogique.
4. RELATIONAL retourne `RELATIONAL_NOT_CONFIGURED_C1` et SEMANTIC retourne
   `SEMANTIC_PROVIDER_NOT_CONFIGURED_C1`. Aucun embedding ou score factice
   n'est créé. Avec les deux canaux requis disponibles, AG-02 publie
   `DEGRADED`.
5. Pour un même passage, STRUCTURED et LEXICAL publient la même identité :
   `source_ref` et `canonical_object_ref` portent l'object id, `locator` porte
   la `search_chunk` ref, et `version_or_checksum` porte `chunk_hash`.
6. L'autorité publiée se limite à une base de registre canonique avec
   `absolute=false`; la présence en base n'implique pas `official=true`.
7. OP-13 résout le locator logique et restitue le texte comme
   `UNTRUSTED_CONTENT`. Une clock injectée fournit l'`Instant`; aucun chemin,
   URL, handle provider ou row SQLite ne traverse la boundary.
8. Le harness test-only appelle les owners AG-02 et ne contient aucun SQL. Il
   projette uniquement codes, booléens, compteurs et statuts fermés.

## Conséquences

SCN-02 peut exécuter le chemin réel OP-11 vers OP-13 avec une identité fusionnée
et une provenance validée par AG-02. L'absence de RELATIONAL et SEMANTIC reste
visible sans transformer le cas en échec. Une évolution du mapping d'identité,
de l'admissibilité structurée ou de l'autorité exige la révision de cet ADR.
Les providers et leur calibration restent hors C1.
