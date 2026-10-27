# ADR — contribution locale en ajout seul, distincte des références canoniques

## Décision et portée

La contribution pédagogique locale complète est conservée dans un overlay séparé. Cette extension Application est désactivée par défaut. Elle ne modifie ni les références canoniques, ni leurs schémas, ni le moteur de recherche, ni P0/P1, ni le parcours COURSE. La conception a été relue avant l’implémentation ; les décisions et preuves privées restent dans le dossier technique externe. Cet ADR générique ne contient aucune donnée propriétaire ou identité runtime.

Une admission locale du texte ne crée pas d’autorité officielle, de relation institutionnelle native ou d’autorisation fournisseur. Le succès de conservation, la préparation locale, l’évaluation pédagogique et la promotion restent distincts.

## Contrats et propriétaires

Neuf nouveaux modules fermés :

| Fichier | Responsabilité |
|---|---|
| `backend/modules/documents_provenance/contracts/dto/local_contribution_provenance.py` | Provenance locale typée ; `UNKNOWN`, non officielle, transfert `NOT_ADOPTED`, recette `NOT_PERFORMED`. |
| `backend/modules/resource_library/contracts/dto/local_contribution.py` | Authority injectée, commande fermée, record complet immuable, relecture exacte et projection locale. |
| `backend/modules/resource_library/ports/outbound/local_contribution_store.py` | Attestation, session, inspection, ajout seul et relecture ; aucun type SQL, path, fournisseur ou SDK dans le port. |
| `backend/modules/resource_library/application/commands/register_local_contribution.py` | Gates, allocation des quatre références locales et conservation par le port. |
| `backend/modules/resource_library/application/queries/read_local_contribution.py` | Vérification des références, hashes, binding et provenance ; inspection descriptive, sans réparation. |
| `backend/adapters/inbound/application/local_contribution.py` | Entrée Application propriétaire de confiance uniquement. |
| `backend/adapters/outbound/resource_library/local_contribution_store.py` | Native Windows, cible/profil/DACL, leases, verrou et publications exclusives. |
| `backend/infrastructure/composition/factories/local_contribution.py` | Preuve propriétaire exacte hors requête, candidate/package/plan/revue/scope attendus ; OFF par défaut. |
| `backend/infrastructure/composition/factories/stmg_local_contribution.py` | Companion STMG utilisant la seule relecture overlay exacte, sans fallback. |

La commande reçoit le texte complet, taille/SHA UTF-8 exacts, clé logique, titre, notion canonique choisie et contexte local. Elle ne reçoit ni authority, path, objet/version/passage imposé, permission ou grant. L’Application alloue `local-content`, `local-version`, `local-passage` et `local-provenance` uniquement après les préconditions et l’inspection sous verrou. Ces namespaces ne désignent pas des objets institutionnels natifs.

La provenance conserve origine du draft, auteur, date, admission locale, autorisation d’opération et contexte. La factory vérifie les octets de la preuve injectée et ses identités exactes. Les attentes sont injectées hors requête, y compris l’attestation liée à la cible, au profil et au binding complet. Une factory OFF ne consulte aucun store/référence et n’alloue rien.

## Conservation et refus

La root neuve autorisée contient `OVERLAY`, le verrou immuable `writer.lock` et quatre répertoires : `intents`, `staging`, `versions`, `commits`. Aucun catalogue mutable, suppression, reset ou remplacement. Une seule nouvelle contribution est permise par scope.

Sous leases natives no-follow et verrou interprocessus non bloquant : intention → record complet → commit liant leurs SHA. Publications exclusives par lien sur le même volume, flush et relecture. Les stages sont retenus en succès comme en échec. Deux noms partageant la même identité native ne sont pas deux sauvegardes indépendantes.

L’inventaire fermé vérifie aussi l’état confirmé : une seule intention/version/commit, quatre stages associés exactement aux quatre publications, aucune entrée orpheline. L’état absent exige le seul stage du marker. Une absence de commit, un orphelin, une incohérence ou une concurrence impose un arrêt descriptif ; aucune nouvelle allocation/publication n’est tentée. Un duplicate confirmé exact retourne les mêmes références sans nouvel effet.

L’adapter refuse contexte élevé, profil/cible/parent divergents, UNC, reparse, root de dépôt, root non attestée, collision, DACL élargie, JSON ambigu, fichier hors borne ou incohérence d’identité/bytes. Les handles de répertoires portent `LIST_DIRECTORY | READ_ATTRIBUTES` sans partage DELETE : READ_ATTRIBUTES seul ne suffit pas à empêcher le renommage Windows. La DACL effective, son propriétaire, sa protection et ses ACE sont contrôlés, sans se fier au seul statut conventionnel du helper.

Les helpers privés existants sont réutilisés exclusivement après création fraîche et sous lease, sur les nouveaux objets possédés. Aucune DACL du parent existant ou référence n’est modifiée ; aucune élévation ou configuration Windows n’est effectuée. `atomic_publish_fresh` n’est pas réutilisé, son branchement de cleanup pouvant supprimer une publication.

