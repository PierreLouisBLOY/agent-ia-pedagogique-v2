# ADR-P12-061 — Découplage de l'admissibilité retrieval

## Statut

Accepté — Phase 12.16-F2A.

## Contexte

Le benchmark F1 a démontré que le résultat combiné était structurellement
identique au canal STRUCTURED. `structured_search()` ne retourne que les
libellés canoniques exacts, tandis que le coordinateur construisait l'ensemble
des identités admissibles uniquement à partir de ce canal. Tout hit LEXICAL,
RELATIONAL ou futur SEMANTIC absent du top STRUCTURED était donc rejeté, même
lorsqu'il référençait un objet canonique courant.

Ce couplage confondait deux responsabilités : produire un signal de recherche
exact et prouver l'admissibilité canonique d'un candidat.

## Options étudiées

### A — Admission post-retrieval explicite

Un port technique indépendant vérifie chaque occurrence après retrieval et
avant fusion. Il reçoit le candidat et la requête inchangée. Cette option rend
la preuve testable et réutilisable par tous les canaux.

### B — Auto-admission du candidat

Rejetée. Les mappings `provenance`, `authority` et `metadata` sont nécessaires
mais ne suffisent pas : un candidat ne doit pas acquérir d'autorité en déclarant
lui-même des marqueurs attendus.

### C — Élargissement de STRUCTURED

Rejetée. Un univers STRUCTURED plus large resterait borné par `channel_limit` ;
une identité légitime pourrait donc être exclue arbitrairement avant même
l'admission.

## Décision

L'option A est retenue avec `EvidenceAdmissibilityPort.is_admissible()`.
`RetrievalCoordinator` utilise le port explicite fourni ou celui implémenté par
le search adapter. Pour les anciens fakes sans port, le fallback reste fermé et
conserve l'admission historique par présence STRUCTURED.

L'adaptateur SQLite prouve indépendamment :

- la liaison `search_chunk` → `object_registry` ;
- le statut `CURRENT` du chunk et son checksum exact ;
- le statut `CANONICAL` lorsqu'il s'agit d'une notion ;
- la source-policy strictement canonique ;
- le filtre actif ;
- le scope de niveau lorsqu'un contexte de niveau actif existe ;
- le scope de topic lorsqu'il correspond au libellé de notion canonique ;
- l'exigence d'autorité éventuelle, limitée à la base du registre canonique.

Une notion sans contexte de niveau actif dans le seed est canonique et globale.
Dès que des contextes actifs existent, le niveau demandé doit correspondre à
l'identifiant, au code ou au libellé canonique normalisé.

## Contrat de fusion

`FusedRetrievalCandidate` exige au moins une occurrence déjà admise par le
coordinateur, mais n'exige plus une occurrence STRUCTURED. La cohérence de
`RetrievalIdentity`, des occurrences et des rangs reste obligatoire.

L'ordre de représentant reste déterministe :

```text
STRUCTURED > LEXICAL > RELATIONAL > SEMANTIC
```

Si une occurrence STRUCTURED existe, elle doit rester représentante. Cette
préférence n'est jamais une condition d'admission.

## Invariants

```text
UNTRUSTED_CONTENT != AUTHORITY
SEMANTIC_SCORE != AUTHORITY
LEXICAL_SCORE != AUTHORITY
RETRIEVAL_RANK != AUTHORITY
```

Les scores alimentent uniquement le classement RRF existant. `rrf_k`,
`channel_limit`, `final_limit`, l'identité canonique et l'ordre des canaux ne
sont pas modifiés. Scope, filtres, source-policy et required-authority sont
transmis au gate sans élargissement.

Tout futur canal SEMANTIC devra présenter une référence canonique vérifiable et
passer exactement le même port. Un score sémantique, même élevé, ne constitue
jamais une preuve d'admissibilité.

## Conséquences

Les hits LEXICAL canoniques courants peuvent désormais améliorer le résultat
combiné sans exact label STRUCTURED. Les rows stale, non canoniques, hors scope
ou demandées sous une politique élargie restent rejetées. Aucun nouveau moteur
de recherche, provider, embedding ou stockage vectoriel n'est introduit.
