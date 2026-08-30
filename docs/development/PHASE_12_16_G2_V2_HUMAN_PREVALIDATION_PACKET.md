# Phase 12.16-G2 — Paquet aveugle de prévalidation humaine du corpus v2

- Corpus : `12.16-g1-v2`
- Checksum corpus : `4fe17f4286eb1a713a3d41a95b99260ef470ba32cadf33c2267dfc4dbaada427`
- REVIEW_STATUS : `NOT_COMPLETED`
- Relecteur ou relectrice :
- Date :
- Version de la grille : `human-prevalidation-v2`
- Exposition préalable aux résultats machine :

## Gate pré-déclarée

- 24/24 contenus structurellement valides.
- 16/16 ordres faibles, 0 inversion et 0 relation non évaluable.
- Les trois qualités doivent être perceptiblement différenciées pour chacun des 16 critères.
- Objectif de conception : 16/16 ordres humains stricts.
- Toute égalité restante exige une disposition explicite avant une évaluation fournisseur.
- Cette gate ne crée aucun seuil de release produit.

## Consignes

1. Examiner chaque contenu sans consulter la clé locale ni les rapports machine.
2. Évaluer séparément la structure et les deux critères indiqués.
3. Utiliser exactement un libellé contrôlé par appréciation.
4. Ne pas corriger le contenu dans ce fichier.
5. Déclarer honnêtement toute exposition préalable.

Libellés : `TRES_SATISFAISANT`, `SATISFAISANT`, `FRAGILE`, `INSUFFISANT`, `NON_EVALUABLE`.

## HPV2-001

- Scénario : `SCN-02`
- Niveau : `terminale-stmg`
- Type de tâche : `resource-search`
- Critères : `scn-02.quality.relevance` ; `scn-02.quality.coverage`
- Sections requises : `concept, summary`
- Contenu synthétique :

  - `concept` : La recherche vise des ressources de gestion financière pour Terminale STMG qui définissent la notion, expliquent une méthode de calcul et proposent un exemple d'application synthétique.
  - `summary` : Filtrer par niveau, notion et tâche; retenir les ressources couvrant définition, méthode et exemple, puis écarter celles qui sont hors niveau, sans calcul ou seulement thématiques.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-02.quality.relevance` :
- Appréciation humaine — `scn-02.quality.coverage` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-002

- Scénario : `SCN-03`
- Niveau : `premiere-stmg`
- Type de tâche : `course-creation`
- Critères : `scn-03.quality.clarity` ; `scn-03.quality.level-adaptation`
- Sections requises : `objective, concept, example, summary`
- Contenu synthétique :

  - `objective` : Repérer deux objectifs possibles d'une organisation.
  - `concept` : Une organisation recherche des résultats pour son activité et peut aussi agir pour les personnes.
  - `example` : Une structure synthétique vend un service et propose une action pour son équipe.
  - `summary` : Les organisations peuvent avoir plusieurs finalités.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-03.quality.clarity` :
- Appréciation humaine — `scn-03.quality.level-adaptation` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-003

- Scénario : `SCN-08`
- Niveau : `bts-cg-2`
- Type de tâche : `qcm-quiz-creation`
- Critères : `scn-08.quality.distractor-quality` ; `scn-08.quality.feedback-quality`
- Sections requises : `question, options, answer-key, feedback`
- Contenu synthétique :

  - `question` : Quel calcul exprime la part des charges dans le chiffre d'affaires ?
  - `options` : A. Charges divisées par chiffre d'affaires. B. Chiffre d'affaires divisé par charges. C. Charges divisées par résultat. D. Résultat divisé par chiffre d'affaires.
  - `answer-key` : A
  - `feedback` : A rapporte bien les charges au chiffre d'affaires. B inverse le rapport, C change le dénominateur et D mesure la part du résultat plutôt que celle des charges.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-08.quality.distractor-quality` :
- Appréciation humaine — `scn-08.quality.feedback-quality` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-004

