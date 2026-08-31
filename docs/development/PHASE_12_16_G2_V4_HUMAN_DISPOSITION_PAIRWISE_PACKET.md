# Phase 12.16-G2 — Prévalidation humaine disposition et comparaison v4

- Corpus : `12.16-g1-v4`
- Checksum corpus : `9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034`
- REVIEW_STATUS : `NOT_COMPLETED`
- Relecteur ou relectrice :
- Date :
- Version de la grille : `human-disposition-pairwise-v4`
- Exposition préalable :

## Définitions contrôlées

- `DELIVER_AS_IS` : peut être remis à l'utilisateur sans correction préalable.
- `REVISE_BEFORE_DELIVERY` : pédagogiquement exploitable mais doit être corrigé ou amélioré avant livraison.
- `REJECT` : ne doit pas être livré et nécessite une reprise substantielle.
- `NON_EVALUABLE` : le contexte ne permet pas une décision fiable.

## Consignes

1. Examiner les trois candidats de chaque carte dans l'ordre affiché.
2. Cocher exactement une disposition globale par candidat.
3. Pour chaque critère, classer directement les trois IDs avec `>` et `=`.
4. Utiliser chaque ID exactement une fois; exemple syntaxique : `ID-1 > ID-2 = ID-3`.
5. Ne fournir aucun score numérique.
6. Ajouter une seule justification courte par carte.

## V4H-001 — SCN-01

- Niveau : `premiere-stmg`
- Type de tâche : `resource-organization`
- Critères : `scn-01.quality.clarity` ; `scn-01.quality.organization-utility`
- Sections requises : `context, summary`

### Candidat `CAND-68D9F800A9`

- `context` : Une ressource synthétique de management fournit un titre, un thème, une notion, un niveau et un statut de vérification, tous consignés dans une note libre unique.
- `summary` : Conserver cette note telle quelle et retrouver la ressource en parcourant les titres; aucune hiérarchie thème/notion, aucun champ de niveau et aucune règle d'usage du statut ne sont définis.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-CB1E203E44`

- `context` : Une ressource synthétique de management comporte un titre, un thème, une notion, un niveau pédagogique et un statut de vérification.
- `summary` : La classer par thème puis par notion, afficher le titre, le niveau et le statut, puis utiliser ce statut pour retrouver et vérifier rapidement la ressource avant son emploi.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-52DB542C05`

- `context` : Une ressource synthétique de management indique un titre et un thème de classement.
- `summary` : La placer dans une catégorie de management et conserver son titre pour la retrouver.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-01.quality.clarity` (IDs : CAND-68D9F800A9, CAND-CB1E203E44, CAND-52DB542C05) :
- Classement relatif — `scn-01.quality.organization-utility` (IDs : CAND-68D9F800A9, CAND-CB1E203E44, CAND-52DB542C05) :
- Justification pédagogique courte de la carte :

## V4H-002 — SCN-02

- Niveau : `terminale-stmg`
- Type de tâche : `resource-search`
- Critères : `scn-02.quality.relevance` ; `scn-02.quality.coverage`
- Sections requises : `concept, summary`

### Candidat `CAND-24EE7CDAE0`

- `concept` : La recherche porte sur une notion de gestion financière en Terminale STMG et doit faire apparaître une méthode de calcul utilisable.
- `summary` : Filtrer par thème et niveau, conserver les ressources qui expliquent le calcul; un exemple d'application peut compléter la sélection.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-70E7C0A2D8`

- `concept` : La recherche vise des ressources de gestion financière pour Terminale STMG qui définissent la notion, expliquent une méthode de calcul et proposent un exemple d'application synthétique.
- `summary` : Filtrer par niveau, notion et tâche; retenir les ressources couvrant définition, méthode et exemple, puis écarter celles qui sont hors niveau, sans calcul ou seulement thématiques.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-53783DC239`

- `concept` : La recherche utilise un mot-clé général de gestion financière pour repérer des ressources qui mentionnent le sujet.
- `summary` : Conserver les titres liés au thème et les présenter dans une liste, sans autre filtre obligatoire.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-02.quality.relevance` (IDs : CAND-24EE7CDAE0, CAND-70E7C0A2D8, CAND-53783DC239) :
- Classement relatif — `scn-02.quality.coverage` (IDs : CAND-24EE7CDAE0, CAND-70E7C0A2D8, CAND-53783DC239) :
- Justification pédagogique courte de la carte :

## V4H-003 — SCN-03

