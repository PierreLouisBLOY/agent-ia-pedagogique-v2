# Phase 12.16-F2B — Semantic retrieval réel

## Verdict

```text
PHASE 12.16-F2B — PASS / CLOSED
SEMANTIC_RETRIEVAL = ESTABLISHED
EMBEDDING_MODEL = text-embedding-3-large
SEMANTIC_INDEX = DERIVED_LOCAL_REBUILDABLE
NEXT_GATE = 12.16-G_READY
```

La finalisation R2 ferme la seule régression observée sans modifier le corpus,
les références attendues ni RRF. Le seed prouve que `SI` est un alias actif de
`notion:systeme-dinformation`. La projection v3 inclut donc tous les alias
canoniques actifs et l'embedding d'une requête qui correspond exactement à un
alias non ambigu reçoit aussi le libellé canonique résolu. Cette règle générale
n'encode ni `SI` ni une expected ref F1.

La gate R1 offline passe à 16/16 récupérations F2A. L'unique run R2 Large passe
ensuite exact-label à 100 %, 16/16 F2A, 17/25 gaps résiduels en SEMANTIC et
16/25 en COMBINED. `SI` est rang 5 LEXICAL, rang 1 SEMANTIC et rang 1 COMBINED.
`rrf_k=60`, `channel_limit=20` et `final_limit=10` restent inchangés.

Le rapport machine complet est
`docs/development/PHASE_12_16_F2B_SEMANTIC_RETRIEVAL_REPORT.json`.

## Préflight, seed et corpus

- branche et HEAD : `phase12/12-16-provider-model-calibration` à
  `5af496494cef6de565fc8a5bf3270e0c346a4396` ;
- `main` et merge-base :
  `7ae02ee109bcc6399ec0f71616da6aef07abda81` ; relation `0/6` ;
- seed : 105 553 920 octets,
  `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` ;
- intégrité/quick : `ok` ; violations FK : `0` ; seed inchangé après les runs ;
- corpus immuable : `12.16-f1-v1`, 60 cas,
  `f9ebd4330c1f4b5d06021b8a29d4d12db4cfaff05b535eec0ff86da4d842f238`.

La clé live a été résolue uniquement par :

```text
ProviderCredentialRef
-> ProviderSecretResolver
-> ProviderSecretValue
-> reveal_for_transport()
```

Aucune valeur de clé n'a été affichée, journalisée ou écrite.

## Gate R1 et autorisation R2

L'approbation explicite de l'utilisateur a été enregistrée avant le live. Le
préflight R1 a authentifié le seed et rejoué hors ligne les 60 requêtes via les
vrais `EvidenceSearchPort`, `EvidenceAdmissibilityPort`, coordinateur et RRF.

```text
R1_OFFLINE = PASS
EXACT_LABEL_COMBINED_RECALL_AT_5 = 100%
F2A_RECOVERIES = 16/16
SI_ALIAS = ACTIVE -> notion:systeme-dinformation
SI_OFFLINE = LEXICAL 5 / SEMANTIC 1 / COMBINED 2
```

L'estimation publiée avant le live était un plafond prudent de 2 678 901
tokens, soit 0,34825713 USD au prix Large revalidé. Elle supposait jusqu'à un
token par octet ajouté par les alias. Le coût observé, 0,34759491 USD, reste
sous ce plafond.

## Revalidation officielle au 2026-08-29

| Candidat | Contexte | Dimension par défaut | Prix input |
|---|---:|---:|---:|
| `text-embedding-3-small` | 8 192 tokens/input | 1 536 | 0,02 USD / 1M tokens |
| `text-embedding-3-large` | 8 192 tokens/input | 3 072 | 0,13 USD / 1M tokens |
| `mistral-embed-2312` | 8k | documentée par Mistral | 0,10 USD / 1M tokens |

