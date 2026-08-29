# Phase 12.16-G1 — Baseline de fondation de calibration pedagogique

## Verdict

`PHASE 12.16-G1 — PASS / CLOSED`

- `CORPUS_VERSION=12.16-g1-v1`
- `CORPUS_SHA256=abeec0b4e5e1f60f2974ec1c19de34a5307e1b7d92e11c7b811e338d3b2e626d`
- `CALL_MATRIX_VERSION=12.16-g2-plan-v1`
- `CALL_MATRIX_SHA256=997e814f65ac7c5fc25da990cf286800fa6ca4edd761d821a6f6f59f5e2550ed`
- `LIVE_PROVIDER_CALL_COUNT=0`
- `LIVE_PROVIDER_COST_USD=0.000000`
- `CREDENTIAL_STATE=NOT_INSPECTED`
- `NEXT_GATE=12.16-G2_READY_AFTER_EXPLICIT_APPROVAL`

Le corpus, le protocole et la matrice sont `FROZEN`. Aucun appel OpenAI,
Anthropic ou autre fournisseur n'a ete execute. Aucun embedding ou index n'a ete
construit ou reconstruit. G2 n'a pas commence.

## Baseline Git d'entree

- Branche : `phase12/12-16-provider-model-calibration`
- Parent F2B : `619c5a5d11e2091c5a311bc913c4b6684358ff6d`
- `main` : `7ae02ee109bcc6399ec0f71616da6aef07abda81`
- `origin/main` : `7ae02ee109bcc6399ec0f71616da6aef07abda81`
- Avance initiale `main...HEAD` : `0/7`
- Worktree initial : propre

## Proprietaire et reutilisation

Le nouveau proprietaire est strictement limite a
`tests/calibration/pedagogical/`. Il reutilise sans les modifier :

- `CANONICAL_PEDAGOGICAL_SCENARIOS` et `CANONICAL_PEDAGOGICAL_SUITE`;
- `SCENARIO_EXPECTATIONS`, `EvaluationRubric` et
  `EvaluationScoringCriterionSpec`;
- `EvaluationScorerPort`, `ScoreEvaluator`, `RubricAggregator` et
  `NormalizedScore`;
- le mapper et l'`AnthropicEvaluationScorer` de Phase 12.16-E avec transport
  injecte;
- les selections documentees `gpt-5.6-terra`, `gpt-5.6-sol` et
  `claude-sonnet-5` sans changer les routes runtime.

Les hashes de fitness verrouillent les catalogues 12.15, le contrat scoring, le
mapper/scorer, les deux adaptateurs OpenAI, le registre de capacites et le
catalogue workflows dans leur etat d'entree.

## Corpus d'ancres

Les huit scenarios portent exactement les seize criteres canoniques. Chacun a
trois ancres courtes : `a`, `b`, `c`, soit 24 ancres et 48 couples
ancre/critere. Toutes possedent exactement les sections requises par leur
scenario et passent les cinq regles d'admissibilite G1.

Cette admissibilite n'est pas une execution des 37 assertions dures canoniques.
Elle confirme seulement : donnees synthetiques, sections exactes, contenu non
vide, projection bornee, absence d'autorite ou de materiel sensible.

L'ordre d'analyse attendu est strictement ordinal pour chaque critere :
`a > b > c`. Les tiers d'analyse sont stockes hors des ancres. Aucun score exact
et aucun seuil de promotion ou de release n'existent en G1.

## Aveuglement du juge

Chacune des 48 observations contient uniquement : critere, scenario, niveau,
type de tache, projection candidate, contraintes de reference et sections
requises. Elle exclut l'identifiant d'ancre, le tier, le fournisseur, le modele,
le score attendu, l'autorite, la gate, les secrets et chemins.

Les 48 observations ont traverse le mapper Anthropic existant et un
`ScoreEvaluator` avec transport enregistreur. Les 48 appels observes sont des
appels au fake local; aucune requete reseau ou SDK fournisseur n'a eu lieu.

## Matrice G2 preparee, non executee

La matrice comporte 96 appels :

- 20 OpenAI : 8 generation, 2 transformation, 3 correction, 7 review;
- 76 Anthropic : 48 scores d'ancres, 16 repetitions couvrant tous les criteres,
  12 scores de sorties selectionnees;
- 10 appels `gpt-5.6-terra`, 10 `gpt-5.6-sol`, 76
  `claude-sonnet-5`;
- 14 appels primaires, 6 fallback et 76 appels juge.