- Scénario : `SCN-05`
- Niveau : `terminale-stmg`
- Type de tâche : `exercise-creation`
- Critères : `scn-05.quality.difficulty-appropriateness` ; `scn-05.quality.instruction-clarity`
- Sections requises : `context, questions, correction-link`
- Contenu synthétique :

  - `context` : Une entreprise synthétique hésite entre un investissement de 8 000 unités qui économise 2 000 unités par an et un autre de 9 000 unités qui en économise 3 000.
  - `questions` : 1. Calculer la durée de récupération de chaque choix. 2. Indiquer le choix le plus rapide et donner une justification courte.
  - `correction-link` : La correction séparée rappelle la division du coût par l'économie annuelle, donne les deux durées et identifie la plus courte.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-05.quality.difficulty-appropriateness` :
- Appréciation humaine — `scn-05.quality.instruction-clarity` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-005

- Scénario : `SCN-03`
- Niveau : `premiere-stmg`
- Type de tâche : `course-creation`
- Critères : `scn-03.quality.clarity` ; `scn-03.quality.level-adaptation`
- Sections requises : `objective, concept, example, summary`
- Contenu synthétique :

  - `objective` : Distinguer une finalité économique d'une finalité sociale et expliquer pourquoi elles peuvent être poursuivies ensemble par une organisation.
  - `concept` : La finalité économique soutient la pérennité de l'activité et ses ressources; la finalité sociale concerne les conditions de travail et les effets sur les personnes impliquées.
  - `example` : Une coopérative synthétique conserve un excédent pour financer son activité et améliore simultanément l'organisation du travail de ses membres.
  - `summary` : En Première STMG, on identifie la finalité à partir de ce que l'organisation cherche à maintenir et des personnes auxquelles son action bénéficie.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-03.quality.clarity` :
- Appréciation humaine — `scn-03.quality.level-adaptation` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-006

- Scénario : `SCN-07`
- Niveau : `bts-cg-2`
- Type de tâche : `correction-remediation`
- Critères : `scn-07.quality.correction-quality` ; `scn-07.quality.remediation-clarity`
- Sections requises : `context, correction-link, summary`
- Contenu synthétique :

  - `context` : Une production synthétique assimile les ventes au résultat malgré la présence d'un montant de charges.
  - `correction-link` : Correction: le résultat ne se limite pas aux ventes; il faut soustraire les charges des produits.
  - `summary` : Remédiation: reprendre un exemple simple avec un montant de produits et un montant de charges, puis comparer le résultat aux ventes.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-07.quality.correction-quality` :
- Appréciation humaine — `scn-07.quality.remediation-clarity` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-007

- Scénario : `SCN-08`
- Niveau : `bts-cg-2`
- Type de tâche : `qcm-quiz-creation`
- Critères : `scn-08.quality.distractor-quality` ; `scn-08.quality.feedback-quality`
- Sections requises : `question, options, answer-key, feedback`
- Contenu synthétique :

  - `question` : Comment calculer le poids des charges dans les ventes ?
  - `options` : A. Ventes divisées par charges. B. Charges moins ventes. C. Charges divisées par ventes. D. Charges plus ventes.
  - `answer-key` : C
  - `feedback` : C construit la proportion demandée en rapportant les charges aux ventes; A inverse les deux grandeurs.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-08.quality.distractor-quality` :
- Appréciation humaine — `scn-08.quality.feedback-quality` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-008

- Scénario : `SCN-04`
- Niveau : `bts-cg-1`
- Type de tâche : `resource-transformation`
- Critères : `scn-04.quality.fidelity` ; `scn-04.quality.level-adaptation`
- Sections requises : `context, concept, example, summary`
- Contenu synthétique :

  - `context` : Une opération synthétique fournit un montant hors taxe et un taux de TVA afin de déterminer le total toutes taxes comprises.
  - `concept` : Calculer la TVA sur le hors taxe, puis l'ajouter au montant initial pour obtenir le TTC.
  - `example` : Pour 100 unités hors taxe à 20 %, le total TTC est de 120 unités.
  - `summary` : Appliquer le taux au hors taxe et ajouter la taxe; présenter le résultat avec son unité.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-04.quality.fidelity` :
- Appréciation humaine — `scn-04.quality.level-adaptation` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-009

- Scénario : `SCN-01`
- Niveau : `premiere-stmg`
- Type de tâche : `resource-organization`
- Critères : `scn-01.quality.clarity` ; `scn-01.quality.organization-utility`
- Sections requises : `context, summary`
- Contenu synthétique :

  - `context` : Une ressource synthétique de management comporte un titre, un thème, une notion, un niveau pédagogique et un statut de vérification.
  - `summary` : La classer par thème puis par notion, afficher le titre, le niveau et le statut, puis utiliser ce statut pour retrouver et vérifier rapidement la ressource avant son emploi.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-01.quality.clarity` :
