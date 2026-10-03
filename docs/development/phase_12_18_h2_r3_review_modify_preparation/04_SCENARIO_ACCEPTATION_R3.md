# R3 — Scénario d'acceptation et tests futurs

Statut : PLAN_SYNTHETIQUE — tous les tests ci-dessous NOT_RUN.
Aucun test technique, socket, subprocess de produit ni SQLite n'est lancé dans
cette préparation. Les valeurs ci-dessous sont inventées pour une future fixture,
pas extraites d'une base ou d'un output R2.

## 1. Fixture pilote ex nihilo

Brief : « Contrôle BTS CG — 1 h — bilan fonctionnel et BFR — /20 ».
Les refs de production/version/case/evidence sont de nouveaux ids synthétiques,
sans reprendre les identifiants de la candidate R2 perdue.

D1=6 points/20 min, D2=6 points/20 min, D3=8 points/20 min.
V1 comporte les cinq sections R2, questions identifiées, réponses et critères
dont les points s'additionnent exactement. ProductionReadView conforme R2,
bundle auxiliaire R3 immutable, contexte confirmé et mentions synthétiques.
La factory de tests peut initialiser V1 dans le même store ; aucune route publique
de création arbitraire/import de bundle n'est ajoutée.

Montants en EUR, strings décimales à deux décimales :

| Donnée de base | Composants | Total |
|---|---|---:|
| Ressources stables | Capitaux propres 220000.00 + dettes stables 80000.00 | 300000.00 |
| Emplois stables | Immobilisations 200000.00 | 200000.00 |
| Actif circulant hors trésorerie | Stocks 45000.00 + créances 75000.00 | 120000.00 |
| Passif circulant hors trésorerie | Fournisseurs 50000.00 + autres dettes 30000.00 | 80000.00 |
| Trésorerie active | Disponibilités 70000.00 | 70000.00 |
| Trésorerie passive | Concours bancaires 10000.00 | 10000.00 |

Actif=390000.00, passif=390000.00.
FRNG=100000.00 ; BFR=40000.00 ; TN=60000.00 =70000.00-10000.00.
D1 porte les reclassements/FRNG, D2 le BFR, D3 V1 le calcul et le commentaire de TN.

La V2 fake doit rendre D3 structurellement plus exigeant :
un scénario créances +20000.00, fournisseurs +5000.00 et calcul de l'effet.
Base D1/D2 et leurs octets inchangés ; nouvelles valeurs seulement dans le scénario D3.
Actif circulant scénario=140000.00 ; passif circulant scénario=85000.00 ;
BFR=55000.00 ; FRNG=100000.00 ; TN=45000.00 ; disponibilités=55000.00,
concours=10000.00. Variation BFR=+15000.00 et TN=-15000.00.
Actif et passif scénario=395000.00.
D3 V2 : calculs/scénario 6 points, interprétation argumentée 2 points, toujours 20 min.
Barème global=20.00. Chaque critère/réponse vise les nouvelles questions D3.
Aucune correction V1 copiée à tort sur une nouvelle question.

La difficulté pédagogique réelle exige une appréciation humaine/review sémantique.
Le test vérifie l'ajout effectif d'un raisonnement de scénario et ses calculs ;
il ne prétend pas avoir prouvé automatiquement toute qualité pédagogique.

## 2. Parcours nominal sans provider réel

1. Créer une session synthétique neuve, volatile, R3 explicitement activé avec doubles.
   Relever prod/version V1, revision et bundle_sha256. Ne jamais utiliser latest.
2. Lire V1 par CAP-R02 deux fois : identité et contenu identiques.
3. Commander Review V1 avec ses refs/hash. Le fake traverse AG04 puis retourne un
   rapport completed, findings typés, couverture et limites. Lire le review_ref.
   Comparer tous les hashes V1 avant/après : aucun changement.
4. Commander CAP-A01 sur V1 : les seize checks sont présents. Cas totalement formalisé
   => PASS ; aucune mutation, aucun provider.
