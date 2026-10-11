# Projet V2 — feuille de route de reprise et de clôture

**Note de mémoire proposée, datée du 27 septembre 2026.** Elle guide la reprise ; les livrables canoniques V2, le code exact et la revue des PR restent les sources d'autorité. Les résultats de tests repris des rapports sont des résultats *rapportés*, non rejoués pour cette note.

## Finalité

Livrer un assistant pédagogique utilisable par un enseignant : rechercher des références identifiées et versionnées, créer, corriger et transformer des cours, exercices, séries de questions et évaluations ; séparer relecture sémantique, validation déterministe et décision pédagogique humaine ; sauvegarder, rouvrir et exporter les versions exactes. La clôture exige un parcours réellement observé dans le navigateur, une livraison reproductible et un procès-verbal de recette enseignant.

## État de référence à ne pas confondre

- Dernier merge GitHub attesté dans l'audit précédent : PR #3 du 19 septembre. Le checkout actuellement ouvert est au commit R5 `5b6f563` du 19 septembre ; son suivi distant n'a pas pu être rafraîchi lors de cette note.
- R6/U1 : commit local déclaré `91db88b0…` ; six couples source/version et sept scénarios P0 rapportés. R7 : lanceur et package de 801 fichiers rapportés. R8-FE : commit local déclaré `c682c439…`, interface P0 à quatre familles ; seule l'évaluation poursuit alors le parcours historique. E0C : commit local déclaré `71131337…`, clôture comparative des guards. Leurs rapports indiquent `push = 0` et `merge = 0`.
- R8-L1 : un mandat propriétaire exact a été consigné, mais la candidate privée de comptage V3 n'est pas adoptée pour le live ; la preuve tarifaire et son admission dans le budget R5 restent à établir. Aucun comptage ou génération R8-L1 réel n'est attesté par les pièces examinées. R8-L2 et la recette finale restent ouverts.
- Les chiffres de dette globale dépendent de la baseline. Ils ne doivent pas être fusionnés en un « global PASS ». Un commit local, un ZIP intègre, un test rapporté, une fonction visible en UI et une recette complète sont cinq preuves distinctes.

## Piste A — réintégrer le code hors ligne, sans attendre le live

**A0. Retrouver la chaîne exacte.** Rafraîchir GitHub et identifier le HEAD de `main`. Retrouver les sources Git R6, R7, R8-FE et E0C, leurs commits, leurs parents, les manifests et les guards. Comparer les deltas au `main` actuel ; conserver les cinq dossiers documentaires non suivis du checkout ouvert. Un rapport ou une archive ne remplace pas le commit source. Si une source manque, signaler précisément ce manque avant de proposer un PR.

**A1. PR R6 — références exactes et contrats P0.** Vérifier les identités ressource/version, la lecture seule CP645, les frontières Application et les statuts des sources. Rejouer les tests applicables dans un environnement conforme, Ruff, mypy, les guards et l'hygiène Git. Documenter les échecs historiques sans les annoncer comme réussites. Soumettre à revue explicite, puis merger seulement le delta approuvé.

**A2. PR R7 — lanceur et package local.** Vérifier le démarrage, l'arrêt, le redémarrage, la réouverture et l'export sur le code intégré. Refaire le contrôle du package exact (manifest, tailles, empreintes, absence de SQLite, `.env`, secrets et données runtime). Soumettre à revue, puis merger.

**A3. PR R8-FE/E0C — interface P0 et guards successeurs.** Intégrer l'interface à quatre familles, la frontière de contexte et la succession exacte des guards sans affaiblir les refus historiques. Conserver l'arrêt explicite des trois familles non-évaluation après le contexte tant que leur génération n'est pas raccordée. Rejouer tests fonctionnels, d'architecture et d'identité sur la baseline intégrée. Si le delta est trop large pour une revue claire, scinder interface et réconciliation des guards en deux PR dépendantes. Faire relire chaque PR avant merge.

Ces PR portent sur du code hors ligne. Un coût de comptage inconnu ou l'absence d'adoption d'un runner privé ne doit pas, à lui seul, bloquer leur proposition à la revue.

## Piste B — cinq jalons de clôture pédagogique

1. **R8-L1 prêt pour décision exécutable.** Conclure la revue ciblée de V3 et de ses limites ; obtenir une preuve écrite du coût de comptage et montrer comment R5 l'admet sous le plafond total. Vérifier le SDK verrouillé, les identités, l'expiration, le non-rejeu et l'adoption de l'exécutable exact. Ne jamais convertir `UNKNOWN` en `KNOWN` sans preuve.
2. **Première création réelle.** Sur le mandat exact encore valide, réaliser au plus le comptage et la génération conditionnelle prévus. Observer la candidate d'évaluation dans la bonne conversation et la bonne version, avec références et trace du routage UI/HTTP → Application → orchestration → AG-02 → AG-03 → fournisseur → candidate. Un résultat injecté manuellement ne démontre pas cette chaîne.
3. **Parcours complet d'évaluation.** Sur la V1 réelle, exercer AG-04 pour la relecture, CAP-A01 pour la validation déterministe, la correction et le barème, puis une modification ciblée par AG-03 sous le mandat R8-L2 approprié. Vérifier version enfant, vues élève/professeur, sauvegarde, export Word, arrêt et réouverture. L'enseignant garde l'arbitrage pédagogique.
4. **P0 complet.** Raccorder cours, exercices et séries de questions au-delà de l'acceptation du contexte, avec les contrats, ports et agents existants. Exercer création et correction représentatives pour les quatre familles et les quatre niveaux, avec sources officielles identifiées et leur statut réel. Ne pas créer un moteur ou un agent par famille sans décision architecturale canonique.
5. **Recette et livraison.** Construire le package final depuis un HEAD Git revu et mergé. Passer les cinq gates R8 (navigateur local, démarrage backend, accès frontend, données locales, recette de bout en bout), recueillir le procès-verbal de l'enseignant, publier notice, checksums, matrice P0 et registre des limites/dettes. Déclarer la Phase 12 close seulement sur ces preuves.

## Mode de travail

Traiter A0 immédiatement ; préparer les PR d'intégration et la preuve tarifaire en parallèle. Regrouper dans chaque PR un objectif, ses contrats, ses consommateurs et ses tests, puis corriger dans ce même lot les défauts démontrés. Éviter une nouvelle série de micro-handoffs ou un audit général sans question précise. Les frontières des Phases 6 et 11, l'absence d'héritage implicite V1, les règles d'AGENTS.md et la séparation génération/validation/qualité/promotion restent applicables. Cette note ne vaut ni revue de PR, ni adoption live, ni autorisation supplémentaire.
