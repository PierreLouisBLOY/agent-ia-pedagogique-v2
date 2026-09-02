# Phase 12.17.2 — Plan de remédiation sans exécution

## Contrainte

Ce document décrit une séquence possible. Aucun changement de code, configuration mypy, ignore, déplacement, appel fournisseur ou démarrage de 12.17.3 n'est exécuté dans 12.17.2.

## Lot A — Remédiation typée ciblée

Périmètre proposé : `13` changements individuels couvrant `19` diagnostics.

- supprimer dix casts réellement redondants et un ignore réellement inutilisé (`C01`);
- distinguer les deux variables de boucle dans `anchor_corpus_v3.py` (`C04`), ce qui traite une racine et six cascades;
- typer explicitement la collection hétérogène du protocole (`C06`).

Garde : conserver à l'identique les données, ordres, identités, montants, projections, hashes contractuels et comportements runtime. Chaque retrait de cast/ignore doit être justifié par le type inféré observé, pas par un affaiblissement de mypy.

## Lot B — Rationalisation architecturale 12.17.4

Périmètre candidat : `9` changements racines couvrant `14` diagnostics.

- formaliser le contrôle de flux non retournant du provider (`C02`);
- centraliser, si les contraintes historiques le permettent, la construction du tuple strong/mixed/weak (`C03`);
- unifier ou aligner les deux gardes budgétaires (`C05`);
- dépendre directement du propriétaire de `AnchorTier` (`C07`);
- exprimer explicitement le contrat commun ou séparer les variables de specs (`C08`);
- décider du placement des deux fichiers provider actuellement sous `tests/providers/anthropic` sans les introduire implicitement dans le runtime métier.

Les fichiers et valeurs historiquement hashés doivent rester traçables. Une consolidation ne doit pas réécrire silencieusement une preuve immuable.

## Validations exigées pour un futur lot autorisé

1. Vérifier le diff et confirmer l'absence de modification de données ou secrets.
2. Rejouer la commande mypy bornée `backend` et exiger `0` erreur sur `659` fichiers ou expliquer toute variation légitime du dénominateur.
3. Rejouer la commande import-driven stricte et exiger la réduction correspondant exactement au lot réalisé.
4. Exécuter les tests ciblés des fichiers touchés, puis les validations applicables de `docs/development/ENVIRONMENT.md`.
5. Recalculer les manifests/checksums affectés uniquement lorsqu'une décision propriétaire l'autorise.
6. N'effectuer aucun appel fournisseur pour valider une remédiation purement statique.

## Critère de sortie futur

La dette ne peut être déclarée fermée que si la reproduction import-driven affiche `0` erreur, sans ignore additionnel, sans relâchement de configuration et sans régression du contrôle `backend`.
