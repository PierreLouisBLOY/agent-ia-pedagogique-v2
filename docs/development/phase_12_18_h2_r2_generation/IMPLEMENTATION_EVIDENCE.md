# R2 — Réalisation synthétique et clôture des guards historiques

Statut : R2_SYNTHETIC_WIRING_ONLY.
Scope : H2_CONVERSATIONAL_GENERATION_V1 / CONVERSATION-HTTP-LOCAL-1.0.
Baseline d'entrée : 19c42bc9f4b0b1a97b9bd2d6b880acd7378459f7.
Manifeste préparatoire approuvé : 359b06ab34aa092831bd0d0eea909fc4b030776eef49414edbe7932f97eb9d6c.
ZIP préparatoire approuvé : 32da3affbff6c5f7f2ce699bf7b82422adc121c879b16a3e1f1ef4ba5ed93cdb.

## Autorité et périmètre exact

P_IMPL et P_DOC_NETWORK sont approuvées ; P_LIVE n'est pas autorisée.
Le périmètre final contient 65 fichiers : 45 créations et 20 modifications.
Les 60 chemins initiaux sont complétés exclusivement par les amendements
explicitement approuvés dans cette tâche :

- R2-C03-1 : backend/agent_runtime/contracts/planning/delegation.py.
  Exception AG01 → AG02, marqueur R2-EVIDENCE-MANDATE-1.0 présent sur le step
  et la délégation, liste ordonnée CAP-E01/E02/E03, lecture seule, profondeur 1,
  aucune redélégation, budgets explicites égaux, zéro retry/tool, au plus
  deux steps et 120 secondes. Les autres délégations restent mono-capacité.
- R2-HISTORY-1 : tests/architecture/test_pedagogical_calibration_fitness.py
  et tests/calibration/pedagogical/repair_tranche_v4_2.py.
  Authentification des trois blobs de génération historiques au commit
  a560d6ca1989ba3dd13c9d02eeb97ef3fff6238b et contrôle indépendant du delta
  actif R2. Leurs octets ont été vérifiés identiques à V4.1 et à l'entrée R2.
  Les constantes de matrices, pricing, carry-forward et manifests historiques
  ne sont pas remplacées. Une identité historique valide ne permet pas un
  ancien live sur des sources actives différentes : ce cas est refusé.

L'ADR et les oracles d'inventaire/AST enregistrent ces décisions. Les assertions
hors des nodes autorisés sont conservées. Les 17 documents protégés et les
quatre pièces préparatoires restent byte-identical, séparés et hors commit.
Le manifeste de réalisation contient les 64 autres fichiers ; aucune
auto-référence au manifeste ou au commit qui le contiendra.

## Réalisation et frontières

Le dialogue local clarifie le pilote sans inventer l'année de BTS, conserve
les échanges et le contexte M07, exige sa confirmation puis entre par M04.
M08 possède conversation, travail long, idempotence/CAS, store volatil et
CAP-R02. Ce dernier lit exactement production_ref + version_ref, sans
fallback latest, provider, mutation ni accès à une autre conversation.

La chaîne synthétique traverse les composants réels : sélection AG01,
PlanCompiler, PlanExecutor, RoutingStepRunner unique, politiques/budgets,
AG02 avec admission F2A et contenu OP13, puis AG03,
GenerationCoordinator/GenerationOutputGuard et ProductionCandidate C08.
Le snapshot SQLite synthétique est fermé avant le port de génération.
Les références déclarées utilisées doivent être un sous-ensemble non vide
des références effectivement transmises. Aucun statut officiel n'est inventé.

Les neuf routes restent fermées ; READ-15/R1 sont conservés. Les commandes
POST sont bornées et protégées par Host/Origin/nonce/intent/framing. GET ne
déclenche aucun travail. L'enfant unique possède un IPC borné, watchdog,
arrêt supervisé et reçu technique one-shot externe. UNKNOWN interdit le rappel.
Les stores de session sont volatils, limités à deux heures et trois candidates ;
ils ne constituent pas une sauvegarde R4.

