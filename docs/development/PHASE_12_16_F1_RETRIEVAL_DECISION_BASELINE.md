# Phase 12.16-F1 — Baseline de décision retrieval

## Parent et portée

Cette baseline part de la clôture E au commit
`c231dbb16a6366ad28743aad75d76a2b26383235` sur
`phase12/12-16-provider-model-calibration`. F1 est strictement un lot de tests,
benchmark et documentation : `BACKEND_DELTA = 0`, `ADR_REQUIRED = NO`.

## Seed et corpus

Le gate utilise la base canonique réelle fournie par la policy
`PEDAGOGICAL_CANONICAL_SEED_PATH`, authentifiée à 105 553 920 octets et au
SHA-256 `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`,
avec intégrité et quick check `ok` et zéro violation FK.

Le corpus versionné `12.16-f1-v1` contient 60 cas, dix par classe A–F et au
moins douze par niveau. Il couvre des notions de management, système
d'information, données, marketing, économie et comptabilité/gestion. Les
références attendues sont fixées avant exécution et protégées par l'empreinte
`f9ebd4330c1f4b5d06021b8a29d4d12db4cfaff05b535eec0ff86da4d842f238`.

## Contrôles et métriques

Chaque requête D/E/F est appariée à un contrôle A. Les dix contrôles A passent
à Recall@5 = 100 % dans STRUCTURED, LEXICAL et le résultat combiné. La baseline
de recherche et les données attendues sont donc saines.

Les métriques sont Recall@1/3/5, MRR@5 et ZeroHitRate, calculées globalement,
par classe, par niveau et par canal. Une référence attendue quelconque suffit
en cas d'attendus multiples. Les formules et valeurs complètes se trouvent dans
`PHASE_12_16_F1_RETRIEVAL_BASELINE_REPORT.md` et dans le JSON machine.

## Résultat et causes

Le Recall@5 global vaut 23,33 % en STRUCTURED, 50,00 % en LEXICAL et 23,33 %
pour la combinaison canonique actuelle. Sur les 30 cas D/E/F, la combinaison
actuelle en rate 30 : 25 `SEMANTIC_PARAPHRASE_GAP` et 5 `ALIAS_GAP` liés à
l'admission structurée exacte. Aucun cas n'est classé DATA, NORMALIZATION,
RELATIONAL ou EXPECTATION, et aucune typo n'est utilisée pour justifier
Semantic.

## Décision de matérialité

`MATERIAL_SEMANTIC_GAP = TRUE` car :

1. 25 misses indépendants sont classés `SEMANTIC_PARAPHRASE_GAP` ;
2. ils couvrent les quatre niveaux ;
3. leurs contrôles exacts passent ;
4. les références existent, sont indexées et lisibles ;
5. les formulations ne sont pas correctement résolues par un simple alias,
   une normalisation ou une réparation de donnée ;
6. elles représentent des questions ou descriptions mono-concept légitimes.

La proportion concernée est de 83,3333 % des cas D/E/F, largement au-dessus de
la zone de prudence de 10 % applicable à un corpus d'au moins 24 cas.

## Séparations maintenues

`SEMANTIC != RELATIONAL` : aucun gap relationnel ne contribue à la décision.
Les variantes simples de casse ou d'accents atteignent Recall@5 = 100 % en
LEXICAL ; Semantic n'est pas proposé comme correcteur orthographique. Les cinq
gaps d'alias restent une dette lexicale/structurée séparée et ne sont pas
comptés dans les 25 preuves sémantiques.

## Reproductibilité

Deux runtimes frais produisent des références ordonnées, métriques, causes et
décision identiques, avec rapport calculé octet-identique. Le seed est identique
avant/après et tous les fichiers runtime/WAL/SHM sont supprimés.

## Outcome et handoff

```text
PHASE 12.16-F1 — PASS / CLOSED
SEMANTIC_JUSTIFIED = TRUE
NEXT_GATE = 12.16-F2_READY
```

F1 n'ajoute ni provider, ni modèle d'embedding, ni vector store, ni appel
réseau. F2 devra repartir de cette preuve, réauditer indépendamment la décision
et seulement alors revalider les options officielles. Aucun travail F2 n'est
inclus dans ce lot.