- Appréciation humaine — `scn-01.quality.organization-utility` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-010

- Scénario : `SCN-07`
- Niveau : `bts-cg-2`
- Type de tâche : `correction-remediation`
- Critères : `scn-07.quality.correction-quality` ; `scn-07.quality.remediation-clarity`
- Sections requises : `context, correction-link, summary`
- Contenu synthétique :

  - `context` : Une production synthétique confond le chiffre d'affaires avec le résultat alors que des produits et des charges sont fournis.
  - `correction-link` : Correction: le chiffre d'affaires mesure les ventes; le résultat correspond aux produits diminués des charges. La confusion vient de l'oubli des charges, qui doivent rester dans le calcul.
  - `summary` : Remédiation: classer trois montants fictifs en produits ou charges, recalculer le résultat, puis expliquer en une phrase pourquoi il diffère des ventes.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-07.quality.correction-quality` :
- Appréciation humaine — `scn-07.quality.remediation-clarity` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-011

- Scénario : `SCN-06`
- Niveau : `bts-cg-1`
- Type de tâche : `assessment-creation`
- Critères : `scn-06.quality.assessment-clarity` ; `scn-06.quality.marking-scheme-coherence`
- Sections requises : `instructions, questions, marking-scheme`
- Contenu synthétique :

  - `instructions` : Présenter pour chaque question la formule, le remplacement par les données, le calcul et l'unité du résultat.
  - `questions` : 1. Calculer la TVA sur 250 unités hors taxe au taux de 20 %. 2. Déterminer le montant TTC correspondant et vérifier l'addition.
  - `marking-scheme` : Question 1: formule 1 point, application 1 point, résultat et unité 1 point. Question 2: formule 1 point, calcul 1 point, résultat, unité et vérification 1 point.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-06.quality.assessment-clarity` :
- Appréciation humaine — `scn-06.quality.marking-scheme-coherence` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-012

- Scénario : `SCN-07`
- Niveau : `bts-cg-2`
- Type de tâche : `correction-remediation`
- Critères : `scn-07.quality.correction-quality` ; `scn-07.quality.remediation-clarity`
- Sections requises : `context, correction-link, summary`
- Contenu synthétique :

  - `context` : Une production synthétique contient une confusion entre les ventes et le résultat.
  - `correction-link` : Correction: le résultat doit aussi tenir compte des charges et ne correspond pas aux seules ventes.
  - `summary` : Remédiation: revoir la définition du résultat et reprendre le calcul présenté.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-07.quality.correction-quality` :
- Appréciation humaine — `scn-07.quality.remediation-clarity` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-013

- Scénario : `SCN-04`
- Niveau : `bts-cg-1`
- Type de tâche : `resource-transformation`
- Critères : `scn-04.quality.fidelity` ; `scn-04.quality.level-adaptation`
- Sections requises : `context, concept, example, summary`
- Contenu synthétique :

  - `context` : Une opération synthétique comporte un montant hors taxe, un taux et un total à déterminer.
  - `concept` : La taxe se calcule sur le montant hors taxe puis s'ajoute au montant de départ.
  - `example` : Avec les valeurs fournies, appliquer le taux puis additionner la taxe obtenue.
  - `summary` : Calculer la taxe et l'ajouter pour obtenir le total.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-04.quality.fidelity` :
- Appréciation humaine — `scn-04.quality.level-adaptation` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-014

