# Phase 12.16-F2A — Remédiation de l'admissibilité retrieval

## Résultat

Le couplage entre admissibilité canonique et exact match STRUCTURED est supprimé.
Le corpus F1 inchangé, rejoué sur le seed réel, montre que COMBINED n'est plus
structurellement identique à STRUCTURED.

```text
ADMISSIBILITY_DECOUPLED = TRUE
SEMANTIC_JUSTIFIED = TRUE
NEXT_GATE = 12.16-F2B_READY
```

Aucun provider, embedding, vector store, table vectorielle, semantic adapter ou
CAP-T04 n'est implémenté.

## Preuve du défaut initial

Les six constats du préflight sont confirmés :

1. `structured_search()` utilisait l'égalité insensible à la casse du libellé canonique ;
2. le canal STRUCTURED SQLite appelait directement cette méthode ;
3. le coordinateur construisait l'univers admissible depuis STRUCTURED seul ;
4. les identités LEXICAL/SEMANTIC absentes de cet univers étaient dropped ;
5. `FusedRetrievalCandidate` exigeait une occurrence et un représentant STRUCTURED ;
6. ces règles expliquaient l'égalité des métriques COMBINED et STRUCTURED en F1.

## Design retenu

L'option A, admission post-retrieval explicite, est retenue. Le nouveau
`EvidenceAdmissibilityPort` vérifie chaque occurrence avant fusion. L'option B
est rejetée car les métadonnées déclarées par un candidat ne valent pas preuve.
L'option C est rejetée car `channel_limit` pourrait toujours retrancher une
identité légitime de l'univers STRUCTURED élargi.

Le port est automatiquement réutilisé lorsque le search adapter l'implémente.
Les fakes historiques dépourvus de ce port conservent un fallback fermé sur la
présence STRUCTURED ; aucune ancienne frontière n'est élargie implicitement.

## Critères SQLite

Avant admission, SQLite vérifie la liaison au registre, le chunk `CURRENT`, le
checksum, le statut canonique des notions, la fraîcheur, la provenance et la
base d'autorité. La requête doit conserver exactement `kinds=(canonical,)` et
`active=True`. Les contraintes non reconnues échouent fermées.

Pour le scope `level`, une notion sans contexte actif est canonique globale —
c'est le cas du seed F1, dont les tables de contexte sont vides. Si des contextes
de niveau actifs existent, le niveau demandé doit correspondre. Les tests
synthétiques prouvent le rejet d'un mauvais niveau.

Le scope optionnel `topic`, utilisé par SCN-04, est vérifié contre le libellé de
notion canonique normalisé ; il n'est jamais ignoré ni dérivé du score lexical.

## Fusion et représentant

RRF, `rrf_k=60`, `channel_limit=20`, `final_limit=10` et l'ordre de tie-break
restent inchangés. Une occurrence admise suffit. Le représentant est choisi dans
l'ordre STRUCTURED, LEXICAL, RELATIONAL, SEMANTIC ; STRUCTURED reste obligatoire
comme représentant lorsqu'il est présent, mais plus comme preuve d'admission.

Les scores et rangs restent non autoritatifs. Scope, filters, source-policy et
required-authority sont transmis au port sans transformation ni élargissement.

## Seed et corpus

- corpus : `12.16-f1-v1`, 60 cas inchangés ;
- corpus SHA-256 : `f9ebd4330c1f4b5d06021b8a29d4d12db4cfaff05b535eec0ff86da4d842f238` ;
- seed : 105 553 920 octets ;
- seed SHA-256 : `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` ;
- integrity/quick : `ok` ; violations FK : `0`.

## Métriques globales avant/après

| Canal | Recall@1 F1 | Recall@1 F2A | Recall@5 F1 | Recall@5 F2A | MRR@5 F1 | MRR@5 F2A | ZeroHit F1 | ZeroHit F2A |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| STRUCTURED | 23,33 % | 23,33 % | 23,33 % | 23,33 % | 0,233333 | 0,233333 | 76,67 % | 76,67 % |
| LEXICAL | 43,33 % | 43,33 % | 50,00 % | 50,00 % | 0,458889 | 0,458889 | 43,33 % | 43,33 % |
| COMBINED | 23,33 % | 46,67 % | 23,33 % | 50,00 % | 0,233333 | 0,478333 | 76,67 % | 43,33 % |