Les comparaisons Terra/Sol sont limitees a des cas representatifs. Chaque type
de production requis et chaque type de review requis est couvert. Des sous-
ensembles deterministes de generation, transformation, correction et review
sont repetes. SCN-01 et SCN-02 restent des ancres fixes sans generation live.
Ce choix donne une observation diagnostique de chaque type de charge tout en
evitant un produit cartesien modele/cas que la taille du corpus ne permettrait
pas d'interpreter statistiquement.

| Charge | Primaire G2 planifie | Fallback documente |
|---|---|---|
| generation / transformation | OpenAI `gpt-5.6-terra` | OpenAI `gpt-5.6-sol` |
| correction | OpenAI `gpt-5.6-sol` | OpenAI `gpt-5.6-terra` |
| review | OpenAI `gpt-5.6-sol` | OpenAI `gpt-5.6-terra` |
| scoring | Anthropic `claude-sonnet-5` | OpenAI `gpt-5.6-sol`, degrade, documente seulement |

Le fallback scoring OpenAI n'est ni implemente ni appele par G1. La matrice
porte un `model_profile_id` explicite pour chaque appel; le garde le compare avec
le fournisseur et le code modele avant autorisation.

Le plan de cout separe documente 1.087576 USD en estimation de base,
3.277152 USD au maximum avant marge et 4.096440 USD avec 25 % de marge. Il exige
une approbation explicite et une reverification tarifaire avant G2.

- Cost plan Markdown SHA-256 :
  `d1ac051b70034aec9ad1552d5492cf8949e204d320989deaa65c5f63915b7443`.
- Cost plan JSON SHA-256 :
  `08339d9b6169921ab1e6ccda28f0a46bfe4ec5aabdaa3ed345e350646f766474`.

## Mesures preparees

Les contrats test-only calculent sans seuil :

- ordres stricts et faibles, egalites, inversions et cas inconclusifs;
- accord exact des repetitions, ecart maximal et delta rationnel absolu moyen;
- sorties structurees, refus, erreurs et inconclusifs;
- qualite par modele, critere et scenario;
- appels, tokens entres/caches/sortis et latence par call ID.

Le repeat judge ajoute une seconde mesure de l'ancre `a` pour chacun des seize
criteres. Le repeat output ajoute une seconde production a un cas determine de
generation, transformation, correction et review. Cette puissance limitee sert
a reperer une instabilite manifeste; elle n'autorise aucune generalisation.

Les seuls types de decision fermes sont `CALIBRATION_SUPPORTED`,
`CALIBRATION_INCONCLUSIVE` et `CALIBRATION_REJECTED`. Leurs seuils ne sont pas
definis en G1. Aucune conclusion statistique generale n'est autorisee par ce
protocole borne.

## Revue humaine et sorties

Le template de revue humaine est livre vide. Son absence de remplissage signifie
qu'une future conclusion G2 restera provisoire. Les sorties brutes G2 devront
rester sous `artifacts/calibration/12.16-g2/raw`, repertoire ignore. Seuls les
IDs, hashes, mesures d'usage et agregats non sensibles pourront entrer dans un
rapport suivi. Les contenus bruts portent un call ID et un hash, sont conserves
au plus sept jours, puis supprimes apres verification du rapport agrege.

## Validations

Les preuves de cloture sont executees depuis Python 3.12 conformement a
`docs/development/ENVIRONMENT.md`. Le test live est ignore sans
`RUN_PEDAGOGICAL_LIVE_CALIBRATION=1`; meme avec le flag, le scaffold G1 est
ferme avant transport faute d'approbation.

- Python : `3.12.13`.
- Tests G1 cibles : `17 passed, 1 skipped`.
- Regressions 12.15/providers/F2B ciblees : `139 passed, 1 skipped`.
- Pytest global final : `4101 passed, 3 skipped`.
- Ruff global : PASS.
- mypy backend : PASS, 658 fichiers source.
- mypy evaluation_harness : PASS, 30 fichiers source.
- compileall backend/evaluation_harness/tests : PASS.
- `git diff --check` : PASS.

Deux essais globaux precedents ont ete rejetes par les permissions locales : le
premier sur la lecture du seed `G:`, le second sur le basetemp Pytest utilisateur.
Le passage final utilise le meme seed canonique en lecture et un basetemp isole
sous `tmp/`, puis execute toutes les assertions avec succes. Aucun de ces essais
n'a lance un fournisseur.