Chaque fichier JSON est borné à 64 KiB ; le texte complet à 16 000 octets, avec taille/hash spécifiques exacts imposés par l’autorisation. UTF-8 strict, JSON fermé et canonique, doublons/NaN refusés. Aucun changement du contrat de passage de recherche à 320 caractères et aucune troncature de l’overlay.

L’Application utilise `ApplicationOutcome`, ses side effects et les failures canoniques existantes. Avant effet : NONE ; après footprint incertain : UNKNOWN/`AF_COMMIT_OUTCOME_UNKNOWN`, résultat non réussi et reconciliation requise. Les pièces restent présentes. Aucun type EffectState du runtime agentique n’est importé par le métier.

## Relecture et sélection locale

La relecture retourne uniquement un graph intention/record/commit exact confirmé, ses références allouées et sa provenance. `SearchSourceStatus` garde identity/lifecycle/validation `UNKNOWN`, passage `UNKNOWN`, base `STATUS_UNAVAILABLE`. La projection garde le texte complet, `authority=UNKNOWN`, association `LOCAL_CONTEXT_ONLY`, relation `NOT_ADMITTED_FOR_POSITIONING` et transfert `NOT_ADOPTED`. Le snapshot de référence conserve explicitement `CONTENT_GAP` lorsqu’il est présent.

Le companion est raccordé à la factory STMG Application existante. Son mapping de lectures exactes est figé en mémoire. Une absence, autre version, provenance modifiée ou ancien scope portant un nouveau choix est refusée, sans fallback canonical/search. Les nouveaux choix/allowlists/preuves sont construits à partir des identités réellement retournées ; leur rattachement final reste une étape explicite après conservation et relecture. Aucun ID concret n’est anticipé par cet ADR.

Le readiness local n’atteste pas à lui seul une couverture pédagogique complète. Un statut de contenu insuffisant reste insuffisant malgré la longueur du texte. La couverture des questions historiques doit être liée aux octets réellement admis et demeure une pièce distincte.

## Frontières et retour OFF

Aucun nouveau routage HTTP, route agentique, capability registry ou permission REQUEST/ALLOW. Les six routes du contrat `ADR-P12-028-use-case-application-routing-boundary` restent exactes. Une future exposition nécessiterait sa propre décision canonique. L’overlay n’alimente ni F2A, ni exact notion/search, ni admission P1, ni dispatch fournisseur.

Retour : fermer les leases, retirer l’injection du choix successeur et conserver la composition OFF. Tous les stages, intentions, versions, commits et inspections restent conservés ; pas de cleanup, rollback, réparation SQL, référence ou HKCU. L’activation réelle exige un plan relu, candidate/package/cible/profil exacts et leurs preuves attendues par Application. La revue du code ne réalise pas cette opération.

## Qualification par impact

Trois nouveaux tests synthétiques : `tests/unit/test_local_contribution.py`, `tests/integration/test_local_contribution_filesystem.py`, `tests/unit/test_stmg_local_contribution.py`. Ils couvrent gates OFF, preuve/scope/cible, texte complet au-delà de 320 caractères, provenance, allocation Application, relecture/reprise descriptive, UNKNOWN, max1, immutabilité, inventaires, orphelins, échecs flush/publication/commit, DACL/native leases/verrou Windows et companion normal.

Les tests natifs manipulent seulement des objets synthétiques neufs hors du dépôt, sans base originale, reçu privé, contenu propriétaire ou permission persistante. Les résultats et manifests sont conservés hors Git ; cet ADR ne présume aucun PASS, activation, qualification live, recette enseignante ou release.

## Provenance V2 : création inconnue, enregistrement distinct

Le contrat V1 et sa validation de date de création restent stricts. Le DTO nominal V2 conserve `draft_created_at=null` et `draft_creation_status=NOT_ESTABLISHED`. Il indique séparément `draft_recorded_at`, auteur de kind SUBAGENT, `recording_basis=ORIGINAL_PROPOSAL_RECEIPT` et descriptor/SHA logique de l'original. Ces métadonnées n'attestent ni auteur humain, ni signature ou création initiale. La date réelle `record.created_at` appartient toujours à l'Application pendant la conservation.

Le parser imbriqué du record choisit uniquement V1 ou V2, sans migration. La factory V2 exige les octets et le SHA attendus du reçu original injectés par la composition trusted hors requête. Elle contrôle UTF-8/JSON strict, raw SHA, auteur/date enregistrée et texte/taille/SHA en mémoire, sans I/O ni exposition du contenu du reçu. Le mode V1 refuse ces entrées supplémentaires. Une preuve absente, ambiguë, divergente, un faux statut de création ou une date de consigne/adoption/mtime substituée entraîne un refus avant effet.

L'origine du draft et sa proposition historique restent immuables ; l'admission ultérieure et la preuve d'opération gardent leurs responsabilités distinctes. Scope et binding incluent toute la provenance V2 exacte. Les futurs choix/projections ne sont rattachés qu'après les vrais IDs et la relecture ; aucune réécriture des anciens scopes, date ou grant. OFF et les refus UNKNOWN/reconciliation du store ne changent pas. Cette évolution a son ADR technique et son avis préalable distinct dans le dossier externe, sans données privées dans Git.
