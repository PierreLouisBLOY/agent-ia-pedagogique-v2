# ADR LU-PRODUIT-01 — composition P0 fournisseur normale, protégée et désactivée

Statut : PROPOSED_FOR_DISTINCT_REVIEW. Date : 2026-10-11. Cette ADR ne constitue aucune autorisation live. Producteur : S4 `/root/agents_controls`.

## Constat dans la candidate

`build_local_read15(..., p0_generation=None)` et `build_p0_creation(..., generation=None)` laissent le port P0 sans fournisseur. Une préparation admissible retourne donc AUTHORIZATION_REQUIRED, sans contenu inventé. `P0CreationService._generate` comporte déjà la confirmation institutionnelle, le contrôle de la préparation exacte, sa consommation avant dispatch et la validation Application du résultat et des bindings.

`build_p0_content_request` et `bind_p0_content`, sous `backend/adapters/outbound/generation/openai/p0_content.py`, proposent le contenu des six familles depuis un contexte confirmé et des références/extraits bornés. Le payload fournisseur exclut les identités locales de production/lineage et sépare la projection institutionnelle bornée. Le cours institutionnel utilise la politique COURSE existante. Le harnais `tools/mega_no_count` constitue une composition privée du pilote M01–M07 : ses grants, namespace, budget, baseline et code pins ne peuvent être réutilisés comme autorisation de l’application normale.

## Décision technique proposée

Composer un **nouvel adaptateur P0 normal**, hors métier, qui implémente le `P0GenerationPort` existant. Préserver ce port, les contrats historiques et les adaptateurs historiques ; aucun assouplissement de leur parsing, COUNT ou scanner. Le mode par défaut reste sans fournisseur. L’activation future nécessite un profil et un grant nouveaux, explicitement injectés par le lanceur et liés à la version source/package qualifiée. Pas de découverte de credential ou grant au démarrage.

### Raccords et responsabilités

1. UI → companion P0 existant → `P0CreationService` → contexte institutionnel confirmé et références authentifiées par les use cases Application. AG01 propose seulement ; AG02 fournit les entrées bornées, sans autorité créée par la génération.
2. Adaptateur P0 normal → `GeneratorAgent` / `GenerationCoordinator`, CAP-G01 existant, par une projection canonique explicite du dispatch P0. `ProductionRequest` conserve famille, objectifs, contexte, références et bindings ; les données d’entrée restent étiquetées non fiables, conformément aux labels et scanners existants. Un `GenerationPort` technique P0 dédié utilise les fonctions purement versionnées de construction et binding P0. Il ne modifie pas le parseur historique de `OpenAIGenerationAdapter`.
3. Préparation technique → sérialisation exacte `r2_request_parameters` existante → préflight sans COUNT → nouvelle réservation durable liée aux empreintes → résolution du secret injectée → transport SDK strict existant (`OpenAISDKResponsesTransportFactory(r2_destination=True)`), endpoint Responses seul.
4. Reçu technique privé capturé avant parsing → `GenerationOutputGuard` avec six champs P0 fermés → `bind_p0_content` → `CreateP0Candidate` et contrôles Application existants. Ne pas prétendre que le fournisseur a déclaré l’usage de chaque source si le schéma P0 ne le contient pas : les sources fournies, les références locales rattachées et les usages réellement déclarés restent distingués.
5. AG04 conserve son port de critique indépendant. La composition minimale autorise uniquement CREATE ; REVIEW reste non lié tant qu’aucune permission distincte n’existe. Le statut de qualité indique explicitement la review non exécutée. REV4 conserve l’obligation d’un oracle indépendant pour les cas quantitatifs. Une réussite du transport/du schéma ne crée ni calcul vérifié, ni adoption, ni promotion.
6. Modifications locales, validation, sauvegarde, reprise authentifiée et export utilisent les commandes Application déjà qualifiées. Aucun appel fournisseur de modification, aucune génération implicite à l’export ou à la reprise.

La première composition proposée reste **synchrone et sérialisée**, comme le port P0 existant : un seul dispatch, budget temporel explicite du transport. Le dossier doit contrôler le délai de l’interface, la déconnexion et la visibilité d’un résultat incertain. Aucun job/polling ni nouveau contrat HTTP asynchrone n’est introduit par cette ADR. Un timeout, annulation ou doute après réservation arrête l’envoi et conserve le namespace consommé ; aucun retry ou recréation automatique d’autorisation.

### Grant versionné proposé, séparé des autorisations historiques

Nouveau contrat fermé d’infrastructure `P0-NORMAL-CREATE-GRANT-1.0` : opération CREATE seulement ; `max_calls=1`, COUNT/REVIEW/MODIFY=0 ; `retry=0`, `fallback=NONE`, parallélisme 1 ; fenêtre UTC bornée, namespace neuf à usage unique, aucun renouvellement automatique.

Identités requises : décision propriétaire exacte et empreinte ; HEAD/arbre source/package, code pins du raccord nouveau, identité du runtime autorisé en lecture ; préparation et contexte confirmés ; références/extraits sélectionnés ; body Responses exact et sa taille ; schéma et profil ; manifeste du tokenizer et de son mapping modèle/données ; preuve tarifaire admise et méthode majorante ; racine privée des reçus et identité du namespace. Les flux HTTP ne permettent ni de charger un grant arbitraire, ni de choisir un endpoint, chemin métier ou secret.