Les trois assets affichent du texte non actif, le contexte, la candidate
NON VALIDÉE et ses références/version exacte. « Modifie le dossier 3 » est
hors scope R2. Aucun AG05, review, validation pédagogique, promotion, export,
nouveau runner, catalogue, budget engine, SDK ou dépendance n'est ajouté.
Les doubles de génération et fixtures sont explicitement limités aux tests.

## Contrôles réellement exécutés

Python 3.12.14 et dépendances déjà présentes. L'environnement enfant est
reconstruit à partir d'une allowlist, sans inspection des valeurs ambiantes
credential/seed/runtime ; aucun opt-in réel n'est transmis.
PIP_NO_INDEX=1, PYTHONDONTWRITEBYTECODE=1 et
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. Fixtures, JUnit, reçus, caches et bytecode
sont exclusivement sous un répertoire temporaire privé hors dépôt.

| Contrôle | Résultat observé |
| --- | --- |
| Global SYNTHETIC_AUTHORIZED après R2-HISTORY-2 | 5456 passed, 0 failed, 28 skipped ; 719.85 s |
| T01–T11, guards modifiés et contrats multi-agents, état final | 397 passed, 0 failed, 0 skipped ; 124.31 s |
| Réemplois et guards préservés, liste distincte des ciblés | 768 passed, 0 failed, 0 skipped ; 63.55 s |
| Adaptation historique R2-HISTORY-1 ciblée (trace antérieure) | 41 passed ; 20.90 s |
| Ruff global, --no-cache | PASS |
| Mypy backend, cache externe | PASS, 724 fichiers |
| Compileall backend et calibration_tooling, bytecode externe | PASS |
| pip check, hors réseau | No broken requirements found |
| node --check frontend/app.js | PASS |
| git diff --check | PASS |
| Inventaire | 65 fichiers exacts : 45 créations, 20 modifications |
| Documents protégés et préparatoires | 21/21 SHA conservés, hors index |
| Recherche ciblée de secrets et fichiers runtime | Aucun candidat dans les 65 fichiers approuvés |

Les comptes ciblés et de réemploi se recouvrent avec la suite globale ; ne pas
les additionner au total global. La suite globale finale inclut tous les tests
R2-HISTORY-2 et F58, sur le code fonctionnel figé. Les écritures documentaires
finales ne modifient pas le code exécuté.

Commande globale réellement exécutée :

```text
python -m pytest --ignore=tests/non_functional/test_retrieval_quality_real_gate.py --import-mode=importlib -p no:cacheprovider --basetemp <temp-externe>/history2-global-index-final --junitxml <temp-externe>/history2-global-index-final.xml -q --tb=short
```

Preuves JUnit privées, conservées hors dépôt (noms relatifs au répertoire
temporaire de validation de cette tâche) :

| Fichier | SHA-256 |
| --- | --- |
| history2-global-index-final.xml | cfec50fb6dc37d7e4737bab0b496fb4b302db45c64678f60e24dba36a937bf9c |
| history2-target-index-final.xml | d6aae8265157c1e66b484ddb4f394cb41d42dea59aacca93228aa4ff651dd2c1 |
| history2-global-final.xml (passe intermédiaire) | 0caef0f1d089fbb86ea997c1148fbcd893a9baf58e062d4498a5e2d600b3ec45 |
| history2-index-counterexamples.xml | a3cae894e194fbeb03cc3f6f8b46aeddd4127155326d94295b5e70ec4f514d6d |
| history2-target-final.xml | 65fc22a9cf9eb6850efbd470f9c59e1524d5570bdeeed054238021f0f7a1dba4 |
| history2-reuse-final.xml | 5a5da0bf13d98366c0545de3d26ea8d119a2c1f43cdcf980c6489d491d0a8620 |
| global-history-approved.xml (ancien blocage 5351/2/28) | 050b57f006cc6f3780a14e7f5d18bb00f3a1c33b1df608f508c2eed55137f9db |
| final-targets.xml | ab7a531f83395f0ccaa53dff5d09ddac965ef0fe7b8c6f675d655525fdb29214 |
| history-r1.xml | 0b15f3d70a48c89a321ce5e947bc2cd0e0a85a13c1e5ca4057fc46c9bd6e4b8c |