5. Envoyer une seule commande « Rends le dossier 3 plus difficile. » avec
   HARDEN_DOSSIER_3, base_version_ref, base_bundle_sha256, expected_revision et UUID.
6. Observer RESERVED/RUNNING puis SUCCEEDED par GET, sans répéter la POST.
   Le fake retourne le delta D3 encodé comme le port générique, M04 l'assemble et
   CAP-A01 contrôle avant publication.
7. V2 publiée atomiquement : même prod, nouvelle ver, parent V1/hash exact.
   V1 reste lisible CAP-R02 avec les mêmes octets.
8. Lire V2 par CAP-R02 et /assessment : correction/barème visent V2, total 20,
   scénarios exacts ; D1/D2/consignes/cas de base inchangés.
9. UI montre V2 courante, V1 consultable, CANDIDATE — NON VALIDÉE.
   Review V1 reste attachée à V1 ; review V2=NOT_RUN. Validation V2 présente.
   Aucune promotion, export, persistance durable ou seconde review automatique.
10. Arrêter : jobs fermés/tués dans les bornes, mémoire libérée.
    Redémarrer : session vide et nonce différent ; anciennes refs introuvables.
    Aucun rechargement d'output depuis un disque.

## 3. Cas sujet R2 sans correction/barème

Créer une fixture distincte : sujet compatible R2 en session, bundle absent.
CAP-R02 lit le sujet ; CAP-A01 renvoie FAIL/ASSESSMENT_BUNDLE_MISSING.
Review complète et modification refusées AVANT provider.
Commander explicitement assessment-preparations avec subject_sha256.
Le fake produit les suppléments ; publication auxiliaire unique et immutable,
sans changer V1 ni son sujet. Vérifier les locators/questions/corrections/barème.
Une préparation répétée avec même clé renvoie le résultat connu sans appel ;
une autre clé refuse ASSESSMENT_ALREADY_PRESENT.
L'ancien rapport de bundle absent reste lié à bundle_sha256=null.
Aucun résultat n'est attribué rétroactivement à ce rapport.

## 4. Matrice de non-régression — 30 obligations

Les identifiants Cxx/Mxx sont ceux de l'inventaire 02, pas des fichiers additionnels.
Ces obligations sont des groupes de cas, pas un compte de tests prétendument passés.

