# Phase 12.16-F1 — Rapport du benchmark retrieval réel

## Résultat

`PHASE 12.16-F1 — PASS / CLOSED` pour le benchmark et la décision. Le besoin
Semantic est matériel ; aucun canal Semantic, embedding, vector store, appel
provider ou changement backend n'est implémenté dans F1.

```text
SEMANTIC_JUSTIFIED = TRUE
NEXT_GATE = 12.16-F2_READY
```

## Périmètre mesuré

Le benchmark traverse uniquement le chemin existant : AG-02
`EvidenceAgent.search_evidence`, `RetrievalCoordinator`, `EvidenceSearchPort`,
`SQLiteEvidenceSearchAdapter`, OP-11 `BusinessSearchAdapter`, puis les canaux
STRUCTURED et LEXICAL. `COMBINED` désigne le résultat fusionné actuel d'AG-02 ;
aucun algorithme de fusion de benchmark n'a été ajouté.

La base réelle est fournie exclusivement par
`PEDAGOGICAL_CANONICAL_SEED_PATH`. Son identité authentifiée est :

- taille : `105553920` octets ;
- SHA-256 : `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` ;
- `integrity_check = ok`, `quick_check = ok`, violations FK = `0`.

## Corpus figé

Le corpus `12.16-f1-v1` contient 60 requêtes. Son empreinte déterministe est
`f9ebd4330c1f4b5d06021b8a29d4d12db4cfaff05b535eec0ff86da4d842f238`.
Les références attendues sont des tuples littéraux de références `notion:*` ;
le test unitaire recalcule l'empreinte du catalogue et interdit toute vérité
dérivée d'un hit observé.

| Niveau | Cas |
|---|---:|
| Première STMG | 18 |
| Terminale STMG | 18 |
| BTS CG 1 | 12 |
| BTS CG 2 | 12 |

Chacune des classes A à F contient exactement 10 cas. Chaque cas D, E ou F est
relié à son contrôle A de la même famille et de la même référence attendue.

## Formules

Pour un cas et un canal, le rang est celui de la première référence retournée
appartenant à `expected_refs`. `Recall@k` est la proportion de cas dont ce rang
est inférieur ou égal à `k`. `MRR@5` est la moyenne de `1/rang` pour les rangs
de 1 à 5, zéro sinon. `ZeroHitRate` est la proportion de réponses sans aucun
candidat. Ces métriques sont des données d'évaluation technique, jamais une
autorité métier ni une validation de domaine.

## Résultats globaux

| Canal | Recall@1 | Recall@3 | Recall@5 | MRR@5 | ZeroHitRate |
|---|---:|---:|---:|---:|---:|
| STRUCTURED | 23,33 % | 23,33 % | 23,33 % | 0,233333 | 76,67 % |
| LEXICAL | 43,33 % | 48,33 % | 50,00 % | 0,458889 | 43,33 % |
| COMBINED actuel | 23,33 % | 23,33 % | 23,33 % | 0,233333 | 76,67 % |

## Résultats par classe — Recall@5

| Classe | STRUCTURED | LEXICAL | COMBINED |
|---|---:|---:|---:|
| A — exact label | 100 % | 100 % | 100 % |
| B — lexical variant | 0 % | 50 % | 0 % |
| C — normalized surface | 40 % | 100 % | 40 % |
| D — synonym/business | 0 % | 50 % | 0 % |
| E — pedagogical paraphrase | 0 % | 0 % | 0 % |
| F — concept description | 0 % | 0 % | 0 % |

Le gate exact est sain : 10 contrôles sur 10 retrouvent leur référence à
Recall@5 dans STRUCTURED et COMBINED. Aucun défaut de donnée ou de baseline ne
bloque donc la décision.

Les 46 misses COMBINED à Recall@5 sont exhaustivement délimités par le catalogue :

- les dix cas B (`RQ-*-B`) ;
- six cas C : `RQ-SYSTEME-INFORMATION-C`, `RQ-DONNEES-PERSONNELLES-C`,
  `RQ-DEMARCHE-MARKETING-C`, `RQ-MARCHE-C`, `RQ-COUT-COMPLET-C` et
  `RQ-METHODE-ABC-C` ;
- les trente cas D/E/F (`RQ-*-D`, `RQ-*-E`, `RQ-*-F`), détaillés avec leurs
  causes dans le rapport JSON.

## Résultats par niveau — Recall@5

| Niveau | STRUCTURED | LEXICAL | COMBINED |
|---|---:|---:|---:|
| Première STMG | 22,22 % | 44,44 % | 22,22 % |
| Terminale STMG | 22,22 % | 44,44 % | 22,22 % |
| BTS CG 1 | 33,33 % | 50,00 % | 33,33 % |
| BTS CG 2 | 16,67 % | 66,67 % | 16,67 % |

## Analyse des misses D/E/F

Les 30 cas D/E/F ratent tous à Recall@5 dans COMBINED. Le rapport JSON associe
chaque case id à son contrôle, son niveau, son rang lexical et sa cause.

| Cause | Nombre | Lecture |
|---|---:|---|
| `SEMANTIC_PARAPHRASE_GAP` | 25 | faible ou nul recouvrement lexical malgré une intention mono-concept légitime |
| `ALIAS_GAP` | 5 | alias présent dans le chunk lexical mais non admis par le contrôle STRUCTURED exact |
| `DATA_GAP` | 0 | les dix références existent et leurs contrôles passent |
| `NORMALIZATION_GAP` | 0 | la classe C atteint 100 % en LEXICAL |
| `LEXICAL_LIMITATION` | 0 | aucun miss D/E/F classé comme simple problème de rang lexical |
| `RELATIONAL_GAP` | 0 | aucun cas multi-hop ou de voisinage n'est inclus |
| `EXPECTATION_ERROR` | 0 | aucune référence attendue corrigée après observation |

Les 25 gaps sémantiques couvrent Première STMG, Terminale STMG, BTS CG 1 et
BTS CG 2, soit `83,3333 %` des 30 cas D/E/F. Les contrôles exacts réussissent,
les références sont présentes et lisibles, et ces paraphrases ne sont ni des
typos ni des requêtes relationnelles. Les six conditions de matérialité sont
donc satisfaites.

## Reproductibilité et hygiène

Deux runtimes SQLite frais issus du même seed produisent les mêmes références
ordonnées, métriques, causes, décision et les mêmes octets JSON calculés. Les
runtimes, WAL et SHM sont supprimés après chaque run. L'inspection authentifiée
avant/après confirme que la taille et le SHA-256 du seed sont inchangés.

Le rapport machine ne contient ni passage pédagogique brut, ni chemin privé,
ni secret. Le corpus contient seulement des requêtes synthétiques courtes et
des références canoniques.