- Scénario : `SCN-08`
- Niveau : `bts-cg-2`
- Type de tâche : `qcm-quiz-creation`
- Critères : `scn-08.quality.distractor-quality` ; `scn-08.quality.feedback-quality`
- Sections requises : `question, options, answer-key, feedback`
- Contenu synthétique :

  - `question` : Quelle opération compare les charges au chiffre d'affaires ?
  - `options` : A. Ajouter les deux montants. B. Diviser les charges par le chiffre d'affaires. C. Garder les charges seules. D. Soustraire un du chiffre d'affaires.
  - `answer-key` : B
  - `feedback` : B effectue la comparaison demandée entre les deux grandeurs.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-08.quality.distractor-quality` :
- Appréciation humaine — `scn-08.quality.feedback-quality` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-015

- Scénario : `SCN-01`
- Niveau : `premiere-stmg`
- Type de tâche : `resource-organization`
- Critères : `scn-01.quality.clarity` ; `scn-01.quality.organization-utility`
- Sections requises : `context, summary`
- Contenu synthétique :

  - `context` : Une ressource synthétique de management fournit un titre, un thème, une notion et un statut de contrôle.
  - `summary` : La ranger par thème, conserver le titre et la notion, puis afficher le statut pour permettre un contrôle ultérieur.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-01.quality.clarity` :
- Appréciation humaine — `scn-01.quality.organization-utility` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-016

- Scénario : `SCN-03`
- Niveau : `premiere-stmg`
- Type de tâche : `course-creation`
- Critères : `scn-03.quality.clarity` ; `scn-03.quality.level-adaptation`
- Sections requises : `objective, concept, example, summary`
- Contenu synthétique :

  - `objective` : Reconnaître une finalité économique et une finalité sociale dans une situation simple d'organisation.
  - `concept` : La finalité économique concerne la continuité de l'activité; la finalité sociale concerne les personnes et leurs conditions de travail.
  - `example` : Une entreprise synthétique vend ses produits tout en améliorant un aménagement de travail pour son équipe.
  - `summary` : Une organisation peut poursuivre ces deux finalités dans une même situation.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-03.quality.clarity` :
- Appréciation humaine — `scn-03.quality.level-adaptation` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-017

- Scénario : `SCN-02`
- Niveau : `terminale-stmg`
- Type de tâche : `resource-search`
- Critères : `scn-02.quality.relevance` ; `scn-02.quality.coverage`
- Sections requises : `concept, summary`
- Contenu synthétique :

  - `concept` : La recherche utilise un mot-clé général de gestion financière pour repérer des ressources qui mentionnent le sujet.
  - `summary` : Conserver les titres liés au thème et les présenter dans une liste, sans autre filtre obligatoire.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-02.quality.relevance` :
- Appréciation humaine — `scn-02.quality.coverage` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-018

- Scénario : `SCN-06`
- Niveau : `bts-cg-1`
- Type de tâche : `assessment-creation`
- Critères : `scn-06.quality.assessment-clarity` ; `scn-06.quality.marking-scheme-coherence`
- Sections requises : `instructions, questions, marking-scheme`
- Contenu synthétique :

  - `instructions` : Effectuer les calculs de taxe et donner les résultats.
  - `questions` : 1. Trouver la TVA pour un montant hors taxe et un taux fournis. 2. Donner le montant TTC.
  - `marking-scheme` : Question 1: 3 points pour une réponse correcte. Question 2: 3 points pour le résultat et sa présentation.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-06.quality.assessment-clarity` :
- Appréciation humaine — `scn-06.quality.marking-scheme-coherence` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-019

- Scénario : `SCN-04`
- Niveau : `bts-cg-1`
- Type de tâche : `resource-transformation`
- Critères : `scn-04.quality.fidelity` ; `scn-04.quality.level-adaptation`
- Sections requises : `context, concept, example, summary`
- Contenu synthétique :

  - `context` : Une note synthétique distingue un montant hors taxe, un taux de TVA, la taxe calculée et le montant toutes taxes comprises.
  - `concept` : La TVA est le montant hors taxe multiplié par le taux; le TTC est ensuite la somme du hors taxe et de la TVA. Chaque résultat conserve son unité monétaire.
  - `example` : Pour 250 unités hors taxe à 20 %, la TVA vaut 50 unités et le TTC 300 unités; la somme 250 plus 50 vérifie le résultat.
  - `summary` : Identifier HT et taux, calculer séparément la TVA, additionner pour obtenir le TTC, puis contrôler l'unité et l'égalité finale.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-04.quality.fidelity` :
- Appréciation humaine — `scn-04.quality.level-adaptation` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-020