- Niveau : `premiere-stmg`
- Type de tâche : `course-creation`
- Critères : `scn-03.quality.clarity` ; `scn-03.quality.level-adaptation`
- Sections requises : `objective, concept, example, summary`

### Candidat `CAND-75E3CDC8DD`

- `objective` : Distinguer une finalité économique d'une finalité sociale dans une organisation.
- `concept` : La finalité économique concerne la pérennité et l'allocation des ressources; la finalité sociale concerne les parties prenantes internes.
- `example` : Une organisation synthétique finance son activité et modifie les conditions de ses parties prenantes internes.
- `summary` : Les deux finalités peuvent coexister, sans méthode fournie pour les identifier dans une situation de Première STMG.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-476FA0E631`

- `objective` : Distinguer une finalité économique d'une finalité sociale et expliquer pourquoi elles peuvent être poursuivies ensemble par une organisation.
- `concept` : La finalité économique soutient la pérennité de l'activité et ses ressources; la finalité sociale concerne les conditions de travail et les effets sur les personnes impliquées.
- `example` : Une coopérative synthétique conserve un excédent pour financer son activité et améliore simultanément l'organisation du travail de ses membres.
- `summary` : En Première STMG, on identifie la finalité à partir de ce que l'organisation cherche à maintenir et des personnes auxquelles son action bénéficie.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-71C89D6BAF`

- `objective` : Repérer plusieurs finalités possibles d'une organisation.
- `concept` : Une organisation peut rechercher la continuité de son activité et agir pour les personnes, sans relier explicitement chaque action à une finalité précise.
- `example` : Une structure synthétique vend un service et modifie le travail de son équipe.
- `summary` : Ces actions peuvent répondre à plusieurs finalités, mais aucun critère ne permet ici de les distinguer.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-03.quality.clarity` (IDs : CAND-75E3CDC8DD, CAND-476FA0E631, CAND-71C89D6BAF) :
- Classement relatif — `scn-03.quality.level-adaptation` (IDs : CAND-75E3CDC8DD, CAND-476FA0E631, CAND-71C89D6BAF) :
- Justification pédagogique courte de la carte :

## V4H-004 — SCN-04

- Niveau : `bts-cg-1`
- Type de tâche : `resource-transformation`
- Critères : `scn-04.quality.fidelity` ; `scn-04.quality.level-adaptation`
- Sections requises : `context, concept, example, summary`

### Candidat `CAND-C33E8F2947`

- `context` : Une opération synthétique fournit un montant hors taxe et un taux de TVA, mais la transformation ne conserve que le total toutes taxes comprises à communiquer.
- `concept` : Le TTC comprend le montant hors taxe et une TVA proportionnelle; la relation est correcte, mais aucune formule ni étape ne montre comment obtenir la taxe.
- `example` : Pour 250 unités hors taxe à 20 %, la note annonce correctement 300 unités TTC sans faire apparaître les 50 unités de TVA ni le contrôle 250 plus 50.
- `summary` : Restituer le TTC correct en laissant à l'utilisateur la reconstruction du calcul de TVA, de l'enchaînement des étapes et du contrôle final.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-8F3C315C21`

- `context` : Une opération synthétique indique un montant hors taxe, un taux et un total toutes taxes comprises à annoncer.
- `concept` : Le montant TTC comprend le montant hors taxe et une taxe proportionnelle, sans expliciter la formule ni l'enchaînement des calculs.
- `example` : Un montant hors taxe soumis à une taxe conduit à un total supérieur au montant de départ.
- `summary` : Identifier les données puis annoncer un TTC, sans calcul séparé de TVA, unité guidée ni vérification.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-1253D730AA`

- `context` : Une note synthétique distingue un montant hors taxe, un taux de TVA, la taxe calculée et le montant toutes taxes comprises.
- `concept` : La TVA est le montant hors taxe multiplié par le taux; le TTC est ensuite la somme du hors taxe et de la TVA. Chaque résultat conserve son unité monétaire.
- `example` : Pour 250 unités hors taxe à 20 %, la TVA vaut 50 unités et le TTC 300 unités; la somme 250 plus 50 vérifie le résultat.
- `summary` : Identifier HT et taux, calculer séparément la TVA, additionner pour obtenir le TTC, puis contrôler l'unité et l'égalité finale.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-04.quality.fidelity` (IDs : CAND-C33E8F2947, CAND-8F3C315C21, CAND-1253D730AA) :
- Classement relatif — `scn-04.quality.level-adaptation` (IDs : CAND-C33E8F2947, CAND-8F3C315C21, CAND-1253D730AA) :
- Justification pédagogique courte de la carte :