| ID | Cas et oracle attendu | Fichiers futurs |
|---|---|---|
| T01 | Bundle valide ; 5 sections, 3 dossiers, ids exacts, bornes, JSON dupliqué/NaN refusé | C27,C31 |
| T02 | Les 16 checks exhaustifs, tri stable, PASS/FAIL/WARNING et prérequis manquants explicites | C28 |
| T03 | Total 19.99/20.01, points négatifs, somme critères incohérente refusés | C28 |
| T04 | FRNG/BFR/TN et sommes composants incohérents ; bool/float/formule code interdits | C28 |
| T05 | Question sans corrigé, corrigé orphelin, critères orphelins/dupliqués refusés | C27,C28 |
| T06 | Mauvaise production/version/hash/case/ref ; cross-session ; pas de fallback | C27,C32,C33 |
| T07 | Durée/niveau/type/total modifiés et provenance officielle inventée refusés | C28,C29 |
| T08 | Review exact V1, sévérités/catégories canoniques, aucun statut d'autorité importé | C30,C35 |
| T09 | Review ne modifie ni V1 ni current_candidate ; completed ne valide/promote pas | C30,C35 |
| T10 | Préparation des suppléments : sujet identique, une matérialisation, rapports liés au bon hash | C27,C32,C35 |
| T11 | Modification D3→V2, D1/D2 inchangés, correction/barème atomiquement cohérents | C29,C35 |
| T12 | Dépendance D1/D2 non approuvée explicitement refusée, même si provider la justifie | C29 |
| T13 | Delta vide ou simple renommage sans complexification structurelle rejeté | C29 |
| T14 | CAP-R02 V1/V2 exacts, parent correct, ancienne version jamais écrasée | C35,C36 |
| T15 | Mauvaise base, révision périmée, double CAS concurrent : au plus une publication | C32,C35,C36 |
| T16 | Double soumission même id/payload : une opération ; payload différent : 409 | C32,C36 |
| T17 | Job/credential/grant absent : refus avant réseau, provider unavailable fail-closed | C32,C37 |
| T18 | Réponse partielle/JSON invalide/ref inconnue/hors scope : FAILED_OUTPUT, V1 préservée | C29,C31,C37 |
| T19 | Timeout/crash après tentative : UNKNOWN, zéro retry/fallback/restart | C37 |
| T20 | Panne de publication : ni V2 sujet seul, ni bundle orphelin, ni mauvais pointeur | C35,C37 |
| T21 | Concurrence R2 génération et R3 : lease partagé empêche le second dispatch | C35,C37 |
| T22 | 7 nouvelles routes, 9 existantes ; méthode/route en plus, traversal/alias/query refusés | C33,C36,C38 |
| T23 | Host/Origin/nonce/framing stricts ; inconnus non réverbérés ; sécurité pure inchangée | C33,C36,M01,M02 |
| T24 | UI : version sélectionnée≠courante, review liée, NON VALIDÉE, DOM sûr, pas de POST retry | C34 |
| T25 | Stop/restart/expiration : mémoire honnêtement perdue ; pas de lecture de disque cachée | C36,C37 |
| T26 | Capacité : 3 versions, 8 rapports/version, tailles ; aucun effacement silencieux V1 | C27,C32,C35 |
| T27 | Zéro seed/user data/metadata, SQL/FS/SDK métier et credential ; doubles uniquement | C38,C35,C37 |
| T28 | Aucun CAP-A02/A03, promotion, export, persistance/browser storage ou accès externe | C34,C38 |
| T29 | G01–G06 : corps hors scope inchangés, mutants historiques et actifs refusés | C26,C39 |
| T30 | Inventaire59 et hashes : omission/substitution/ajout/staging caché, protected21+6 et mocks Git refusés | C26,C39,M10,M14 |

À compléter par l'exécution des tests R2 existants, guards non modifiés de review/
generation/READ-15/recherche/hygiène/calibration, lint/typecheck/compileall et suite
globale synthétique explicitement approuvée. Aucun test réel seed n'est présenté PASS.

## 5. Vérification UI honnête

Les tests C34 examinent le code et le contrat d'état, sans les présenter comme un test
interactif du navigateur. C36 exécute les réponses HTTP loopback et transitions.
Une recette humaine sur le navigateur local, une fois P_R3_IMPL approuvé, vérifiera
le rendu, les boutons, la navigation V1/V2 et les badges ; résultat séparé,
jamais inventé. Aucun moteur navigateur/dépendance installé pour obtenir un PASS.
Si aucune interaction navigateur n'est autorisée/disponible, noter UI_VISUAL_REVIEW=NOT_RUN.

## 6. Futur scénario réel — pas exécuté ni autorisé

La preuve R2 antérieure n'est pas une fixture réutilisable.
Une V1 nouvellement générée et encore en session, ses projections minimisées et
chacun des appels préparation/review/modification doivent être autorisés séparément.
Le test déterministe demeure local. La review V2 ne se déclenche pas automatiquement.
Les plafonds, modèle et scopes sont à établir sur la future baseline, pas aujourd'hui.

Gate de préparation : DOCUMENTARY_COMPLETE si six pièces cohérentes et hashes valides.
Gate d'implémentation : R3_SYNTHETIC_WIRING_ONLY après tests réellement réussis.
Gate produit réel : NOT_ESTABLISHED tant que la preuve live et l'appréciation
pédagogique n'ont pas eu lieu. Arrêt avant R4/H3 dans tous les cas.
