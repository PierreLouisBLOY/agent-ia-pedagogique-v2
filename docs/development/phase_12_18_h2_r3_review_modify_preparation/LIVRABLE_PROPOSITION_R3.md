# Livraison — Proposition R3 vérification / modification ciblée

R3_PROPOSAL = COMPLETE (préparation documentaire uniquement).
Date de préparation : 2026-09-06.
Baseline inchangée : `817ad474d93c78c602a22bd30cf77fe7621e68b1`.
Scope proposé : H2_CONVERSATIONAL_REVIEW_MODIFY_V1.
Contrat proposé : REVIEW-MODIFY-HTTP-LOCAL-1.0.
IMPL_AUTHORIZATION = PENDING_OWNER_REVIEW.
R3_IMPLEMENTATION = NOT_STARTED ; R3_LIVE = NOT_RUN.

## Résultat livré

Les six pièces du mandat sont réunies dans ce dossier et son ZIP externe :

1. 01_CONTRAT_R3_REVIEW_VALIDATION_MODIFICATION.md — contrats et limites.
2. 02_INVENTAIRE_FICHIERS_GUARDS_R3.json — chemins exacts, pré-hashes, guards, checks.
3. 03_DECISION_ET_PLAN_EXECUTION_R3.md — permissions distinctes et réalisation.
4. 04_SCENARIO_ACCEPTATION_R3.md — pilote et 30 obligations de tests futurs.
5. LIVRABLE_PROPOSITION_R3.md — présent bilan.
6. MANIFEST_SHA256.txt — SHA des cinq pièces précédentes, sans auto-référence.

Le SHA du manifeste et celui du ZIP sont calculés APRÈS création et livrés dans
le message final externe. Ils ne sont pas insérés dans un fichier qu'ils hachent,
ce qui créerait une auto-référence impossible.

## Comptes exacts du futur lot

| Mesure | Nombre |
|---|---:|
| Composants existants réutilisés (8 EXISTS + 4 PARTIAL) | 12 |
| Nouveaux composants proposés | 8 |
| Fichiers de réalisation | 59 |
| CREATE / MODIFY | 44 / 15 |
| Guards à modifier / nouveaux | 6 / 2 |
| Total guards dans le lot | 8 |
| Routes nouvelles / conservées / registre final | 7 / 9 / 16 |
| Assets frontend, inchangés en nombre | 3 |
| Checks déterministes CAP-A01 | 16 |
| Types d'étapes pouvant nécessiter provider | 3 |
| Nouveaux fichiers de tests exécutables proposés | 13 |
| Obligations de non-régression planifiées | 30 |
| Pièces de préparation créées maintenant | 6 |

Les trois étapes provider sont préparation des suppléments, review, modification.
Elles ne sont NI trois appels autorisés NI un budget approuvé. Une nouvelle V1
réelle serait un prérequis live distinct, car l'ancienne candidate R2 n'existe plus.

## Écarts et décisions rendus explicites

1. CAP-A01 est déclaré mais les règles métier du pilote ne sont pas implémentées.
   Proposition : M09, seize contrôles purs avec raisons PASS/FAIL/WARNING.
2. R2 possède un sujet cinq sections, pas un bundle sujet/correction/barème typé.
   Proposition : artefact auxiliaire V1 immutable, matérialisé une fois explicitement ;
   aucune mutation du sujet. V2 contient tous les éléments publiés atomiquement.
3. Les guards actifs figent encore l'état R2 : ils doivent évoluer sur six fichiers
   exactement, sans modifier les manifests historiques ni les guards de calibration/
   hygiène non impactés. Le contrôle historique et le contrôle courant sont distincts.
4. Les mappings OpenAI R2 restent gelés : le pont nouveau réutilise une section
   JSON textuelle du format générique, avec validation locale stricte. Pas de promesse
   de schéma interne R3 imposé par le provider ni de compatibilité live déjà testée.
5. Le grant et la candidate R2 ne sont pas disponibles pour une reprise live :
   grant CONSUMED, contenu perdu à l'arrêt. Leur hash historique n'est pas un texte.