## V4H-005 — SCN-05

- Niveau : `terminale-stmg`
- Type de tâche : `exercise-creation`
- Critères : `scn-05.quality.difficulty-appropriateness` ; `scn-05.quality.instruction-clarity`
- Sections requises : `context, questions, correction-link`

### Candidat `CAND-9873A63D8B`

- `context` : Une entreprise synthétique hésite entre un investissement de 8 000 unités qui économise 2 000 unités par an et un autre de 9 000 unités qui en économise 3 000.
- `questions` : 1. Calculer la durée de récupération de chaque choix. 2. Indiquer le choix le plus rapide et donner une justification courte.
- `correction-link` : La correction séparée rappelle la division du coût par l'économie annuelle, donne les deux durées et identifie la plus courte.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-01ADA7FABC`

- `context` : Deux investissements synthétiques présentent chacun un coût et une économie annuelle différents.
- `questions` : 1. Effectuer un calcul utile pour chaque proposition. 2. Choisir une proposition et expliquer brièvement la réponse.
- `correction-link` : La correction séparée indique qu'il faut comparer les durées calculées et retenir la plus courte.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-2E26645B8E`

- `context` : Une entreprise synthétique compare deux investissements: 12 000 unités pour 3 000 unités d'économie annuelle et 15 000 unités pour 5 000 unités d'économie annuelle.
- `questions` : 1. Écrire la formule de durée de récupération. 2. Calculer la durée pour chaque investissement. 3. Comparer les deux résultats et justifier le choix le plus rapide en une phrase.
- `correction-link` : La correction séparée attribue une étape à la formule, détaille 12 000 divisé par 3 000 et 15 000 divisé par 5 000, puis relie les résultats de quatre et trois ans au choix justifié.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-05.quality.difficulty-appropriateness` (IDs : CAND-9873A63D8B, CAND-01ADA7FABC, CAND-2E26645B8E) :
- Classement relatif — `scn-05.quality.instruction-clarity` (IDs : CAND-9873A63D8B, CAND-01ADA7FABC, CAND-2E26645B8E) :
- Justification pédagogique courte de la carte :

## V4H-006 — SCN-06

- Niveau : `bts-cg-1`
- Type de tâche : `assessment-creation`
- Critères : `scn-06.quality.assessment-clarity` ; `scn-06.quality.marking-scheme-coherence`
- Sections requises : `instructions, questions, marking-scheme`

### Candidat `CAND-E1AE44C1C9`

- `instructions` : Présenter pour chaque question la formule, le remplacement par les données, le calcul et l'unité du résultat.
- `questions` : 1. Calculer la TVA sur 250 unités hors taxe au taux de 20 %. 2. Déterminer le montant TTC correspondant et vérifier l'addition.
- `marking-scheme` : Question 1: formule 1 point, application 1 point, résultat et unité 1 point. Question 2: formule 1 point, calcul 1 point, résultat, unité et vérification 1 point.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-651CA5C9C3`

- `instructions` : Effectuer les calculs de taxe et donner les résultats.
- `questions` : 1. Trouver la TVA pour un montant hors taxe et un taux fournis. 2. Donner le montant TTC.
- `marking-scheme` : Question 1: 3 points pour une réponse correcte. Question 2: 3 points pour le résultat et sa présentation.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-FA62B7A502`

- `instructions` : Répondre aux deux questions à partir des données fournies, sans forme de calcul, unité ni justification explicitement attendue.
- `questions` : 1. Calculer la TVA sur 200 unités hors taxe à 20 %. 2. Calculer le montant TTC.
- `marking-scheme` : Attribuer 6 points globalement si l'ensemble paraît correct, sans répartition par question, formule, application numérique, résultat ou unité.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-06.quality.assessment-clarity` (IDs : CAND-E1AE44C1C9, CAND-651CA5C9C3, CAND-FA62B7A502) :
- Classement relatif — `scn-06.quality.marking-scheme-coherence` (IDs : CAND-E1AE44C1C9, CAND-651CA5C9C3, CAND-FA62B7A502) :
- Justification pédagogique courte de la carte :

## V4H-007 — SCN-07

- Niveau : `bts-cg-2`
- Type de tâche : `correction-remediation`
- Critères : `scn-07.quality.correction-quality` ; `scn-07.quality.remediation-clarity`
- Sections requises : `context, correction-link, summary`

### Candidat `CAND-4D87CF7DEB`