COMBINED récupère 16 cas lexical-only à Recall@5 : cinq B, six C et cinq D.
STRUCTURED et LEXICAL sont inchangés ; le delta provient exclusivement du
découplage d'admissibilité.

## Delta par classe — COMBINED Recall@5

| Classe | F1 | F2A | Delta |
|---|---:|---:|---:|
| A exact label | 100 % | 100 % | 0 point |
| B lexical variant | 0 % | 50 % | +50 points |
| C normalized surface | 40 % | 100 % | +60 points |
| D synonym/business | 0 % | 50 % | +50 points |
| E pedagogical paraphrase | 0 % | 0 % | 0 point |
| F concept description | 0 % | 0 % | 0 point |

## Delta par niveau — COMBINED Recall@5

| Niveau | F1 | F2A | Delta |
|---|---:|---:|---:|
| Première STMG | 22,22 % | 44,44 % | +22,22 points |
| Terminale STMG | 22,22 % | 44,44 % | +22,22 points |
| BTS CG 1 | 33,33 % | 50,00 % | +16,67 points |
| BTS CG 2 | 16,67 % | 66,67 % | +50,00 points |

## Misses résiduels et décision Semantic

Les cinq anciens `ALIAS_GAP` sont récupérés. Les 25 misses résiduels D/E/F sont
tous `SEMANTIC_PARAPHRASE_GAP`, soit 83,3333 % des 30 cas D/E/F. Ils couvrent
les quatre niveaux, leurs contrôles exacts passent à 100 %, les références
existent et les formulations sont légitimes, mono-concept et non relationnelles.

La décision Semantic est donc recalculée, pas héritée : les six conditions de
matérialité restent satisfaites après suppression complète du biais
d'admissibilité.

Le corpus réel ne produit aucun candidat SQL stale ou non canonique à dropper :
ces lignes sont éliminées avant construction des candidats. Le nombre de cas
F1 attendus perdus par le gate est donc `0`. Les tests négatifs injectent
explicitement stale, noncanonical, wrong-scope, filtre inactif et source-policy
élargie ; chacun est rejeté.

## Sécurité et reproductibilité

Les tests prouvent l'admission lexical-only canonique, le rejet inadmissible,
la préférence STRUCTURED, la stabilité des identités/rangs, la propagation
inchangée des contraintes et le gate commun d'un futur candidat semantic-only.
Les fixtures SQLite rejettent stale, noncanonical, wrong-scope et politiques
élargies. Deux runtimes frais ont produit des rapports byte-identiques et laissé
le seed inchangé.

## Références et validations

- branche : `phase12/12-16-provider-model-calibration` ;
- parent du lot : `a5877b2c8bc3fe1eed960bee98a27fc6ca44b1a1` ;
- `main` et `origin/main` inchangés : `7ae02ee109bcc6399ec0f71616da6aef07abda81` ;
- relation avant commit : `main...branch = 0/5` ;
- régressions retrieval/AG-02/12.7/12.12 : `409 passed` ;
- SCN-02 réel : `1 passed` ; SCN-04 réel : `1 passed` ;
- suite canonique réelle, deux runtimes : `1 passed` ;
- benchmark F1 réel, deux runtimes : `1 passed`, rapports byte-identiques ;
- suite globale réelle : `4046 passed`, aucun skip ;
- Ruff : PASS ; mypy backend : 653 fichiers, PASS ;
- mypy evaluation harness : 30 fichiers, PASS ; compileall : PASS ;
- `git diff --check` : PASS.

ADR : `ADR-P12-061-retrieval-admissibility-decoupling.md`.
Commit prévu : `fix: decouple retrieval admissibility from exact match`.
