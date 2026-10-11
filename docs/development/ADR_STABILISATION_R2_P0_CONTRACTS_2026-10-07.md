# ADR — Stabilisation R2 des consommateurs P0

Entrée : 85caccd778ca148bd061830546b85bcc0f041e85.
Mandat propriétaire : 03_PROMPT_CODEX_STABILISATION_R2.md, SHA-256
3a9175804b1e295288542b6164027ee26ba9138ef04d281e440206a6a111c88b.
Statut : revue technique locale avant implémentation ; revue de PR encore requise.

## AA01 — Applicabilité et preuve de calcul

Le plan 1.1 distingue REQUIRED, NOT_REQUIRED et UNDETERMINED. Une absence de
mot-clé n'est pas une preuve d'inapplicabilité. Les opérations demandées, les
données et expressions de la production, puis les réponses numériques sont
examinées ; les mots-clés restent un signal conservateur supplémentaire.
Un objectif explicitement qualitatif sans signal quantitatif peut justifier
NOT_REQUIRED. Un nombre de contexte (année, durée, identifiant) ne constitue pas
à lui seul une opération. La génération et chaque version modifiée réévaluent
la production ; elles ne conservent aucune preuve de calcul de leur parent.

Le statut public reste ECHEC si un contrôle requis n'est pas exécuté, devient
A_DETERMINER lorsque l'applicabilité est indéterminée, et réserve NON_APPLICABLE
à une justification explicite. Une revue sémantique ne prouve pas un calcul.
Le contrôle CAP-A01 existant peut être projeté uniquement s'il a été exécuté
sur le même bundle, production et version, avec ses contrôles exacts. Le P0
libre sans ce contrôle reste sans preuve ; aucun moteur universel n'est ajouté.

## AA02 — Successeur fermé de rapport

P0-REVIEW-1.0 conserve ses quatorze champs et reste le défaut historique.
P0-REVIEW-1.1 ajoute uniquement uncertainties, obligatoire et borné, sous la
politique NEGATIVE_AUTHORITY_DIAGNOSTICS_V1 déjà adoptée le 5 octobre. Le
consommateur accepte la forme exacte de chaque version ; ni suppression des
réserves, ni clés supplémentaires arbitraires, ni assouplissement du scanner.
La sélection de politique reste explicite dans la composition. Les identités
production/version/hash, le non-rejeu et NOT_PERFORMED restent obligatoires.
Le rapport complet est conservé dans la sauvegarde documentaire existante.

## Revue technique et preuves requises

Les deux corrections restent dans les responsabilités Application, contrats et
adaptateur existantes. Aucun agent n'acquiert une autorité métier, SQL, secret ou
stockage. Aucun provider n'est raccordé implicitement. Les contrats de production
et de sauvegarde ne changent pas ; leurs originaux restent lisibles.
La revue exige les trois contre-exemples exacts et paraphrases, calcul ajouté,
cas qualitatif et nombre de contexte, preuve CAP-A01 réellement exécutée et
substitution refusée. Le service et l'adaptateur doivent être traversés ensemble
avec un double déclaré : historique, réserve vide/non vide, type invalide, clé
inconnue, mauvaise version/hash, puis sauvegarde et réouverture exactes.
Les nouvelles identités entrent dans le successeur de garde R6 et sa couverture
de mutation active. Tests, Ruff, mypy et contrôle du diff précèdent la publication.
Cette revue locale ne remplace aucune revue humaine exigée ni recette enseignante.
