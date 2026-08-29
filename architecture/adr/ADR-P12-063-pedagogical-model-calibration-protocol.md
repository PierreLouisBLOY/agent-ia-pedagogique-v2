# ADR-P12-063 — Protocole de calibration pedagogique des modeles

- Statut : Accepted
- Date : 2026-08-29
- Phase : 12.16-G1

## Contexte

Les routes fournisseur et modele de Phase 12.16 sont configurees, mais leur
calibration pedagogique exige un protocole reproductible avant tout appel live.
Le corpus golden 12.15, ses rubriques, l'evaluation harness, les adaptateurs et
les registres sont deja leurs proprietaires canoniques. Ils ne doivent pas etre
modifies pour porter des donnees ou des politiques de calibration.

Une note chiffree revelee au juge, un identifiant d'ancre semantique ou une
etiquette de qualite introduirait un biais. Un lancement sans matrice figee ni
plafond approuve exposerait aussi le lot a une derive de cout et de cardinalite.

## Decision

La calibration pedagogique dispose d'un proprietaire strictement test-only sous
`tests/calibration/pedagogical/`. Aucun module runtime ni le harness ne peut
l'importer.

Le corpus `12.16-g1-v1` derive les identifiants de scenario, niveaux, intentions,
sections et references de rubriques des proprietaires 12.15. Il contient trois
ancres synthetiques et structurellement valides par scenario, soit 24 ancres et
48 couples ancre/critere. Les attentes sont uniquement ordinales : pour chaque
critere, `a > b > c`. Aucun score exact ni seuil de release n'est defini.

Les etiquettes d'analyse `STRONG`, `MIXED` et
`WEAK_BUT_STRUCTURALLY_VALID` restent dans une table separee. Le juge ne recoit
que sept champs : critere, scenario, niveau pedagogique, type de tache,
projection candidate, contraintes de reference et sections requises. Il ne
recoit aucun identifiant d'ancre, tier, fournisseur, modele, score attendu,
autorite, gate, secret ou chemin.

L'admissibilite des ancres repose sur cinq regles locales. Elle reste distincte
des 37 assertions du corpus canonique et ne pretend pas les executer. La
serialisation reutilise le mapper Anthropic et l'`EvaluationScorerPort`
existants avec un transport injecte dans les tests.

La future matrice live `12.16-g2-plan-v1` est fermee par un checksum. Elle
contient exactement 20 appels OpenAI et 76 appels Anthropic. Les comparaisons
primaire/fallback et les repetitions sont des sous-ensembles bornes; elles ne
forment pas une exploration exhaustive. Toute modification de call ID, modele,
charge, repetition, borne d'entree ou de sortie invalide l'approbation.

Le garde budgetaire G2 est local au protocole de calibration. Il refuse avant
l'appel un checksum, un appel, un fournisseur ou un modele inattendu, un compte
depasse, un plafond absent ou insuffisant, un cout observe hors politique ou une
indisponibilite de credential declaree par l'appelant. Il ne reutilise ni ne
modifie le budget de recovery et n'appelle pas `CAP-T04`.

Les sorties live brutes resteront sous
`artifacts/calibration/12.16-g2/raw`, chemin ignore par Git. Seuls des rapports
agreges, sans contenu brut ni secret, pourront etre proposes a la revue humaine.

## Consequences

- G1 est entierement hors ligne et ne reconstruit aucun embedding ou index.
- Les prix sont un snapshot documentaire/test-only et ne deviennent pas une
  configuration runtime.
- Le scaffold live reste ferme en G1, y compris si son flag est positionne.
- G2 exige une approbation explicite du checksum et du plafond, puis une nouvelle
  verification des prix.
- La revue humaine est obligatoire avant toute confiance definitive; son absence
  rend les conclusions G2 provisoires.

## Options ecartees

- Ajouter les ancres au corpus golden 12.15 : rejet, car la calibration ne doit
  pas modifier la verite de regression.
- Reutiliser les assertions dures comme score pedagogique : rejet, car validite
  structurelle et qualite graduelle sont des responsabilites distinctes.
- Envoyer les tiers ou des scores attendus au juge : rejet pour cause de biais.
- Lancer toutes les combinaisons modele/cas : rejet car non borne et inutile pour
  une decision representative.
- Implementer un scorer OpenAI de fallback en G1 : rejet; seule la decision de
  fallback degrade est documentee pour un lot ulterieur.
