# R3 — implémentation et preuves synthétiques

## Identité et périmètre

- Baseline d’entrée : `817ad474d93c78c602a22bd30cf77fe7621e68b1`.
- Manifeste du paquet approuvé : `b9f90be754a2e7dc359087675e23ec4284673e9e5336fe742ecf286a1ddba211`.
- P_R3_IMPL explicitement approuvé par le propriétaire dans la conversation.
- 59 fichiers exacts : 44 créations et 15 modifications ; 6 guards existants amendés dans leurs seuls nœuds autorisés, 2 nouveaux guards.
- Les 27 documents préparatoires (21 antérieurs + 6 R3) restent inchangés et hors commit. Les 37 dépendances en lecture seule conservent leurs SHA-256.
- Aucun nouveau fichier de réalisation, guard supplémentaire, dépendance, lock, migration ou changement de configuration persistante.

## Réalisation

M04 assemble un bundle immutable sujet/corrigé/barème ; M09 réalise CAP-A01 sans agent ni fournisseur ; M08 possède CAS, idempotence, lease commun R2/R3, rapports et publication atomique. Les ponts réutilisent AG03 CAP-G02 et AG04 CAP-V01. CAP-R02 et les sources génération/review historiques sont conservés.

Le registre fermé comprend les 9 routes conservées et 7 routes R3. La sécurité HTTP R2 reste identique (boucle locale, Host/Origin, nonce, framing borné). Les trois assets existants offrent préparation, review, validation et modification ciblée, ainsi que la sélection d’une version exacte. Une séquence de lecture évite l’affichage tardif d’une autre version. Aucun stockage navigateur ni POST répété automatiquement.

Les 16 contrôles CAP-A01 couvrent les liens exacts, le barème /20, les composants et relations FRNG/BFR/TN, les locators du corrigé et les expressions de données REF/ADD/SUB (profondeur 4, 16 opérandes, 60 calculs au maximum). Un texte de réponse non formalisé produit WARNING même si la sortie ne déclare pas cette limite. PASS ne certifie ni la pédagogie, ni les explications libres, ni une validation officielle.

### Clarifications expressément demandées

1. L’échelle source et son locator sont obligatoires. `180.00 kEUR` devient `180000.00 EUR`, tandis que `180.00 EUR` reste `180.00 EUR`. Échelle absente, ambiguë ou incompatible : refus avant publication. Aucune supposition d’unité.
2. La review est liée au couple production/version et au hash du bundle. Le parcours synthétique vérifie une review V1, puis une V2 publiée seulement après CAP-A01, avec `REVIEW_NOT_RUN` et aucun héritage de la review V1. V1 reste strictement inchangée.

Une sortie incorrecte ou une panne de publication ne laisse ni sujet seul, ni bundle orphelin, ni pointeur V2. Les tests couvrent les doubles CAS, l’idempotence, le lease R2/R3, les 3 versions, les 8 rapports/version et l’arrêt des processus synthétiques sans retry. Une assertion d’autorité dans le contenu pédagogique reste rejetée par AG04 inchangé.

## Contrôles réellement exécutés

Outils déjà disponibles : Python 3.12.14, pytest 9.1.1, ruff 0.16.4, mypy 2.3.1, Node 25.9.0. Aucune installation ni consultation réseau.

| Contrôle | Résultat |
|---|---|
| 13 nouveaux fichiers de tests + 6 guards existants amendés | 317 PASS, 72.62 s |
| Non-régression après protection contre les lectures UI tardives | 29 PASS, 6.10 s |
| mypy strict backend, cache externe | PASS, 747 fichiers |
| ruff check . --no-cache | PASS |
| compileall backend, PYTHONPYCACHEPREFIX externe | PASS |
| node --check frontend/app.js | PASS |
| Inventaire exact et empreintes protégées | PASS |
| Scan des 59 fichiers : motifs de clés privées et extensions runtime/binaires | 0 motif / 0 extension |
| git diff --check | PASS |
| Suite globale SYNTHETIC_AUTHORIZED | 5667 PASS, 28 skips préexistants, 0 échec ; 808.03 s |

La suite globale utilise `python -m pytest --import-mode=importlib -q -p no:cacheprovider --basetemp <temp-neuf-externe> --junitxml <journal-externe> --ignore=tests/non_functional/test_retrieval_quality_real_gate.py`. Aucun autre ignore n’est ajouté. Les tests opt-in existants sans leurs prérequis ne sont pas présentés comme exécutés.

Journal JUnit conservé hors dépôt : 5695 tests collectés, 0 failure, 0 error, 28 skipped. SHA-256 : `67be6bfce9056beb986f1fcb2a104aa4bc05dc3c1d2dfa266a27d88766dba858`.

### Incidents de validation, sans modification hors périmètre

- Première collecte globale arrêtée sur deux fichiers historiques homonymes `test_local_browser_read15_http.py` (unit/integration). Résolution uniquement dans le processus par `--import-mode=importlib`, sans renommage, exclusion ni modification des tests historiques.
- La première neutralisation .NET des variables de base les laissait présentes mais vides. Cette tentative globale a été interrompue ; aucun PASS ne lui est attribué. La neutralisation finale utilise `Remove-Item Env:<nom>`, sans lecture/affichage des valeurs. L’absence des cinq paramètres SQLite est vérifiée par un assert de présence uniquement. Les trois gates réelles contrôlées ensuite retrouvent leur skip préexistant « base non configurée ».
- Les opt-ins live/calibration restent absents dans le processus synthétique. Aucun grant antérieur n’est repris.
- Les défauts ordinaires de typage, parsing de sortie, raccordement et fixtures ont été corrigés dans les 59 fichiers approuvés. Aucun guard supplémentaire n’a été affaibli.

## Limites et arrêt

```text
R3_STATUS = R3_SYNTHETIC_WIRING_ONLY
R3_LIVE = NOT_RUN
R3_PRODUCT_COMPLETE = NOT_ESTABLISHED
P_R3_DOC_NETWORK = NOT_AUTHORIZED
ALL_R3_LIVE_PERMISSIONS = NOT_AUTHORIZED
PROVIDER_CALLS = 0
CREDENTIAL_RESOLUTION = 0
USER_DATA_OR_METADATA_ACCESS = 0
CANONICAL_SEED_WRITES = 0
REAL_SEED_GATE = NOT_RUN / NOT_PASS
UI_VISUAL_REVIEW = NOT_RUN
R4 = NOT_STARTED
H3 = NOT_STARTED
```

Les preuves HTTP et d’assets ne constituent pas une recette visuelle interactive. Le stockage R3 est volatil et perdu à l’arrêt. Le worker injectable est synthétique ; la composition normale refuse tout dispatch fournisseur. Le futur live nécessite des décisions, projections minimisées, identité de baseline et budget distincts ; le fichier LIVE_SCOPE_PROPOSAL.json n’accorde aucune autorisation.

Les 28 skips sont les gates de base réelle/live sans prérequis (26) et les tests de liens symboliques indisponibles sur cet environnement (2). Aucun skip/xfail nouveau n’a été ajouté. L’unique exclusion explicite reste la gate réelle de qualité retrieval.

Les contrôles pré-commit sont réussis. Le commit de livraison doit avoir la baseline d’entrée comme parent et exactement les 59 fichiers de l’inventaire ; son identité est fournie dans la réponse de livraison et vérifiable dans Git. Le manifeste couvre les 58 autres fichiers du lot, sans auto-référence. Aucun push ou merge.