OpenAI documente 300 000 tokens sommés par requête embeddings et le paramètre
`dimensions` pour les modèles `text-embedding-3`. `large` est présenté comme
le modèle embeddings OpenAI le plus capable pour l'anglais et le non-anglais.
Sources : [small](https://developers.openai.com/api/docs/models/text-embedding-3-small),
[large](https://developers.openai.com/api/docs/models/text-embedding-3-large),
[guide embeddings](https://developers.openai.com/api/docs/guides/embeddings).

Pour les contrôles de données, `/v1/embeddings` ne stocke pas d'état applicatif,
est éligible au Zero Data Retention, et les données API ne servent pas à
l'entraînement par défaut sauf opt-in. Les logs d'abuse monitoring peuvent être
retenus jusqu'à 30 jours par défaut. Le traitement régional européen exige un
projet éligible et `eu.api.openai.com`; cette propriété n'a pas été affirmée
pour les runs effectués sur l'endpoint SDK par défaut. Source :
[OpenAI data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint).

Mistral reste une alternative opérationnelle européenne, avec endpoint régional
`api.eu.mistral.ai` : [modèle](https://docs.mistral.ai/models/mistral-embed-23-12),
[prix](https://mistral.ai/pricing/api/),
[inférence régionale](https://docs.mistral.ai/inference/regional-inference).
Google et Anthropic restent hors chemin initial conformément aux décisions
précédentes.

## Dimensionnement avant architecture vectorielle

| Mesure | Valeur |
|---|---:|
| Chunks CURRENT canoniques | 26 848 |
| Objets canoniques uniques | 26 724 |
| Caractères / octets UTF-8 | 5 218 631 / 5 465 536 |
| Longueur chars min / médiane / p95 / max | 2 / 163 / 431 / 1 422 |
| Longueur UTF-8 min / médiane / p95 / max | 2 / 171 / 450 / 1 484 |
| Projection UTF-8 min / médiane / p95 / max | 79 / 274 / 621 / 6 224 |
| Chunks/projections potentiellement > 8 192 | 0 / 0 |

Répartition par type registre : CORRECTION 4 197, FRAMEWORK_ELEMENT 984,
METHOD 1 399, NOTION 752, OFFICIAL_OCCURRENCE 762, PEDAGOGICAL_CONTENT
11 733, QUESTION 5 622, RESOURCE 1 399.

Répartition par chunk : CORRECTION 4 197, METHOD 1 399, NOTION_ALIASES 124,
NOTION_LABEL 628, OFFICIAL_FRAMEWORK_ELEMENT 984, OFFICIAL_OCCURRENCE 762,
PEDAGOGICAL_CONTENT 11 733, QUESTION 5 622, RESOURCE_TITLE 1 399.

Aucun découpage n'est nécessaire. Les payloads float32 seuls sont estimés à
27 492 352 octets en dimension 256, contre 164 954 112 en 1 536 et
329 908 224 en 3 072. Pour un scan cosine exact standard-library, 256 réduit
le stockage et le travail par 6×/12×. Cette réduction a été testée sur les 60
cas pour les deux modèles, et la dimension réellement retournée est inscrite
au manifest.

## Architecture réalisée

`ModelProfileConfig` n'a pas été détourné avec un faux
`reserved_output_tokens`. Le même owner config contient maintenant un
`EmbeddingProfileConfig` minimal et le workload technique
`SEMANTIC_EMBEDDING`. Les anciennes configs restent valides et aucun nouveau
capability ni registre n'est créé.

Le transport interne `OpenAISDKEmbeddingTransport` utilise le SDK existant,
`max_retries=0`, un timeout configuré, des batches bornés, des erreurs fermées
et seulement les compteurs d'usage sûrs. Le pacing de 10 secondes a été fourni
explicitement au builder live pour respecter le débit ; ce n'est pas un retry
et sa valeur par défaut reste zéro.

Projection déterministe v3 :

```text
canonical_object_ref: <ref>
chunk_type: <type>
content:
<texte CURRENT>
[active_canonical_aliases:
 <tous les alias ACTIVE de la notion, ordre fixe>]
[linked_canonical_context:
 <contenus pédagogiques canoniquement liés, ordre fixe, plafond 6000 octets>]
```

Le seed contient 182 alias actifs répartis sur 124 notions canoniques. Pour une
requête égale à un alias compact actif non ambigu, l'entrée query devient
`original_query + resolved_canonical_alias`; les alias multi-mots restent dans
la projection mais ne sont pas réécrits côté query dans ce lot. Dans F1, cette
règle couvre `SI`, `amortissements` et `ABC`. Le score final reste le cosine de
l'embedding réellement retourné.

Les liens généraux `content_notion`, `method_notion` et `resource_notion`
produisent 10 190 arêtes de roll-up. Lorsqu'un passage lié porte le meilleur
score, le backend peut reporter ce score vers le vrai passage-label CURRENT de
la notion, tout en conservant `matched_passage_ref` en provenance. Le gate F2A
revalide ensuite ref, locator, checksum, freshness, scope et autorité. Aucune
expected ref F1 ne participe à la projection. Checksum de corpus projeté :
`2759d3a932b2a1bf407a720bdf033ab8a23ca6bb2cb3d793b72be7f844642990`.

Le sidecar SQLite séparé est dérivé, local, non autoritatif et reconstructible :
schema 2, manifest seed/model/dimension/projection/count/checksum, BLOB float32
little-endian, norme positive, clé de ligne déterministe et table de roll-up.
Le build écrit un temporaire transactionnel, exécute `quick_check`, relit le
manifest puis fait un remplacement atomique. Aucun build n'a lieu à l'import
ou dans une requête. Tout mismatch devient
`SEMANTIC_INDEX_STALE_OR_INCOMPATIBLE`; missing index, timeout, rate limit ou
provider unavailable dégradent uniquement le canal optionnel.

La recherche brute-force cosine est fonctionnelle à cette échelle : environ
1,8 seconde médiane, p95 sous 1,92 seconde, et une sonde `tracemalloc` autour
d'une requête mesure environ 55 Mo. Ce sont des mesures de faisabilité, pas un
SLA. Aucun vector DB ou nouvelle dépendance n'est justifié à ce stade.

## Comparaison et validation live finale

La comparaison initiale v2 a testé Small et Large sur le même seed, la même
projection, la dimension 256 et les mêmes 60 requêtes ; elle a sélectionné
Large car il récupérait 17/25 gaps SEMANTIC contre 14/25 pour Small. Conformément
à R2, Small n'a été ni reconstruit ni retesté. Le seul run final a utilisé Large
avec la projection v3 et le même corpus immuable. Les sidecars v2/v3 mesurent
46 133 248 octets.

| Mesure globale | small SEMANTIC | small COMBINED | large SEMANTIC | large COMBINED |
|---|---:|---:|---:|---:|
| Recall@1 | 20,00 % | 46,67 % | 6,67 % | 46,67 % |
| Recall@3 | 63,33 % | 73,33 % | 51,67 % | 71,67 % |
| Recall@5 | 71,67 % | 80,00 % | 66,67 % | 83,33 % |
| MRR@5 | 0,421944 | 0,606667 | 0,313611 | 0,612500 |
| ZeroHitRate | 0 % | 0 % | 0 % | 0 % |

| Faisabilité | small | large |
|---|---:|---:|
| Build | 410 180 ms | 387 161 ms |
| Appels build | 34 | 34 |
| Tokens build | 2 671 835 | 2 673 375 |
| Tokens 60 queries | 392 | 432 |
| Coût expérimental estimé | 0,05344494 USD | 0,34759491 USD |
| Latence médiane / p95 | 1 800,341 / 1 918,070 ms | 1 680,882 / 1 740,675 ms |

Classes sémantiques attendues :

| Classe | small SEMANTIC R@5 | small COMBINED R@5 | large SEMANTIC R@5 | large COMBINED R@5 |
|---|---:|---:|---:|---:|
| E — paraphrase pédagogique | 50 % | 50 % | 60 % | 60 % |
| F — description conceptuelle | 60 % | 60 % | 80 % | 80 % |

Les métriques Recall@1/3/5, MRR@5 et ZeroHitRate par classe et par niveau sont
dans le JSON. Le run final Large conserve les performances E/F de la comparaison
initiale (60 % / 80 % Recall@5), exact-label reste à 100 %, les 16 récupérations
F2A sont toutes préservées, et le gain sémantique matériel reste 17/25. Le
surcoût de Large n'a été examiné qu'après ce delta qualité mesuré.

## Gate no-regression et misses résiduels

La gate no-regression passe à 16/16. `RQ-SYSTEME-INFORMATION-D` (`SI`) est rang
5 LEXICAL, rang 1 SEMANTIC et rang 1 COMBINED. Aucun calibrage de RRF n'a été
fait et le corpus F1 reste byte-identique.

Les dix misses COMBINED résiduels sont ACTION-COLLECTIVE B/E/F,
SYSTEME-INFORMATION E, DEMARCHE-MARKETING E, MARCHE D, BILAN D,
AMORTISSEMENTS D/F et METHODE-ABC E. `MARCHE D` reste une interaction de
ranking/fusion (rang 5 SEMANTIC, hors top 5 COMBINED). Les autres restent des
misses de modèle/ranking malgré des contenus liés présents. Aucun expected ref
ambigu, manque de source ou besoin relationnel n'a été démontré.

## Exécutions et nettoyage

Commandes live, sans secret :

```text
RUN_F2B_LIVE_SEMANTIC_BENCHMARK=1
F2B_LIVE_MODEL=text-embedding-3-large
F2B_LIVE_REPORT_PATH=<absolute temporary json path>
python -m pytest -q -p no:cacheprovider tests/non_functional/test_semantic_retrieval_live_gate.py
```

Résultats acquis :

- R1 offline seed réel, 60 requêtes : `1 passed`, exact-label 100 %, 16/16 ;
- R2 live Large, un index et 60 requêtes : `1 passed in 585.08s` ;
- configuration/transport/index/admissibilité/AG-02 ciblés : 172 passed ;
- runtime/C1/SCN-02/SCN-04/génération/suite canonique/F1 réels :
  `22 passed in 533.22s` ;
- premier global finalisable : 4 082 passed, 2 failed, 2 skipped ; les deux
  échecs étaient exclusivement les fitness anti-artefacts détectant le
  basetemp réel précédent sous `.tmp` ;
- après suppression vérifiée de `.tmp`, les deux fitness : 2 passed ;
- global final sur basetemp externe neuf :
  `4 084 passed, 2 skipped in 847.67s` ; les skips sont les gates R1/live
  explicitement opt-in ;
- Ruff : PASS ; mypy backend : 658 fichiers, PASS ; mypy
  evaluation_harness : 30 fichiers, PASS ; compileall backend,
  evaluation_harness et tests : PASS ; `git diff --check`, validation JSON,
  scans secrets, chemins privés et bases runtime : PASS.

Tous les index/runtime temporaires ont été supprimés, le seed réauthentifié
inchangé, et aucun fichier vectoriel n'est tracké. Les gates R1/live restent
skip par défaut. Les dépendances runtime restent exactement `openai>=3.5,<4`.

## Livraison

`ADR-P12-062` fige la sélection de `text-embedding-3-large`, la projection v3,
le sidecar local dérivé, l'admissibilité commune et la dégradation optionnelle.
Toutes les validations de promotion sont passées. Ce document et l'ADR font
partie du commit F2B unique direct sur F2A ; son SHA final est rapporté après
création/push, tandis que `main` reste inchangé.
