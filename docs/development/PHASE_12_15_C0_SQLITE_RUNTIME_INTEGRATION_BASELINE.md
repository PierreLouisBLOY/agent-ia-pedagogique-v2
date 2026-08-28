# Phase 12.15-C0 — Baseline d'intégration SQLite runtime

## 1. Erratum et frontière

Le seed Phase 3 au SHA-256
`38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`
représente légitimement le schéma antérieur à la migration Phase 7. C0 applique
donc le modèle suivant :

```text
seed canonique immuable -> copie runtime -> migrations Phase 7 -> application
```

Le hash runtime ne remplace pas l'identité canonique du seed. C0 ne lance aucun
scénario pédagogique complet et s'arrête avant C1.

## 2. Recovery Phase 7

La branche historique n'était pas publiée dans l'origin V2. Elle a été retrouvée
dans le dépôt historique `agent-ia-pedagogique` puis récupérée sans merge.

| Objet | Commit historique | Action C0 |
| --- | --- | --- |
| migration 001 | `98d8464232f3cea21f7ac911c268b1ad8e675e0d` | copie octet-identique sous `database/migrations` |
| implémentation | `deb751d5b103023d13c8713d9aa663e0e44476e8` | adaptation aux packages outbound V2 |
| contract kits | `a57b95f06d47677728da5a6f9ecc0b403b118c70` | adaptation aux gates C0 |

Le blob Git de la migration est
`38b369d73be55f8c90dca62544a64b1277190c14` et son SHA-256 est
`5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102`.

## 3. Seed et runtime

Le chemin réel du seed reste local et n'est pas documenté. La configuration
utilise `PEDAGOGICAL_CANONICAL_SEED_PATH` et
`PEDAGOGICAL_RUNTIME_DATABASE_PATH`.

Le bootstrap :

1. authentifie taille, hash, 98 tables, 20 index explicites, 7 triggers et 2 vues ;
2. exécute integrity, quick et foreign-key checks en lecture seule ;
3. refuse une destination identique ou préexistante ;
4. copie le seed ;
5. inspecte le ledger version/checksum ;
6. applique `001` et le ledger dans une transaction `BEGIN IMMEDIATE` ;
7. vérifie les 15 documents, la contrainte SHA et les clés étrangères ;
8. checkpoint WAL, recalcule le hash runtime et publie la readiness.

Le ledger et les marqueurs `operation_ref` sont des tables techniques
`_runtime_*`. L'inventaire métier reste 98/20/7/2.

## 4. Mapping Phase 7 vers V2

| Contrat | Owner/adaptateur |
| --- | --- |
| OP-01 | KnowledgeStore |
| OP-02 | DocumentStore |
| OP-03 | ResourceStore |
| OP-04 | ContextStore |
| OP-05 | WorkStore avec expected version |
| OP-06 | ValidationStore append/read |
| OP-07 | QualityStore append/read |
| OP-08 | LifecycleDecisionStore append/read |
| OP-09 | AuditTraceabilityStore append/read |
| OP-10 | SQLiteUnitOfWork, commit unique, rollback, operation marker |
| OP-11 | BusinessSearchAdapter FTS5, hits non autoritatifs |
| OP-12 | ReadModelAdapter dérivé |
| OP-13 | DocumentContentAccessAdapter logique |

Les records SQLite sont mappés en dictionnaires ou dataclasses dans les
adapters. Aucune `sqlite3.Row`, table ou connexion n'entre dans Domain,
Application ou les agents.

## 5. Préparation C1

La requête stable `absence` résout réellement un hit FTS5 `notion:absence`.
Chaque hit transporte une `passage_ref` vers le texte inline de `search_chunk` ;
OP-13 restitue ce fragment avec des refs logiques uniquement. Les références de
documents historiques ne contiennent pas d'extrait inline, seulement des
locators de provenance ; ce gap est explicite et n'empêche pas le chemin C1
SearchHit -> passage inline.

## 6. Sécurité et exploitation

- aucune dépendance runtime ajoutée ;
- aucun provider, modèle, embedding ou réseau ;
- aucune base, WAL ou SHM suivi par Git ;
- seed inchangé avant/après les gates ;
- runtime local configurable hors Git ;
- retry aveugle interdit, réconciliation par `operation_ref` disponible.

La décision d'architecture est
[ADR-P12-056](../../architecture/adr/ADR-P12-056-sqlite-runtime-composition-integration.md).
