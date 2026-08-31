# Prompt de reprise — remédiation offline avant recalibration fournisseur V4

Reprendre depuis le commit de baseline `a3de3a86f5ddd9afea10d71a277854458a7d4b5f` sur la branche `phase12/12-16-provider-model-calibration`.

La clôture corrective V4 est immuable : formulaire `5748b0f223b3039b463f975de8d99772a9f18ad729535a73bd27dfcfc27042a6`, corpus `9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034`, Gate A PASS et Gate B PASS.

Implémenter exclusivement hors ligne la fermeture des bloqueurs suivants :

1. versionner une matrice effectivement reliée aux anchors V4 ;
2. unifier et faire approuver le snapshot pricing et le plafond recalculé ;
3. ajouter une garde de baseline V4 avant construction de tout transport ;
4. intégrer le canary breaker au chemin réel avant fan-out ;
5. relier les métriques et rapports à la baseline humaine V4 et implémenter le pairwise annoncé.

Utiliser uniquement fakes/mocks pour les tests. Ne résoudre aucun credential, ne construire aucun transport réel, n'effectuer aucun appel OpenAI ou Anthropic, ne définir pas `RUN_PEDAGOGICAL_LIVE_CALIBRATION`, ne modifier ni corpus, ni formulaire, ni attestation, ni route runtime. Ne lancer aucune suite globale.

Produire un nouvel audit déterministe, les checksums, les tests ciblés, un protocole de canary, un plafond recalculé et une checklist. Maintenir `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE` tant qu'une autorisation propriétaire distincte ne précise pas la nouvelle matrice, son checksum, le nombre maximal d'appels et le plafond.

Ne pas commit ni pousser sans instruction explicite du propriétaire.