- `context` : Une production synthétique confond le chiffre d'affaires avec le résultat alors que des produits et des charges sont fournis.
- `correction-link` : Correction: le chiffre d'affaires mesure les ventes; le résultat correspond aux produits diminués des charges. La confusion vient de l'oubli des charges, qui doivent rester dans le calcul.
- `summary` : Remédiation: classer trois montants fictifs en produits ou charges, recalculer le résultat, puis expliquer en une phrase pourquoi il diffère des ventes.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-AA6DC17B18`

- `context` : Une production synthétique assimile les ventes au résultat alors que des produits et des charges sont disponibles.
- `correction-link` : Correction: le résultat tient compte des produits et des charges; corriger l'égalité proposée sans diagnostic de l'oubli ni formule explicitée.
- `summary` : Remédiation: reprendre les montants, proposer un nouveau résultat puis relire la définition, sans étape de classement ni critère de réussite.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-B30EAF29B1`

- `context` : Une production synthétique assimile les ventes au résultat alors que des produits et des charges sont disponibles.
- `correction-link` : Correction: le chiffre d'affaires et le résultat sont deux indicateurs différents, et les charges interviennent dans le résultat, sans diagnostic précis ni relation de calcul explicitée.
- `summary` : Remédiation: relire la définition puis remplacer la phrase erronée, sans classement des montants, recalcul guidé ni critère de réussite.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-07.quality.correction-quality` (IDs : CAND-4D87CF7DEB, CAND-AA6DC17B18, CAND-B30EAF29B1) :
- Classement relatif — `scn-07.quality.remediation-clarity` (IDs : CAND-4D87CF7DEB, CAND-AA6DC17B18, CAND-B30EAF29B1) :
- Justification pédagogique courte de la carte :

## V4H-008 — SCN-08

- Niveau : `bts-cg-2`
- Type de tâche : `qcm-quiz-creation`
- Critères : `scn-08.quality.distractor-quality` ; `scn-08.quality.feedback-quality`
- Sections requises : `question, options, answer-key, feedback`

### Candidat `CAND-2F2B00FF95`

- `question` : Quel calcul exprime la part des charges dans le chiffre d'affaires ?
- `options` : A. Charges divisées par chiffre d'affaires. B. Chiffre d'affaires divisé par charges. C. Charges divisées par résultat. D. Résultat divisé par chiffre d'affaires.
- `answer-key` : A
- `feedback` : A rapporte bien les charges au chiffre d'affaires. B inverse le rapport, C change le dénominateur et D mesure la part du résultat plutôt que celle des charges.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-97895E88E0`

- `question` : Quel calcul exprime la part des charges dans le chiffre d'affaires ?
- `options` : A. Charges divisées par chiffre d'affaires. B. Charges ajoutées au chiffre d'affaires. C. Charges multipliées par chiffre d'affaires. D. Charges diminuées du chiffre d'affaires.
- `answer-key` : A
- `feedback` : A exprime le rapport demandé; les trois autres réponses sont seulement déclarées incorrectes, sans relier chacune à une confusion ni proposer de remédiation.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

### Candidat `CAND-4C31D32120`

- `question` : Quel calcul exprime la part des charges dans le chiffre d'affaires ?
- `options` : A. Charges divisées par chiffre d'affaires. B. Charges ajoutées au chiffre d'affaires. C. Charges multipliées par chiffre d'affaires. D. Chiffre d'affaires diminué des charges.
- `answer-key` : A
- `feedback` : A construit le rapport demandé; les autres propositions sont incorrectes sans explication de la confusion associée.

Disposition :

- [ ] DELIVER_AS_IS
- [ ] REVISE_BEFORE_DELIVERY
- [ ] REJECT
- [ ] NON_EVALUABLE

- Classement relatif — `scn-08.quality.distractor-quality` (IDs : CAND-2F2B00FF95, CAND-97895E88E0, CAND-4C31D32120) :
- Classement relatif — `scn-08.quality.feedback-quality` (IDs : CAND-2F2B00FF95, CAND-97895E88E0, CAND-4C31D32120) :
- Justification pédagogique courte de la carte :

## Synthèse et signatures

- Huit cartes revues : [ ] oui [ ] non
- Vingt-quatre dispositions renseignées : [ ] oui [ ] non
- Seize classements relatifs renseignés : [ ] oui [ ] non
- Avis : [ ] utilisable [ ] révisions requises [ ] inconclusif
- Relecteur ou relectrice :
- Responsable de la calibration :
- Date de clôture :
