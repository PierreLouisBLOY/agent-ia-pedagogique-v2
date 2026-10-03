# R3 — Décision propriétaire et plan d'exécution

Statut : PROPOSITION À RELIRE — aucune décision préremplie.
Ce document n'autorise rien par lui-même. Il répond au mandat documentaire R3 ;
il ne lance pas l'implémentation.

## 1. Liaison et décision demandée

- Baseline : `817ad474d93c78c602a22bd30cf77fe7621e68b1`.
- Scope : `H2_CONVERSATIONAL_REVIEW_MODIFY_V1`.
- Contrat : `REVIEW-MODIFY-HTTP-LOCAL-1.0`.
- Source mandat ZIP SHA-256 : `c773d127371ae2ad17f4fd78902273a19a4dc268aa900fa5c28c0ef9a44bcac2`.
- Source mandat manifest SHA-256 : `6f88e1032f7e26b6e616bd9eb76b6fc7b1ecd7156426391d069f23ff33c27982`.
- Proposition à approuver : les cinq pièces couvertes par MANIFEST_SHA256.txt,
  plus ce manifeste. Son empreinte externe est fournie avec le ZIP de livraison.
- Futur lot exact : 59 fichiers = 44 CREATE + 15 MODIFY, inventaire 02.
  Les six fichiers de préparation restent hors du futur commit applicatif.
- G01–G06 : six guards existants à faire évoluer, G07–G08 : deux nouveaux.
  Les sources et fonctions hors de leurs scopes restent intactes.

Le propriétaire doit décider P_R3_IMPL pour TOUT ce paquet : contrat du bundle,
matérialisation immutable des suppléments V1, CAP-A01, delta D3 strict,
ports/agents réutilisés, sept nouvelles routes (registre final 16), trois assets,
59 fichiers, huit guards, non-régressions et commit local cohérent après validation.
Aucun fichier ne sera ajouté au fil de l'eau. Un défaut ordinaire se corrige dans
ce lot ; un véritable élargissement est rapporté par son delta exact.

## 2. Permissions séparées

| Permission | Décision aujourd'hui | Portée à soumettre |
|---|---|---|
| P_R3_IMPL | EN ATTENTE du propriétaire | Code, ADR, G01–G08, tests synthétiques et commit local exact |
| P_R3_DOC_NETWORK | EN ATTENTE, non nécessaire pour implémenter avec doubles | Documentation publique officielle du provider retenu avant préparation live |
| P_R3_LIVE_REVIEW | NON AUTORISÉ | Une critique AG04 explicite, entrée/version/hash et coût bornés |
| P_R3_LIVE_MODIFY | NON AUTORISÉ | Une transformation D3 explicite, correction/barème inclus dans le même résultat |
| P_R3_LIVE_PREPARE_SUPPLEMENTS | NON AUTORISÉ | Si nécessaire, un appel distinct pour préparer le bundle d'un sujet existant |
| Nouvelle génération d'une V1 après perte de R2 | NON AUTORISÉ | Prérequis live distinct, jamais reprise du grant R2 |

Aucun nom propriétaire, timestamp, signature ou APPROVED à recopier comme s'il
était acquis. Une réponse d'approbation future doit viser baseline + manifeste
de CE paquet et les permissions choisies, pas un ancien paquet R2.
Approuver P_R3_IMPL n'approuve ni réseau ni budget ni transfert.

### P_R3_IMPL proposé

Tests Python 3.12 avec dépendances déjà disponibles ; sockets HTTP sur loopback ;
sous-processus supervisé fake borné ; magasins de session volatils ; horloge/ids
injectés. Si un test de composition en a besoin, fixtures SQLite synthétiques
neuves sous un nouveau répertoire temporaire système hors dépôt, jamais copie
d'une base existante. Logs/caches/pyc hors dépôt ; configuration limitée au processus.
Tests attestant zéro tentative fournisseur et aucune résolution de credential.

La suite SYNTHETIC_AUTHORIZED est à approuver POUR R3 : seule exclusion proposée,
`tests/non_functional/test_retrieval_quality_real_gate.py`.
L'accord R2 n'est pas automatiquement réutilisé.
REAL_SEED_GATE reste NOT_RUN / NOT_PASS ; aucun autre ignore/skip/xfail de masquage.
Les skips historiques éventuels sont inventoriés et justifiés, jamais présentés
comme tests réussis ni utilisés pour masquer une régression R3.

Interdictions maintenues : seed/runtime utilisateur/sidecars et leurs métadonnées,
migrations, configuration persistante, lock/dépendance nouvelle, résolution réseau,
credentials, provider, payload externe, réécriture des sources/manifests historiques,
push/merge, R4/H3 et calibration. Aucun appel R2, même pour régénérer la candidate.

### P_R3_DOC_NETWORK proposé, plus tard