Par rapport aux 5381 cas de la trace 5351/2/28, les 5484 cas finaux ajoutent
103 tests : 99 régressions R2-HISTORY-2, un contrôle F58 absent de l'ancienne
collecte et trois contre-exemples d'index. Les deux anciens échecs passent.
Ces différences expliquent le total observé sans convertir de skip en succès.

Les 28 skips préexistants restent distincts des succès : 23 gates SQLite non
configurées, trois gates retrieval/calibration non activées et deux tests
de liens symboliques indisponibles. L'unique exclusion est celle explicitement
autorisée. REAL_SEED_GATE = NOT_RUN / NOT_PASS.

### Échecs intermédiaires résolus, non masqués

La première suite globale avait 5294 passed, 37 failed et 28 skipped
(634.55 s). Une assertion de hash actif et 36 assertions de matrices dérivées
confondaient sources historiques et code actif. Le travail a été arrêté
avant toute adaptation ; R2-HISTORY-1 a ensuite été soumis et approuvé.
La reprise ci-dessus résout ces 37 échecs, sans nouveau skip, ignore ou xfail.
Elle avait révélé les deux contrôles transverses supplémentaires détaillés ci-dessous,
ensuite corrigés après l'accord explicite R2-HISTORY-2.

Une ancienne suite ciblée avait 243 passed et un échec d'attente de cinq
secondes du harness produit sous typecheck concurrent. L'attente de test
est désormais de douze secondes ; SDK 90 s, watchdog produit 120 s et bornes
d'arrêt sont inchangés. La reprise immédiate a réussi (18 tests, 13.47 s),
puis la suite ciblée finale complète ci-dessus a réussi.

## R2-HISTORY-2 — accord explicite et deux échecs résolus

L'état d'entrée réel était 5351 passed / 2 failed / 28 skipped en global,
et 255 tests ciblés réussis. Les deux échecs ont été conservés et reproduits
isolément (history-freeze-blocker.xml, deux échecs en 0.48 s) avant ce correctif.
Aucune nouvelle suite globale n'a servi seulement à reproduire ce blocage.

L'accord explicite du propriétaire autorise les deux chemins ci-dessous,
65 fichiers = 45 CREATE + 20 MODIFY, et un commit cohérent après validation.
Les deux SHA PRE ont été revérifiés avant édition. Aucun timestamp/signature
n'est inventé. Le ZIP externe a été lu sans extraction : quatre pièces
vérifiées contre son manifeste, sans ajouter son contenu au dépôt.

- ZIP SHA-256 : 9d006e13901f235dda2ac2c6a4dafe9f819daecf0cb91e79c9e08aed69a94d9b.
- Manifeste du ZIP : 20766a35b1caa5115ee661c3f9a179dd9f8524948ead4d51d6e1343de73b3d82.

| Source | Node unique modifié | SHA PRE | SHA POST |
| --- | --- | --- | --- |
| tests/architecture/test_calibration_tooling_boundary.py | test_all_40_historical_files_are_byte_exact_and_read_only | 43f91d0ea1d631588b76c9646edb8ddba16a771393694d4aa8cda95b2c2e2309 | dfa0f3ad3e7db0c12a6b4ed349f76f722f3e1326133e02f451a28e9c6dd2b39a |
| tests/architecture/test_repository_hygiene_b06.py | test_b01_evidence_stays_tracked_and_historical_freeze_stays_intact | 1d854e51559244b52c3b062bdfbde410653b8fdeff223deead9334eef5d9acfc | 8ceffb8d460a759ec90371e246aef43d346801ca6fc064c8ba2877d439ae51e9 |

Cause commune : HIST-020 désigne le helper
tests/calibration/pedagogical/repair_tranche_v4_2.py. Ses octets actifs ont
évolué avec R2-HISTORY-1, mais les deux guards exigeaient encore le SHA B01
courant d1e5b40dd1437aad38f5da0db4797e2670da953ee554f09f4aa1b1f078e9a6b6.

Le helper de preuve ajouté uniquement dans T11,
r2_historical_entry_sha256, n'accepte que ce chemin précis. Il vérifie :

1. Le blob Git de ce fichier à la référence fixe
   6d0d66380757d7502fd967cd0246c5b6ff91d5f8, hashé réellement et comparé
   au SHA B01/PRE inchangé. Le blob est identique à celui de l'entrée R2 :
   objet Git 4e361d5fd497dbd5050f82293c58d0de270de47c.
