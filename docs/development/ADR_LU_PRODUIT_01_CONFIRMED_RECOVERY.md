# ADR LU-PRODUIT-01 — reprise interne d'un CREATE confirmé

Statut : PROPOSED_FOR_DISTINCT_REVIEW. Date : 2026-10-11. Complément R1/A1 de la composition normale ; aucun droit live.

## Décision proposée

La factory normale reçoit explicitement un adaptateur et une seule identité grant/namespace. Avant de servir HTTP, elle appelle `confirmed_dispatch() -> Mapping[str, object] | None`, capacité de lecture technique de cet adaptateur. Elle n'explore aucun dossier historique et ne recherche pas de grant ambiant. Sans réservation ou réponse confirmée, le retour vaut None ; un reçu UNKNOWN, incomplet, corrompu, substitué ou une chaîne incohérente provoque un refus fermé, sans nouveau dispatch.

Le dispatch est une copie exacte de l'entrée R6-P0-DISPATCH-1.0, capturée avant l'effet. Le reçu RESPONSE_CAPTURED et son artifact sont liés au grant, body, préflight, namespace et dispatch. L'adaptateur relit avec les primitives F02 existantes, compare toutes les empreintes et accepte exclusivement `completed`. Il ne restaure aucune permission : la fenêtre du grant peut être expirée pour lire un effet confirmé. Une preuve de consommation n'est jamais effacée.

La factory remet ce dispatch au service Application par `recover_confirmed_generation(request: Mapping[str, object]) -> Mapping[str, object]`. Le service refuse les ports sans la capacité companion `P0ConfirmedGenerationRecoveryPort`, les bindings et identités déjà présents avec un contenu différent. Il appelle exclusivement `recover_confirmed(request=request)`, jamais authorize/generate. L'adaptateur repasse le même parsing strict, les labels, CAP-G01 en préparation sans exécution, GenerationOutputGuard et bind_p0_content. Aucune résolution de secret, construction de transport, réservation ou autorisation ne se produit dans cette voie.

Le service répète CreateP0Candidate et les contrôles de contexte, references/extraits et lineage exacts ; le cours conserve sa politique propre. Il n'attribue pas une nouvelle intelligence ni une review à ce rejeu. Le résultat rejoint les records et passe les validations locales actuelles puis `publish_generated`, via saved_source et le use case Application save existant. Une version déjà sauvegardée est acceptée uniquement si son bundle SHA et ses identités sont identiques ; aucun écrasement, nouveau parent ou duplication artificielle. Une erreur de publication conserve le reçu technique et n'annonce pas APPLICATION_SAVED.

Cette conservation de sécurité et la récupération du même résultat sont explicites dans l'interface. Le chemin utilisateur après redémarrage est la bibliothèque existante ; aucun endpoint fournisseur de reprise ni nouveau bouton de génération implicite. Les imports documentaires n'acquièrent pas cette capacité. Les références privées manquantes empêchent leur revalidation ; le résultat reste exposé avec les dispositions historiques de sources, sans vérité reconstruite depuis un rapport.

## Contrôles et limites

Tests synthétiques : capture puis arrêt avant publication, nouvelle instance et grant expiré, zéro secret/transport/authorize/generate à la reprise, publication Application des mêmes prod/ver/bundle et ouverture depuis bibliothèque. Mutations : autre dispatch/lineage/ref/extrait/body/grant/artifact, UNKNOWN, incomplete, output invalide, collision de version et preuve manquante ; aucun résultat de secours.

L'adaptateur possède uniquement la conservation technique privée d'un effet normalisé (pas le raw HTTP absent du contrat transport), sans store métier parallèle. Application possède la sauvegarde durable du candidat. Ce protocole ne relance aucun fournisseur, ne qualifie pas pédagogiquement la réponse, n'adopte aucun tarif et ne modifie aucune seed ou runtime original.

Retour arrière : ne pas injecter la composition normale. Les reçus restent immuables ; le mode par défaut reste sans fournisseur.
