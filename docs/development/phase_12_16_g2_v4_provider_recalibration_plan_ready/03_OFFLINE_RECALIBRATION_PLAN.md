# Phase 12.16-G2-V4 — Plan de remédiation avant live

Ce plan ne constitue ni une modification du runner ni une autorisation d'exécution.

## Ordre des travaux

1. Relier une matrice versionnée aux 24 anchors V4 et à leurs critères, puis recalculer cardinalité, hash et budget.
2. Désigner un snapshot tarifaire unique, daté et sourcé pour les trois modèles ; l'utiliser dans la matrice, le runner, le ledger et les tests.
3. Ajouter une garde d'entrée vérifiant branche/dérivation, corpus V4, formulaire corrigé et clôture corrective avant toute construction de transport.
4. Brancher le canary breaker dans le chemin effectif : aucun fan-out tant que les canaries requis ne sont pas terminaux et valides.
5. Relier les métriques à la baseline humaine V4 immuable et implémenter la comparaison pairwise annoncée.
6. Exécuter un dry-run complet avec fakes : succès, baseline invalide, matrice invalide, pricing incohérent, credentials absents, plafond dépassé, canary échoué, sortie invalide et secret simulé.
7. Produire une nouvelle preuve offline, puis demander séparément l'approbation financière et l'autorisation live propriétaires.

## Protocole de canary futur

Après résolution des cinq bloqueurs et uniquement sous autorisation propriétaire explicite :

1. vérifier la baseline V4, la matrice, le pricing et le plafond ;
2. vérifier la destination locale des sorties et ouvrir volontairement le flag live ;
3. exécuter un canary OpenAI minimal prévu par la nouvelle matrice ;
4. vérifier structure, redaction, usage, coût et écriture atomique ;
5. exécuter un canary Anthropic minimal sur un anchor V4 ;
6. effectuer les mêmes contrôles ;
7. autoriser le fan-out borné seulement si les deux canaries ont réussi.

Au premier échec technique ou de conformité : `FAN_OUT = CANCELLED`, ledger terminal, aucun retry implicite et aucun changement de route runtime.

## Protocole de métriques futur

La référence est la baseline humaine V4 verrouillée : `8/8` strong livrables, `0/8` mixed livrables, `0/8` weak livrables, `16/16` strong > mixed et `16/16` strong > weak.

Le rapport devra mesurer par scénario et critère : accord de disposition, préférence pairwise, séparabilité strong/non-strong, stabilité des répétitions, non-évaluables, erreurs, coûts et provenance par `call_id`. Il ne pourra ni réécrire les labels humains ni adopter un seuil de release.

## Condition de sortie

Les cinq bloqueurs doivent être prouvés fermés. Un nouveau checksum de matrice et un plafond final doivent ensuite recevoir une approbation propriétaire explicite. Aucune autorisation antérieure ne vaut pour cette future matrice.