2. Le fichier ACTIF contre son hash R2-HISTORY-1 approuvé :
   9b85e5496ed9177bfd11fff896b7bd9bd87b4bf919216c6327172a784cf952d9.
   Les non-régressions AST et de refus d'ancien live restent exécutées.
3. Les 39 autres entrées restent contrôlées sur leurs octets COURANTS.
   Le tooling conserve son ordre de hachage, ses 40 identifiants, son hash
   ordonné et toutes les autres assertions. L'hygiène conserve les preuves
   suivies et l'intégrité du manifeste de freeze.

Le digest historique renvoyé provient des octets réellement lus et validés ;
ce n'est pas une constante attendue retournée sans preuve. Pas de fallback
HEAD ni de bascule de tout le freeze vers l'historique. Aucun fichier Git
historique, aucune ancienne empreinte attendue ni ancien ADR n'a changé.
Le support partagé historical_hash_freeze.py reste inchangé :
95fedd65171033273b68c34ad8b9e50aaf0c6d6da1140ae7b9708b21483b903c.

### Contre-exemples et identité du périmètre

- Absence, corruption, mauvaise référence historique et tentative de
  référence équivalente mais non autorisée : refus.
- Mauvais chemin, fichier actif absent et altération du refus live dans le
  helper actif : refus, même si le blob historique reste intact.
- Altération simulée de CHACUNE des 39 autres entrées, dans CHACUN des deux
  guards : 78 contre-exemples ; aucune source réelle n'est écrite.
- Imports historiques interdits par la frontière tooling : refus sur
  fixtures neuves hors dépôt. Les contrôles d'hygiène existants (fichiers
  forcés dans l'index, DB/sidecars/secrets/temporaires/preuves) restent joués.
- Inventaire : absence, 66e chemin et substitution conservant 65 chemins
  sont refusés dans les états simulés non suivi, indexé et committé.
  Une modification du seul contrat JSON ne peut pas autoriser la substitution.
  L'état réel avant et après commit est aussi comparé à la baseline fixe.
  Le diff de l'INDEX est interrogé séparément : une modification indexée
  masquée par les octets courants et l'indexation de documents protégés sont
  également refusées (trois contre-exemples supplémentaires).
- Les déclarations top-level des deux guards, sauf leur node unique, sont
  identiques par AST. Leurs autres instructions/assertions sont préservées.
  Les 20 SHA PRE et les 45 créations sont contrôlés séparément.

Le premier lancement de ces nouveaux contre-exemples a observé 148 succès et
deux erreurs de fixture : la racine de diagnostic de la fixture d'import
restait celle du dépôt. Seule la fixture T11 a été corrigée pour injecter
sa racine temporaire. Le guard produit est resté intact ; la reprise complète
ciblée ci-dessus réussit. Aucun ignore, skip ou xfail n'a été ajouté.

La première passe globale R2-HISTORY-2 a réussi (5453 passed, 28 skipped,
741.97 s). Pendant la revue finale de l'inventaire, un cas d'index caché par
le worktree a été identifié puis corrigé dans G02/T11 déjà autorisés. Les
204 contrôles ciblés ont réussi (38.00 s). Une nouvelle suite ciblée complète
et une nouvelle globale sont exécutées après ce renforcement ; seules leurs
valeurs finales en tête de rapport sont utilisées pour la gate de commit.

La comparaison au manifeste de travail antérieur confirme qu'AG02, les
adaptations historiques précédentes et le code fonctionnel R2 n'ont pas
changé pendant R2-HISTORY-2. Aucun 66e fichier ni nouvelle source préparatoire.
Les preuves historiques des arrêts restent dans ce rapport ; elles ne sont
pas remplacées par des succès rétroactifs.

## Recette navigateur synthétique

Recette manuelle réellement effectuée sur boucle locale, fixture C13 fraîche
et worker de test explicite : demande pilote, clarification sans année
inventée, précisions synthétiques, confirmation, candidate cinq sections,
lecture exacte et refus OUT_OF_SCOPE de « Modifie le dossier 3 ».
L'interface affiche CANDIDATE — NON VALIDÉE, trois références fournies et
une déclarée utilisée. L'onglet a été fermé et le serveur supervisé s'est arrêté.
Le skill computer-use a servi à l'interaction et à l'inspection visuelle.
Cette preuve n'est ni une génération réelle ni une validation pédagogique.