Lecture seule de documentation publique officielle : disponibilité du modèle/profil,
API de réponse, format, limites entrée/sortie, paramètres, coûts (dont cache/tiers),
rétention et store=false si applicable. Pas de clé, authentification, API de comptage,
payload, dépendance ni installation. Ne pas affirmer que les tarifs ou modèles
historiques R2 sont valides pour R3 sans cette vérification.
Le protocole générique local a été inspecté ; sa viabilité live R3 reste non démontrée.
Un changement de modèle/profil ne doit pas être substitué automatiquement.

### Futur live : décision par appel, pas d'autorisation collective implicite

Trois types d'étapes provider possibles, pas trois appels déjà approuvés.
Sur une V1 complète déjà disponible : review V1 + modification = deux appels
potentiels ; une review V2 est encore un appel indépendant et facultatif.
Sur une V1 sujet seul : préparation des suppléments ajoute un appel potentiel.
Aujourd'hui V1 réelle R2 est perdue : une nouvelle génération préalable serait une
permission supplémentaire et n'appartient pas au présent lot synthétique.

Avant chaque demande live, produire : commit exact, hashes du contrat/runner/entrée
et projection minimisée, modèle/profil documentés, max_input/max_output, prix
documentés, coût maximum recalculé, règle de coût inconnu et nombre d'appels exact.
Si tokens ou coût non établis, refuser le dispatch ; aucune hypothèse gratuite
sur le coût d'un comptage ni crédit hérité de R2.
Le plafond R2 de 0.140000 USD n'est PAS un plafond R3 approuvé.

Transfert : uniquement projections de la V1 synthétique disponible et/ou delta
généré explicitement autorisées, références pédagogiques nécessaires déjà en
mémoire. Aucun SQLite, fichier brut, sortie historique perdue, chemin local,
secret ou donnée personnelle. L'autorisation doit préciser le provider destinataire.
Aucun transfert de sortie d'un fournisseur vers un autre sans accord explicite.

Grant one-shot consommé dès tentative, zéro retry/fallback/rerun ; usage capturé
avant parsing et résultat inconnu traité fail-closed. Les trois types d'étapes
n'impliquent ni fanout ni enchaînement automatique. En particulier une modification
réussie ne lance pas une review V2 toute seule. À l'arrêt : live désactivé.
Les preuves durables techniques d'un futur live restent hors Git et nécessitent
un scope de runner/receipt distinct, non improvisé durant l'implémentation synthétique.

## 3. ADR et guards : décision précise

L'ADR R3 C40 décrit l'extension du produit, relue après approbation et AVANT code.
L'ADR R2, les cinq documents actifs R2 et les 21 préparatoires antérieurs restent
identiques. Ce nouveau contrat versionne une extension ; il ne rebaptise pas une
ancienne preuve pour lui faire couvrir R3.

Les cardinalités ne sont pas fusionnées :
R1=30 chemins, R2 initial=65, correctif R2=22, union R2=67.
R3=59 chemins de delta depuis 817ad474, avec recouvrements explicitement listés ;
ce n'est pas 67+59 fichiers disjoints. Routes R2=9, R3 final=16.
Les nouveaux six préparatoires sont vérifiés par leur manifeste externe au lot et
interdits de staging ; ils ne sont pas un préfixe globalement ignoré.

G01/G05 doivent vérifier DEUX choses :
1. les historiques aux commits de référence immuables, notamment la clôture R2 à 817 ;
2. l'état actif complet R3 (HEAD, working tree ET index, incluant ajouts non suivis).
Une vérification seulement historique ne couvre pas le produit courant.

Les oracles nouveaux ne se contentent pas de croire un JSON modifié par le même diff :
liste littérale indépendante dans tests/support/r3_guard_oracle.py, liaison à ce
paquet approuvé, cardinalités et pré-identités recoupées, tests de substitution
à nombre égal, suppression, duplication, ajout hors allowlist et modification d'index
avec working tree propre. Aucune autorisation par prefix, same-count ou ancien hash.

G03 conserve toutes ses assertions sauf la dernière du test identifié.
G06 conserve le corps sauf sa première assertion de nombre.
G04 ne change qu'une fonction/allowlist de owners backend.
G02 et G05 conservent tous contre-exemples historiques, y compris l'ancienne
normalisation exacte d'une assertion de correction ; celle-ci est prouvée sur
son blob de clôture authentifié, et l'évolution active R3 est contrôlée séparément.
Ne pas contourner un autre guard découvert : signaler fichier/fonction/assertion
et delta demandé, sans lancer un audit général.

Les guards repository_hygiene, calibration_tooling et pedagogical_calibration
sont examinés mais NON MODIFIÉS : aucun de leurs fichiers gelés n'entre dans R3.
Même règle pour les propriétaires SDK, AG04, HTTP pur et contrats canoniques.
Leur exécution future constitue une non-régression, pas une demande d'amendement.

