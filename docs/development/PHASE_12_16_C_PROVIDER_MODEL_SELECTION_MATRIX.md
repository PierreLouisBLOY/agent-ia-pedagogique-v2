# Phase 12.16-C — Matrice de sélection providers et modèles

## 1. Cadre de scoring

Le score est un outil documentaire, pas un benchmark. Échelle fermée :

- `0` : incompatible ou bloqué ;
- `1` : très faible/risque majeur ;
- `2` : faible ;
- `3` : acceptable mais à calibrer ;
- `4` : solide sur faits officiels ;
- `5` : support officiel fort et faible incertitude.

`FUNCTIONAL_FIT` est plafonné à 3,8 faute de calibration sur corpus
pédagogique. Les mentions provider ne sont pas traitées comme preuve de qualité
française, STMG ou BTS. Pour chaque champ matériel `UNKNOWN`, une pénalité de
0,25 est appliquée à la catégorie concernée, plafonnée à 1 point par catégorie.
Les scores affichés intègrent déjà cette pénalité.

## 2. Poids par workload

| Catégorie | Generation | Correction | Review | Scoring |
|---|---:|---:|---:|---:|
| FUNCTIONAL_FIT | 30 | 35 | 35 | 30 |
| STRUCTURED_OUTPUT | 20 | 20 | 20 | 20 |
| CONTEXT | 5 | 5 | 5 | 5 |
| COST | 15 | 5 | 5 | 5 |
| PRIVACY | 10 | 15 | 10 | 10 |
| API_STABILITY | 10 | 10 | 10 | 10 |
| OPERATIONAL_COMPLEXITY | 10 | 10 | 15 | 5 |
| JUDGE_INDEPENDENCE | 0 | 0 | 0 | 15 |
| **Total** | **100** | **100** | **100** | **100** |

L'indépendance n'est pondérée que pour `EVALUATION_SCORING`. Review conserve un
profil distinct, mais reste une fonction produit ; le judge du harness exige
une séparation plus forte.

## 3. Scores de catégories communs