- Scénario : `SCN-06`
- Niveau : `bts-cg-1`
- Type de tâche : `assessment-creation`
- Critères : `scn-06.quality.assessment-clarity` ; `scn-06.quality.marking-scheme-coherence`
- Sections requises : `instructions, questions, marking-scheme`
- Contenu synthétique :

  - `instructions` : Présenter les deux calculs demandés et écrire l'unité de chaque résultat.
  - `questions` : 1. Calculer la TVA sur 200 unités hors taxe à 20 %. 2. Calculer le montant TTC.
  - `marking-scheme` : Question 1: formule 1 point et calcul avec unité 2 points. Question 2: calcul 2 points et résultat avec unité 1 point.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-06.quality.assessment-clarity` :
- Appréciation humaine — `scn-06.quality.marking-scheme-coherence` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-021

- Scénario : `SCN-01`
- Niveau : `premiere-stmg`
- Type de tâche : `resource-organization`
- Critères : `scn-01.quality.clarity` ; `scn-01.quality.organization-utility`
- Sections requises : `context, summary`
- Contenu synthétique :

  - `context` : Une ressource synthétique de management indique un titre et un thème de classement.
  - `summary` : La placer dans une catégorie de management et conserver son titre pour la retrouver.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-01.quality.clarity` :
- Appréciation humaine — `scn-01.quality.organization-utility` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-022

- Scénario : `SCN-05`
- Niveau : `terminale-stmg`
- Type de tâche : `exercise-creation`
- Critères : `scn-05.quality.difficulty-appropriateness` ; `scn-05.quality.instruction-clarity`
- Sections requises : `context, questions, correction-link`
- Contenu synthétique :

  - `context` : Deux investissements synthétiques présentent chacun un coût et une économie annuelle différents.
  - `questions` : 1. Effectuer un calcul utile pour chaque proposition. 2. Choisir une proposition et expliquer brièvement la réponse.
  - `correction-link` : La correction séparée indique qu'il faut comparer les durées calculées et retenir la plus courte.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-05.quality.difficulty-appropriateness` :
- Appréciation humaine — `scn-05.quality.instruction-clarity` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-023

- Scénario : `SCN-02`
- Niveau : `terminale-stmg`
- Type de tâche : `resource-search`
- Critères : `scn-02.quality.relevance` ; `scn-02.quality.coverage`
- Sections requises : `concept, summary`
- Contenu synthétique :

  - `concept` : La recherche porte sur une notion de gestion financière en Terminale STMG et doit faire apparaître une méthode de calcul utilisable.
  - `summary` : Filtrer par thème et niveau, conserver les ressources qui expliquent le calcul; un exemple d'application peut compléter la sélection.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-02.quality.relevance` :
- Appréciation humaine — `scn-02.quality.coverage` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## HPV2-024

- Scénario : `SCN-05`
- Niveau : `terminale-stmg`
- Type de tâche : `exercise-creation`
- Critères : `scn-05.quality.difficulty-appropriateness` ; `scn-05.quality.instruction-clarity`
- Sections requises : `context, questions, correction-link`
- Contenu synthétique :

  - `context` : Une entreprise synthétique compare deux investissements: 12 000 unités pour 3 000 unités d'économie annuelle et 15 000 unités pour 5 000 unités d'économie annuelle.
  - `questions` : 1. Écrire la formule de durée de récupération. 2. Calculer la durée pour chaque investissement. 3. Comparer les deux résultats et justifier le choix le plus rapide en une phrase.
  - `correction-link` : La correction séparée attribue une étape à la formule, détaille 12 000 divisé par 3 000 et 15 000 divisé par 5 000, puis relie les résultats de quatre et trois ans au choix justifié.

- Structure valide : [ ] oui [ ] non
- Appréciation humaine — `scn-05.quality.difficulty-appropriateness` :
- Appréciation humaine — `scn-05.quality.instruction-clarity` :
- Ambiguïté ou manque de contexte :
- Justification pédagogique courte :
- Action demandée : [ ] aucune [ ] révision [ ] exclusion

## Synthèse et signatures

- Vingt-quatre items revus : [ ] oui [ ] non
- Limites de la revue :
- Avis : [ ] utilisable [ ] révisions requises [ ] inconclusif
- Relecteur ou relectrice :
- Responsable de la calibration :
- Date de clôture :