## 4. Réalisation séquencée dans le même incrément

### Étape I — Entrée et ADR

Réutiliser les preuves documentaires encore valides ; vérifier HEAD exact, les
15 pré-SHA, l'absence des 44 CREATE et les sources protégées. Aucun accès de base.
En cas de dérive réelle, décrire les seuls chemins divergents.
Relire et matérialiser l'ADR C40 avec approbation liée au paquet ; aucun commit
isolé qui neutraliserait un guard avant le produit.

### Étape II — Métier et doubles

C01–C10 : DTO bundle/révision, M04, CAP-A01 M09 et 16 checks.
C24–C25 et C27–C31 : fixtures, doubles, tests de schéma, nombres, review et mapping.
Pas de réponse provider bricolée pour forcer PASS : contre-exemples explicites.
La fixture est créée ex nihilo, sans import d'anciens outputs ni reproduction
du texte de la candidate R2 perdue.

### Étape III — Session, ports et publication

C11–C16, M03 : réservation, idempotence, M04/M09, R3Store sous le même verrou.
C18–C23 : ponts canoniques AG03/AG04, job fake supervisé, worker et composition.
M04–M06 : raccordement borné aux points de composition existants.
CAP-R02 et DTO R2 inchangés. Tests de CAS et de panne avant/après publication.
Les deux bundles sujet/correction/barème doivent être atomiques et comparables.

### Étape IV — HTTP/UI et guards ensemble

C17, M01–M02, M07–M15, C26, C32–C39 :
sept routes fermées, trois assets, non-régressions G01–G08.
Les états R2 restent compatibles, les états R3 sont dans leur enveloppe versionnée.
Aucun nouveau JavaScript asset, framework serveur ou import SDK métier.
Corriger les défauts ordinaires dans les 59 chemins ; pas de neutralisation
isolée d'un test ou de diminution du scénario.

### Étape V — Validation réelle synthétique puis commit borné

C41–C44 : contrat actif, preuves réelles, proposition live non autorisée et manifest.
Exécuter seulement APRÈS accord P_R3_IMPL et permission du profil synthétique.
L'ordre et les commandes indicatives suivants reprennent ENVIRONMENT.md sans
installation ni réseau :

- Python 3.12 déjà disponible ; PYTHONDONTWRITEBYTECODE=1.
- compileall backend, avec PYTHONPYCACHEPREFIX vers un nouveau dossier temp externe.
- pytest ciblé sur les 13 nouveaux fichiers de test, plus les six guards modifiés
  et les non-régressions R2/READ-15/recherche/review/generation/hygiène historiques.
- pytest global SYNTHETIC_AUTHORIZED : `python -m pytest -q -p no:cacheprovider --basetemp <nouveau-temp-externe> --ignore=tests/non_functional/test_retrieval_quality_real_gate.py`.
- `python -m ruff check . --no-cache`.
- `python -m mypy backend --cache-dir <nouveau-cache-externe>`.
- Git diff --check, inventaire exact HEAD/index/working, scan des ajouts pour secrets,
  données runtime, SQLite, prompts/réponses bruts, sources protégées et pollution temp.

Les chemins <...> sont à allouer sous le temp système, jamais à exécuter littéralement.
Ne pas lire une valeur de configuration utilisateur pour en dériver le chemin.
Une configuration legacy parasite est neutralisée uniquement dans le processus
synthétique, sans en afficher les valeurs ni suivre ses chemins.
Si dépendance absente : état explicite NOT_RUN, aucune installation implicite.

Reporter nombre réellement exécuté, passes/échecs/skips, commandes, versions et
durées réelles. Ne jamais déduire la réussite d'une lecture de source ou du paquet.
Aucune suite n'a été exécutée pendant cette préparation.

Après PASS de tous contrôles applicables et revue du diff : un seul commit local
cohérent sur les 59 chemins exacts, sans les six préparatoires ni les 21 anciens,
sans runtime/receipt/output. Pas de push/merge. La nouvelle baseline est alors le
commit obtenu, et ne peut recevoir un live sans nouvelle liaison explicite.

## 5. Sortie de l'implémentation future et arrêt

R3_SYNTHETIC_WIRING_ONLY si la suite synthétique passe.
REAL_SEED_GATE=NOT_RUN/NOT_PASS.
R3_LIVE=NOT_RUN ; R3_PRODUCT_COMPLETE=NOT_ESTABLISHED.
Le scénario prouve la plomberie métier synthétique et ses refus, pas la qualité
d'un modèle réel ni la validation humaine d'un sujet.
Livrer code/commit/preuves ; arrêter avant live, R4/H3.
Prochaine action aujourd'hui : revue propriétaire de CE paquet unique.