| Modèle | Structured | Context | Cost | Privacy | Stability | Ops | Judge independence |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gpt-5.6-terra` | 5.0 | 5.0 | 3.5 | 4.0 | 4.0 | 5.0 | 1.0 |
| `gpt-5.6-sol` | 5.0 | 5.0 | 2.5 | 4.0 | 4.0 | 5.0 | 1.0 |
| `gpt-5.6-luna` | 5.0 | 5.0 | 5.0 | 4.0 | 4.0 | 5.0 | 1.0 |
| `claude-sonnet-5` | 5.0 | 5.0 | 3.0 | 4.0 | 5.0 | 3.5 | 5.0 |
| `gemini-3.7-flash` | 4.5 | 5.0 | 4.0 | 1.0 | 4.0 | 2.0 | 5.0 |
| `mistral-medium-3-5` | 4.0 | 3.5 | 4.0 | 4.5 | 5.0 | 3.5 | 5.0 |
| `mistral-small-2603` | 4.0 | 3.5 | 5.0 | 4.5 | 5.0 | 2.5 | 5.0 |

Justifications : OpenAI obtient 5 en structure/contexte grâce au support
schema et aux limites publiées ; Anthropic combine schema, ID pinned et cycle
de vie explicite ; Mistral perd des points de contexte pour ses maxima
input/output inconnus ; Gemini est fortement pénalisé en privacy/ops par
l'incompatibilité potentielle avec les mineurs, le tarif temporaire et les
garanties régionales inconnues. L'indépendance vaut 1 pour les modèles OpenAI
car le generator primaire est OpenAI, et 5 pour les autres providers.

## 4. Matrice Generation

| Modèle | Functional fit | Score pondéré /100 | Rang | Décision |
|---|---:|---:|---:|---|
| `gpt-5.6-terra` | 3.5 | **82.5** | 1 | PRIMARY candidate |
| `gpt-5.6-luna` | 2.5 | 81.0 | 2 | Alternative coût, calibration requise |
| `gpt-5.6-sol` | 3.5 | 79.5 | 3 | FALLBACK qualité |
| `claude-sonnet-5` | 3.3 | 78.8 | 4 | Alternative provider |
| `mistral-medium-3-5` | 3.0 | 75.5 | 5 | Alternative UE |
| `mistral-small-2603` | 2.5 | 73.5 | 6 | Open-weight research only |
| `gemini-3.7-flash` | 3.0 | 67.0 | 7 | Bloqué pour chemin initial |

Terra est retenu pour son compromis catalogue coût/capacité ; Sol est le
fallback de qualité au sein du même contrat technique. Luna ne devient pas
primary avant preuve de qualité pédagogique équivalente.

## 5. Matrice Correction

| Modèle | Functional fit | Score pondéré /100 | Rang | Décision |
|---|---:|---:|---:|---|
| `gpt-5.6-sol` | 3.7 | **83.4** | 1 | PRIMARY candidate |
| `gpt-5.6-terra` | 3.3 | 81.6 | 2 | FALLBACK coût |
| `claude-sonnet-5` | 3.5 | 81.5 | 3 | Alternative provider |
| `gpt-5.6-luna` | 2.5 | 77.5 | 4 | Non retenu sans mesure |
| `mistral-medium-3-5` | 3.0 | 75.0 | 5 | Alternative UE |
| `mistral-small-2603` | 2.5 | 70.5 | 6 | Research only |
| `gemini-3.7-flash` | 3.0 | 63.0 | 7 | Bloqué pour chemin initial |

Correction reçoit un profil différent de Generation : la conservation fidèle
des contraintes est prioritaire sur l'économie. Elle continue d'utiliser
`GenerationPort/CAP-G03` ; aucun nouveau port n'est demandé.

## 6. Matrice Review

| Modèle | Functional fit | Score pondéré /100 | Rang | Décision |
|---|---:|---:|---:|---|
| `gpt-5.6-sol` | 3.8 | **85.1** | 1 | PRIMARY candidate |
| `gpt-5.6-terra` | 3.2 | 81.9 | 2 | FALLBACK coût |
| `claude-sonnet-5` | 3.5 | 81.0 | 3 | Alternative provider |
| `gpt-5.6-luna` | 2.5 | 78.5 | 4 | Non retenu sans mesure |
| `mistral-medium-3-5` | 3.0 | 74.0 | 5 | Alternative UE |
| `mistral-small-2603` | 2.5 | 68.5 | 6 | Research only |
| `gemini-3.7-flash` | 3.0 | 64.0 | 7 | Bloqué pour chemin initial |

Review utilise un profil propre même si son code modèle est identique à
Correction. Cela permet des prompts, limites, métriques et calibrations
distincts sans confondre les responsabilités.

## 7. Matrice Evaluation Scoring

| Modèle | Functional fit | Score pondéré /100 | Rang | Décision |
|---|---:|---:|---:|---|
| `claude-sonnet-5` | 3.8 | **87.3** | 1 | PRIMARY cross-provider judge |
| `mistral-medium-3-5` | 3.2 | 80.2 | 2 | Alternative indépendante/UE |
| `mistral-small-2603` | 2.7 | 77.2 | 3 | Research only |
| `gemini-3.7-flash` | 3.0 | 72.0 | 4 | Bloqué par conditions d'âge |
| `gpt-5.6-sol` | 3.2 | 70.7 | 5 | FALLBACK dégradé, non indépendant |
| `gpt-5.6-terra` | 3.0 | 70.5 | 6 | Same-provider non retenu |
| `gpt-5.6-luna` | 2.5 | 69.0 | 7 | Same-provider non retenu |

## 8. Comparaisons factuelles condensées

| Modèle | Contexte | Max output | Input/cache/output USD/MTok | Batch/cache | Structured output |
|---|---:|---:|---|---|---|
| `gpt-5.6-terra` | 1 050 000 | 128 000 | 2.00 / 0.20 / 12.00 | oui/oui | JSON Schema |
| `gpt-5.6-sol` | 1 050 000 | 128 000 | 4.00 / 0.40 / 20.00 | oui/oui | JSON Schema |
| `gpt-5.6-luna` | 1 050 000 | 128 000 | 0.20 / 0.02 / 1.20 | oui/oui | JSON Schema |
| `claude-sonnet-5` | 1 000 000 | 128 000 | 2.00 / 0.20 / 10.00 | oui/oui | JSON Schema avec limites |
| `gemini-3.7-flash` | 1 048 576 | 65 536 | 0.75 / 0.075 / 3.75 jusqu'au 2026-12-31 | oui/oui | subset JSON Schema |
| `mistral-medium-3-5` | 256 000 total | UNKNOWN | 1.50 / 0.15 / 7.50 | oui/oui | custom schema avec limites |
| `mistral-small-2603` | 256 000 total | UNKNOWN | 0.15 / 0.015 / 0.60 hosted | oui/oui | custom schema avec limites |

| Provider | Rate limits | Data training default | Retention/ZDR | Région UE | Lifecycle |
|---|---|---|---|---|---|
| OpenAI | tiers publics, compte-dépendant | non | logs jusqu'à 30 j; ZDR approuvé | stockage+processing éligibles sous conditions | ID explicite; surveiller dépréciations |
| Anthropic | RPM/ITPM/OTPM par tier | non commercial | 30 j; ZDR enterprise approuvé | garantie UE standard UNKNOWN | ID Sonnet 5 pinned; >=60 j de préavis |
| Google | RPM/TPM/RPD par tier | non payé; oui possible gratuit | durée abuse UNKNOWN; ZDR conditionnel | UNKNOWN | stable; éviter alias latest |
| Mistral | RPS/TPM compte-dépendant | non API | défaut stateless UNKNOWN; ZDR approuvé | endpoint inference UE, control plane non garanti | GA fixe, préavis 6 mois |

Les quatre offres possèdent HTTPS brut et SDK Python. Aucun SDK n'est requis
par leur protocole. La charge de deux familles d'adaptateurs est acceptée
uniquement pour obtenir un judge inter-fournisseur.

## 9. Stratégie d'indépendance du judge

| Option | Décision | Motif |
|---|---|---|
| A — même modèle self-judge | Rejetée | biais de style, erreurs corrélées, self-preference |
| B — autre modèle même provider | Fallback seulement | intégration simple mais indépendance partielle |
| C — judge cross-provider | **Retenue** | meilleure séparation structurelle, à valider par runs aveugles |

`GENERATOR_PRIMARY != JUDGE_PRIMARY`

Le primary judge est `claude-sonnet-5`. Le fallback `gpt-5.6-sol` maintient la
disponibilité mais est explicitement un mode dégradé d'indépendance ; ses scores
ne peuvent pas être mélangés silencieusement avec ceux du judge primary.

## 10. Sélection finale

| Workload | Primary provider/model | Fallback | Alternative provider | Why | Risks / mesure obligatoire | Confidence |
|---|---|---|---|---|---|---|
| GENERATION | OpenAI `gpt-5.6-terra` | OpenAI `gpt-5.6-sol` | Anthropic `claude-sonnet-5` | meilleur compromis documenté structure/coût | français, STMG/BTS, refus, validité schema, latence/coût réels | MEDIUM |
| CORRECTION | OpenAI `gpt-5.6-sol` | OpenAI `gpt-5.6-terra` | Anthropic `claude-sonnet-5` | priorité à fidélité/contraintes | préservation aveugle, variance, coût | MEDIUM |
| REVIEW | OpenAI `gpt-5.6-sol` profil distinct | OpenAI `gpt-5.6-terra` profil distinct | Anthropic `claude-sonnet-5` | critique structurée à haut enjeu | extraction findings, evidence refs, overblocking | MEDIUM |
| EVALUATION_SCORING | Anthropic `claude-sonnet-5` | OpenAI `gpt-5.6-sol` mode dégradé | Mistral `mistral-medium-3-5` | indépendance cross-provider + schema pinned | répétabilité, accord inter-judge, biais, coût runs aveugles | MEDIUM |

Profils documentaires :

```text
GENERATION_PRIMARY_PROFILE = openai.gpt-5.6-terra.generation
GENERATION_FALLBACK_PROFILE = openai.gpt-5.6-sol.generation-fallback
CORRECTION_PRIMARY_PROFILE = openai.gpt-5.6-sol.correction
CORRECTION_FALLBACK_PROFILE = openai.gpt-5.6-terra.correction-fallback
REVIEW_PRIMARY_PROFILE = openai.gpt-5.6-sol.review
REVIEW_FALLBACK_PROFILE = openai.gpt-5.6-terra.review-fallback
SCORER_PRIMARY_PROFILE = anthropic.claude-sonnet-5.scorer
SCORER_FALLBACK_PROFILE = openai.gpt-5.6-sol.scorer-degraded-independence
```

Ces noms ne sont pas injectés dans la configuration runtime en C.

## 11. Stratégie providers et pinning

`INITIAL_IMPLEMENTATION_STRATEGY = MULTI_PROVIDER_FROM_START`

La portée est strictement limitée à deux familles : OpenAI pour D et Review,
Anthropic pour le scorer E. La complexité est justifiée par l'indépendance du
judge ; Google et Mistral ne sont pas implémentés en D/E. Si l'adaptateur
Anthropic ne satisfait pas les gates privacy/contractuels, E s'arrête au lieu de
basculer silencieusement vers un self-judge.

`MODEL_ID_POLICY = PINNED_OR_FIXED_RELEASE_ID`

- OpenAI : IDs explicites `gpt-5.6-terra`, `gpt-5.6-sol`, `gpt-5.6-luna` ; ne
  pas utiliser l'alias `gpt-5.6`.
- Anthropic : `claude-sonnet-5` est officiellement un ID de release pinned.
- Google : ID stable explicite ; jamais `gemini-flash-latest`.
- Mistral : major-minor/release explicite ; jamais `-latest` ou `-major` en
  production.

## 12. Handoffs

### D — Generation/Correction

Implémenter uniquement l'adaptateur outbound OpenAI après revalidation des
facts. Mapper request/response, JSON Schema strict, usage tokens, finish status,
request/model identifiers et erreurs vers les ports existants. Conserver deux
profils séparés, `terra` pour Generation et `sol` pour Correction. Décider le
transport par une revue de dépendance explicite ; aucun retry/fallback métier
n'est ajouté par l'adaptateur.

### E — Review/Scorer

Review reste sur l'adaptateur OpenAI avec profil Sol dédié. Ajouter l'adaptateur
Anthropic seulement pour `EvaluationScorer`, avec structured output strict,
mapping des scores et provenance provider/modèle. Marquer tout fallback OpenAI
comme `DEGRADED_JUDGE_INDEPENDENCE` et séparer ses résultats.

### G — Calibration

Exécuter sur corpus canonique : générations répétées, corrections aveugles,
reviews répétées, scoring aveugle, self-judge contre cross-judge, français
STMG/BTS, long contexte et taux de conformité JSON Schema. Mesurer moyenne,
dispersion, refus, erreurs de schema et accord inter-judge. Aucun threshold n'est
fixé en C.

### H — Limites

Partir des maxima officiels, puis mesurer tokens input/output, latence, coût,
timeouts, capacité input sûre et comportements de saturation. Les plafonds
runtime ne doivent pas être égaux automatiquement aux maxima catalogue.

### F — Sémantique

Revalider séparément prix, dimensions, privacy et lifecycle des embeddings.
Aucun modèle d'embedding n'entre dans les routes B/C.

## 13. Risques ouverts et gates

- aucun modèle n'a encore démontré la qualité pédagogique attendue ;
- Sol a un horizon de prix promotionnel publié ;
- les détails de rétention et de région doivent être confirmés au niveau du
  contrat/account avant données réelles ;
- le fallback scorer même-provider perd l'indépendance ;
- toute utilisation visant des mineurs exclut Gemini Developer API selon les
  conditions auditées ;
- l'option open-weight exige une étude matériel/ops/sécurité séparée.

`MUST_MEASURE_IN_G_OR_H = QUALITY_FR_STMG_BTS, SCHEMA_VALIDITY, REPEATABILITY, REFUSAL_RATE, TOKEN_USAGE, LATENCY, COST, RATE_LIMIT_BEHAVIOR, CROSS_JUDGE_AGREEMENT`