## Projection F58 et live toujours fermé

LIVE_GENERATION_SCOPE.json contient la projection exacte issue des fixtures
synthétiques C13 et du serializer réellement exercé hors ligne. Le transport
existant a été capturé par un client en mémoire explicitement factice,
sans construction de client SDK, credential, réseau ou transmission.

- Entrée JSON : 2659 octets UTF-8 ; projection sérialisée : 5083 octets.
- Projection SHA-256 : 76caedfd0c8735bf8e6bff13549e0fff0c50ea908b94c0f8fc17c11bfdcea293.
- Profil SHA-256 : c4fbac4a4aa54c65022f942c620431ff72ff876068435dfa854e7550cf869e16.
- Pricing SHA-256 : e4359625a5e0acf7142b35e472e98c5aed113f5af0b4bd4db1bcf5d5a6fac35d.
- Profil proposé : gpt-5.6-terra, LOW, Responses, schéma strict, sortie 4096,
  SDK 90 s, job 120 s, un appel maximum, zéro retry/fallback.
- Modèle/documentation officielle vérifiés le 2026-09-06 :
  [modèle et tarifs](https://developers.openai.com/api/docs/models/gpt-5.6-terra),
  [rétention](https://developers.openai.com/api/docs/guides/your-data),
  [tokens](https://developers.openai.com/api/docs/guides/token-counting),
  [Responses](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

Les tarifs documentaires de 2 USD/MTok en entrée et 12 USD/MTok en sortie,
avec facteur prudent 1,25 sur l'entrée, donnent 0,131072 USD pour
32768/4096 tokens. La borne d'entrée de 32768 tokens n'est PAS démontrée :
la taille en octets ne constitue pas ici une attestation du comptage provider.
Le plafond de 0,140000 USD est uniquement proposé, non approuvé.
Aucun endpoint de comptage ni sonde de disponibilité n'a été appelé.
store=false ne promet pas une rétention nulle.

La factory OpenAI existante est raccordée par injection et testée avec
resolver/transport synthétiques. Sur cette baseline, le mode CLI
--live-authorization refuse AVANT tout stat/read du chemin et l'entrée
worker produit refuse toute génération. Il n'existe pas de mock caché,
ni de chemin live activable par le seul dépôt d'un fichier d'autorisation.

Le live exige encore : preuve de borne d'entrée, source de credential choisie
explicitement sans en exposer la valeur, budget et transfert approuvés,
autorisation one-shot liée au commit livré et activation vérifiée de la
composition live. Ce handoff ciblé et cette activation ne sont pas réalisés
par cette livraison. Les champs d'approbation/source/commit d'exécution
restent null ou false dans F58 ; aucun LIVE_READY n'est revendiqué.
Le commit qui contient ces preuves s'identifie par Git, sans cycle de hash.

## Bilan et arrêt

Appels fournisseur = 0 ; credentials réels inspectés/résolus = 0 ; dépense = 0.
Accès données utilisateur/seed/runtime/sidecars, même métadonnées = 0.
Migration/configuration persistante/nouvelle dépendance/lock/push/merge = 0.
Réseau limité aux pages publiques officielles autorisées et aux tests loopback.
Le commit autorisé est unique et local : 65 fichiers, code et preuves réunis
après succès des validations. Son SHA est livré dans la réponse et vérifiable
par Git ; il n'est pas inclus dans son propre contenu. L'index explicite et
le diff fixe sont vérifiés avant commit, puis les mêmes contrôles sont rejoués
après commit. Les 21 non-suivis protégés/préparatoires demeurent hors index.
Les preuves brutes, sorties synthétiques de test et fichiers SQLite restent hors Git.

R2_SYNTHETIC_WIRING_ONLY ; génération réelle = NOT_RUN.
R2_PRODUCT_COMPLETE n'est pas revendiqué. CAP-R02 est vérifié synthétiquement.
R3/R4/H3 ne sont pas démarrés ; la feuille de route reste inchangée.
