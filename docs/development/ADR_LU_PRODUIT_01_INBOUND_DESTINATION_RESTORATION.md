# ADR LU — restauration des frontières inbound et de la destination affichée

Statut : IMPLÉMENTÉ HORS ACTIVATION, après les revues distinctes préalables `f415c130d6afcadc9abe939c293b66f6497434c603a2afe371f43e2b0ee7fc22` (frontières inbound) et `c56714ea136cf2409e155c6f32aab24491795dbbde1829cba090bc81a6b79f8b` (octets du compagnon destination). Même LU-PRODUIT-01. Le global brut `30bab7a` conserve 8898 PASS / 26 FAIL / 0 ERROR / 5 SKIP et ses treize nouveaux FAIL internes ; ce correctif ne réécrit aucune preuve.

## Défauts établis

La sonde `probe_frontend_internal_global_failures.json` reproduit le prédicat frontend historique inchangé sur les trois assets du global. Son unique correspondance est l'URL informative du consentement dans app.js ; les cinq node_ids UNSAFE_OR_EXTERNAL_ASSET sont liés au même prédicat. Une URL distante incorporée à un asset dépasse cette frontière fermée, même si sa présence vise seulement l'information.

`api/p0_notion_evidence.py` instancie SearchSourceStatus et AdmittedLocalPassage depuis les modules métier. `api/routes.py` importe require_logical_identifier du port métier. Les frontières HTTP existantes interdisent ces dépendances directes. Les routes et projections doivent rester des structures wire bornées, sans autorité métier.

## Décision minimale proposée

1. p0_notion_evidence : remplacer l'instanciation du passage métier par les contrôles de projection wire identiques à ceux déjà utilisés dans SearchEndpoint : types exacts, bornes des quatre identifiants, alphabet Unicode lettres/nombres ou `._:-`, extrait de 320 caractères maximum sans caractères de contrôle/format/séparateur interdit, booléen de troncature exact. Conserver les données natives, tous les statuts et provenance, exclusions, tailles et empreintes. La validation SearchSourceStatus passe par `validate_source_status_projection` de la frontière inbound Application existante, comme la recherche historique. Aucun nouveau lecteur, callback, SQL ou permission.
2. routes : valider le format de notion_id avec unicodedata et les bornes wire déjà admises, sans import métier. Les tuples de routes historiques et tous les rejets existants restent identiques. Le use case Application revalide toujours l'identité canonique : accepter un format ne crée aucune notion.
3. Destination consentement : projection publique additionnelle `transfer_destination` dans l'enveloppe de retour du preview, hors du preview 1.0 et de son hash. Champs fermés proposés : `provider`, `model`, `endpoint`, `permission_sha256`. Ils proviennent exclusivement de la permission exacte validée par l'adaptateur ; aucun credential, grant ou appel n'est créé. La projection ne devient pas une nouvelle autorisation.
4. Le frontend affiche cette destination comme texte après validation de la structure fermée, du provider/model admis, de la correspondance permission_sha256 avec le preview et de l'URL par ses composants : HTTPS, hôte exact api.openai.com, chemin exact /v1/responses, aucun port, userinfo, query ou fragment. Aucune URL distante littérale n'est stockée dans l'asset. Aucune concaténation de fragments ne remplace l'ancien littéral pour échapper au scanner. Aucun lien, fetch ou navigation externe n'est ajouté. Une projection absente ou mutée bloque l'acceptation et l'envoi ; les confirmations de contenu/coût et l'expiration restent obligatoires.

## Périmètre et contrôles

S3 possède uniquement p0_notion_evidence.py, routes.py et un nouveau test wire. Root possède p0_product.py/app.js et les témoins Node de consentement. S4 possède intention et EvidenceAgent/security. Aucun scanner, assertion historique, seed, original, lock ou autorité n'est changé.

Rejouer sans modification d'assertion les tests exact-notion HTTP (positifs, données natives/UNKNOWN, limites, exclusions sans oracle, mutations) ; ajouter les témoins d'absence d'import métier et d'équivalence du format wire sur caractères Unicode/invalides. Rejouer les node_ids historiques de frontières après le correctif S4 et les cinq node_ids frontend après celui de root. La destination nécessite ses propres positifs et mutations provider/model/permission/hash/host/path/port/userinfo/query/fragment/missing/unknown fields, plus état périmé ou draft. Un double de transport est explicitement déclaré ; zéro fournisseur réel.

Les gardes versionnés ne sont rafraîchis qu'après revue source finale puis des octets exacts des contrôles. Les nouvelles mutations fichier/index et la qualification composite devront couvrir ce delta réel. La restauration ne dispense ni revue, ni qualification du package.

## Retour arrière

Avant commit root, retirer seulement les modifications source exactes de cette restauration sur la candidate isolée, en conservant les bruts et prototypes. Après commit, conserver l'historique et créer si nécessaire un successeur local revu ; aucun reset, effacement d'archive ou remplacement de base.

## Limites

Les treize nouveaux FAIL ne sont pas clos par cet ADR ou la sonde. Chaque fermeture exige le node_id exact réussi, ses octets actuels et l'applicabilité prouvée. Le timeout historique du lanceur conserve sa signature et sa limite de 15 secondes sous charge. La donnée native UNKNOWN, les exclusions, les décisions P1 et la recette enseignante gardent leurs dispositions. Aucun appel fournisseur, COUNT, credential, promotion, release ou ouverture live.
