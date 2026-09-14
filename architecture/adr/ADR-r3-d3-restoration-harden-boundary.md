# ADR — Reprise ponctuelle D3 et successeur technique borné

Statut : ACCEPTED_SYNTHETIC_IMPLEMENTATION. Décision propriétaire explicite liée au manifeste source indiqué ci-dessous. Le contrat est réalisé exclusivement avec des sources artificielles ; aucun effet opérationnel sur le pilote n'est autorisé.

Le store reste volatil. Ajouter une fabrique de restauration exacte n’est pas un service général d’import, export ou persistance (R4 reste séparé). Aucun port agent supplémentaire, aucune entrée filesystem métier dans un agent, aucun SQL.
L’autorité de restauration et la permission de modification sont séparées. Le contrat A14 existant vérifie le changement éditorial historique avec parent, plan et preuve indépendante ; son prédicat et source_capability=null ne changent pas.
M08 charge atomiquement deux objets historiques vérifiés dans un store neuf et garde le plan consommé ; M09 revalide ; M04 assemble le futur delta D3 uniquement ; AG03 propose via GenerationPort, sans autorité de publication.
La session restaurée n’est pas activée en production par défaut et ne réouvre pas les grants consommés.

E08 étend un vocabulaire fermé du diagnostic/reçu, pas la règle de refus ou la route HTTP.
HARDEN a une projection/sortie dédiées pour réduire transfert et erreurs, sans extraction générale d’un framework de génération.
Les helpers publics d’anchors peuvent être réutilisés sans modifier leur sémantique ; le protocole PREPARE reste inchangé.

Les guards historiques conservent leurs tables/preuves. Un seul nouveau successeur D3 s’enracine à 6e43ca5a avec inventaire exact, assertions et hashes de sortie à sceller après implémentation. Les délégations et changements d’assertion sont explicitement inventoriés.
La reconstitution d’une vue historique pour comparaison AST n’est admise qu’après vérification des bytes courants exacts ET du delta D3 autorisé ; elle ne peut masquer une mutation du candidat.

Rejetés : callback toujours vrai ; Evidence construite à partir du candidat comme autorité ; republisher V2 ; supprimer V1 ; modifier A14 ; générique base_bundle complet au provider ; masquer le défaut E08 ; élargir les guards par dossier ; prévalider un budget inconnu ; lancer R4/H3.

L'accord groupé couvre les 46 chemins et symboles, les tests nommés, un commit local, la publication sur codex/r3-d3-synthetic-6e43ca5a, la validation d'un clone sans pièces privées et l'intégration à main selon ses protections. Aucun force-push, rebase, squash ou contournement de protection. La restauration du pilote et tout effet fournisseur exigent des accords distincts.


## Adoption pour l'implémentation synthétique

Accord groupé propriétaire lié au manifeste source a61c067f01d8bb43d191900ac681b46cf46e764a95ef98069b5ffdec28d623ca. Seuls les 46 chemins de IMPLEMENTATION_SCOPE.json sont autorisés. Aucune autorité live implicite. Les tests SQLite historiques sont limités à neuf cas synthétiques, avec fichiers temporaires externes ; aucune base utilisateur.