6. « Plus difficile » ne se réduit pas à un score automatique : le test contrôle
   le delta et les calculs ; l'appréciation pédagogique est une review/humaine distincte.
7. Le produit restera CANDIDATE — NON VALIDÉE dans R3, même avec CAP-A01 PASS.
   Aucun CAP-A02, export, R4, H3 ou calibration intercalé.

Ces écarts sont traités dans la proposition soumise, pas corrigés dans le code
aujourd'hui. Ils ne sont pas dissimulés derrière R3_PRODUCT_COMPLETE.

## Preuves documentaires de cette intervention

- Source ZIP lue entièrement, ses sept entrées inventoriées ; les six payloads
  concordent avec son manifeste.
- Source ZIP SHA :
  `c773d127371ae2ad17f4fd78902273a19a4dc268aa900fa5c28c0ef9a44bcac2`.
- Source manifest SHA :
  `6f88e1032f7e26b6e616bd9eb76b6fc7b1ecd7156426391d069f23ff33c27982`.
- HEAD relu exact ; pas de diff suivi ni de staging.
- Rapport R2 relu, SHA vérifié :
  `c207cc9bff53a9b090f6321b89bdc48e6b42b1edd8e35f7a710c2ca70d200150`.
- Reçu R2 consommé, SHA vérifié :
  `4a64c0c07b07d3180e41fd64e90e7ab821c2e1e02af4b02792121e6125487f17`.
- Rapport : R2_LIVE_GENERATION=PASS, R2_PRODUCT_PROOF=OBTAINED,
  LIVE_AUTHORIZATION=CONSUMED ; aucune réexécution.
- Candidate SHA rapporté :
  `6003b6f55258c47d77efab2c864138b91afc715dec82ad94f8b637c691bfc7dc`.
  Contenu non relu et non reconstruit.
- 15 pré-SHA recalculés ; 44 cibles CREATE absentes ; 59 chemins uniques.
- 37 dépendances/documents actifs lus ou identifiés comme préservés et hachés ;
  21 anciens préparatoires inchangés. Leurs chemins/hashes sont dans 02.
- Vérification documentaire JSON/comptes/empreintes exécutée, sans importer ou
  exécuter le code applicatif. Les fixtures SQL n'ont pas été ouvertes.
- Aucune donnée runtime brute ni secret dans le paquet ; aucune copie des sorties
  générées, du runner/grant, de base SQLite ou de fichier utilisateur.

## Permissions à décider

P_R3_IMPL : en attente, pour le seul lot59 et ses gardes/tests/commit.
P_R3_DOC_NETWORK : en attente si préparation live ultérieure ; inutile pour les doubles.
P_R3_LIVE_REVIEW, P_R3_LIVE_MODIFY, P_R3_LIVE_PREPARE_SUPPLEMENTS : non autorisés.
Leurs scopes, modèle, projection, tokens, tarif et plafond doivent être liés à une
future baseline. Aucun modèle, budget ou signature propriétaire prérempli.
La seule exclusion synthétique proposée doit être réapprouvée pour R3 ;
gate seed réelle toujours NOT_RUN / NOT_PASS.

## Activité réellement effectuée et arrêt

CODE_CHANGES = 0
TECHNICAL_TESTS = 0
PROVIDER_CALLS = 0
CREDENTIAL_RESOLUTION = 0
USER_DATA_OR_METADATA_ACCESS = 0
SQLITE_OPENS = 0
EXTERNAL_NETWORK = 0
GIT_TRACKED_DIFF = 0
GIT_STAGING = 0
GIT_COMMITS = 0

Six nouveaux documents non suivis sont la seule écriture dans le dépôt.
Le ZIP est hors dépôt. « Git changes=0 » signifie ici code suivi/index/commit
inchangés, pas absence de nouveaux documents de préparation.
R3_SYNTHETIC_TESTS = NOT_RUN ; REAL_SEED_GATE = NOT_RUN / NOT_PASS.
R3_PRODUCT_COMPLETE = NOT_ESTABLISHED.
NEXT_ACTION = OWNER_REVIEW_OF_THIS_SINGLE_PACKET.
STOP_BEFORE_IMPLEMENTATION_LIVE_R4_H3 = TRUE.
