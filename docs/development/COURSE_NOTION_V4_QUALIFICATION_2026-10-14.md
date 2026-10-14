# COURSE riche — raccordement versionné V4

Même LU-PRODUIT-01, 14 octobre 2026. Développement local dans une branche isolée ; aucune activation dans la copie fournisseur adoptée.

## Revue préalable

La proposition initiale de l'ADR `ADR_COURSE_NOTION_BINDING_V4_2026-10-14.md`, SHA-256 `7ae4b62c206e3216ce7062d4f6f4a094fe2fa816ddba2246bfc18f2a3e22477f`, a reçu avant implementation un avis distinct FAVORABLE_LIMITED de `/root/p1_preparation_review`. Ses octets exacts sont conservés dans le dossier technique ; seul le blanc terminal de cette copie Git a ensuite été retiré pour le contrôle de diff. Reçu technique externe SHA-256 `0a12c4114cc4a45072c483bbe150293050a819eae57d9ab946a25f172465afc1`. Cet avis préalable ne qualifie pas le code ou le package successeur.

## Raccordement

Une nouvelle demande CHAPTER utilise contexte COURSE4, contenu riche2, chapitre LINEAGE4 et production COURSE3. Les thèmes libres restent distincts des notions sélectionnées. Les alias N sont dérivés de la résolution exacte d'Application, en ordre de sélection ; aucune inférence ou autorité n'est créée. Le binder remplace seulement l'alias par son libellé canonique. Les textes pédagogiques sont livrés intégralement par le fournisseur.

Les validators contrôlent également la méthode, les liens, la couverture unique des questions, leur ordre, la séparation professeur, le numéro local et la cohérence des contrats. Edition locale, conservation, réouverture et export consomment le même chapitre lié. La nouvelle paire locale conserve la borne de 32 versions ; les imports et autres anciennes familles gardent leurs limites. Les anciennes demandes, schémas et règles V3 restent applicables à leurs versions.

## Contrôles réellement exécutés

- Première sélection : 117 PASS, zéro FAIL/ERROR/SKIP ; nouveaux contrats et quatre parcours Application/HTTP synthétiques, refus V3 et wire historiques, livraison et lignée historique.
- Consommateurs et frontières : 218 PASS, zéro FAIL/ERROR/SKIP ; sélection comprenant certains node_ids du premier contrôle. Les deux nombres ne sont pas additionnés comme un nombre de tests distincts.
- Dernier refus ajouté (numéro de chapitre) et quatre parcours Application/HTTP : 5 PASS, zéro FAIL/ERROR/SKIP, résultat complémentaire.
- Ruff conforme après correction des imports ; le premier contrôle Ruff en erreur reste dans le dossier technique.
- Mypy : aucun problème sur 923 fichiers backend ; compilation backend réussie.
- Syntaxe JavaScript et exécution pure du constructeur de contexte UI sur fixtures DOM synthétiques : CHAPTER4, EXPLAINED3 et refus de numéro invalide vérifiés. Ce contrôle n'est pas une inspection visuelle du navigateur.

Fixtures synthétiques uniquement pour ces contrôles. Aucun appel fournisseur réel, ancienne réponse pédagogique, base originale, ledger P1 ou pièce privée ne constitue une fixture. Aucun global n'est relancé. Les reçus exacts et la revue distincte du successeur restent externes au dépôt.

## Limites

L'ancienne tentative riche reste PARSING_REJECTED et non qualifiée. Le correctif ne récupère pas ses octets ni son grant et ne réécrit aucun résultat historique. La continuité P1 est bloquée jusqu'à une disposition exacte distincte ; les réservations pessimistes restent conservées. Aucun nouveau corps n'est couvert implicitement par un accord antérieur.

Un nouveau rattachement source/package/schéma/corps, une qualification réelle bornée et ses consentements frais restent nécessaires. M02 exige sa transition Application et sa cible distincte ; les choix locaux et admissions acquis ne sont pas remis en question. Word technique des nouveaux exports reste à réaliser. Recette enseignante : exclusivement dernière étape, non réalisée et non signée. Aucun merge, déploiement ou release.