Profil proposé à soumettre au propriétaire : OpenAI Responses ; modèle explicite `gpt-5.6-terra` déjà employé, reasoning low, service_tier default, `store=false`, `stream=false`, `background=false`, tools vides et tool_choice none ; sortie ≤4 096 tokens ; plafond proposé 0,140000 USD pour **cette génération seule**. Ces valeurs ne sont pas autorisées par les anciens grants. Leur adéquation et le tarif doivent être revalidés avant tout envoi nouveau.

### Préflight financier et réservation

Réutiliser la méthode locale déjà qualifiée dans le pilote, **par un successeur produit sans identités/grants/scénarios anciens**, avec tokenizer officiel isolé fourni et vérifié, mapping officiel du modèle non modifié, données/versions/empreintes authentifiées, comptage de toutes chaînes/clés et JSON sérialisé, réseau interdit pendant le comptage. Tokenizer non reconnu ou données manquantes : STOP ; aucune approximation par caractères et aucun COUNT fournisseur.

Calculer `T = max(tokens_chaines_et_cles, tokens_JSON_serialise)`, puis `U = T + 10 000`. Exiger `U ≤ 40 000` et `C = (U × prix_entree_majorant + 4 096 × prix_sortie_majorant) / 1 000 000 ≤ plafond`. Prix exacts Decimal, unités USD, preuve datée et admise ; pas de réduction présumée pour le cache, pas de COUNT historique assimilé à zéro. L’égalité des empreintes est vérifiée à nouveau immédiatement avant l’envoi.

**Deux plafonds indépendants :** 40 000 tokens ne prouvent pas un coût ≤0,14 USD. Avec les prix **historiques** 2,50/12 USD par million employés par le pilote, le seuil financier est `U ≤ 36 339` (donc `T ≤ 26 339`), sous le plafond technique 40 000. Ce calcul ne constitue pas une preuve tarifaire actuelle.

Réservation pessimiste durable avant tout accès au credential et toute construction d’un transport. Réutiliser les primitives de publication privée exclusive et les contrôles F02 actuels ; **ne pas appeler OneShotReceipt avec un faux ConversationDraftRequest** : ce reçu est lié au contrat R2. Un successeur de reçu P0 conserve les états RESERVED / PROVIDER_ATTEMPTED / USAGE_CAPTURED / PARSED / CONSUMED / UNKNOWN, avec request/grant/preflight exacts, aucun contenu ou credential public et aucune suppression de preuve.

La clé est une `ProviderSecretValue` opaque, reçue d’un `ProviderSecretResolver` injecté après réservation, jamais exposée au navigateur, au métier, aux agents, au JSON du grant, aux logs, stdout ou Git. La saisie native masquée/canal privé déjà existants sont réutilisés seulement après autorisation propriétaire future. Ne pas activer le resolver d’environnement implicitement ni utiliser un shell portant la clé en argument. Le transport strict conserve destination fixe, `max_retries=0`, absence de proxy/env ambiant et de redirection.

## Inventaire minimal proposé, à geler après revue

- Nouveaux adaptateur P0 canonique/technique et policy/grant/reçu normal, dans adapters/infrastructure ; aucun concept spécialisé dans shared_kernel.
- Successeur pur de préflight local et interface injectée de tokenizer/tarif ; les fichiers privés de tokenizer/tarif/grants restent hors Git.
- Nouveau binding/factory normal et option explicite de composition du lanceur ; factory par défaut inchangée sans grant. Aucun endpoint d’activation fournisseur au navigateur.
- Tests doubles explicites des raccords, effets, refus et identités, plus contrôle normal de startup désactivé. Le code historique du pilote reste inchangé.

La liste finale exacte des fichiers sera ajoutée au successeur collectif d’inventaire. Les contrats nouveaux et leur couverture devront être relus avant leur implémentation ; aucune extension globale des scanners ni du plafond d’entrée P0 n’est incluse.

## Contrôles requis avant une décision live mûre

Nominal : deux phases authorize/generate liées au même request/preflight, un seul transport synthétique, labels/scanners et guards canoniques traversés, résultat rattaché aux bindings originaux et source non modifiée, copie sauvegardée/reprise/exportable par Application.

Mutations : HEAD/package/runtime/contexte/ref/extrait/body/schema/profile/tarif/tokenizer/namespace/horloge substitués ; grant absent, expiré, déjà consommé, autre opération ; plafond coût ou tokens dépassé ; endpoint/model/tier/reasoning/outils altérés ; COUNT/REVIEW/MODIFY interdits ; preuve écrite impossible, collision/concurrence/substitution F02 ; credential indisponible ; réponse incomplète/refusée/malformée, timeout/usage manquant ou incohérent. Chaque refus doit prouver zéro resolver/transport lorsqu’il est antérieur à l’envoi ; aucune sortie de secours pédagogique.

Les tests à doubles ne valident ni l’accès au modèle ni son intelligence pédagogique. Les contrôles tarifaire/tokenizer actuels, la confirmation du transfert des extraits exacts et la nouvelle autorisation opérationnelle restent des conditions explicites. L’ADR permet seulement un raccord hors live après revue, aucun envoi ni saisie de clé.

## Retour arrière

Ne pas activer le nouveau profil ; laisser `p0_generation=None`, sans modifier les anciennes preuves, branches, grants/réservations, bases ou runtimes. Aucun rollback propriétaire, migration, release ou déploiement. Les contenus déjà produits restent inchangés.
