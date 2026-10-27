# Addendum ADR LU-S5 — média local sur production réouverte

Statut : PROPOSED_FOR_REVIEW. Lot LU-PRODUIT-01, base 89ef3ed.
Complète sans remplacer ADR-LU-S5-production-media.md, revue sur le SHA-256
`b69bc1bad962a8ec6827b031ba5d1d5cbe94531ccacba6ca82ace9e8aef82b5a`.

## Défaut établi et décision proposée

La première commande média demande les extraits de preuve et crée de nouveaux
identifiants de run/step/request. Ces extraits ne sont pas réattestés après
réouverture et cette transformation est incompatible avec ReviseSavedP0Candidate.
Ajouter une voie locale explicite conservant contexte, références et identités
historiques de la lineage ; seuls la version enfant, parent_version_ref et le
plan média changent. Aucune restauration d'autorité, admission de source,
génération fournisseur ou promotion n'en découle.

La commande commune accepte une preuve explicite optionnelle : présente, elle
emploie ReviseP0Candidate et en vérifie les empreintes ; absente, elle emploie
ReviseSavedP0Candidate et consigne sources=RESERVE avec
HISTORICAL_EVIDENCE_NOT_REVALIDATED. Les validations héritées ne sont pas
transformées en contrôles actuels. Les réserves et provenance du parent restent
conservées ; les revues de l'enfant sont vides. Le parent est immuable.

## Contrat HTTP compagnon fermé

POST `/api/v2/p0/media`, contrat `P0-LOCAL-MEDIA-HTTP-1.0`. Aucun changement du
registre historique R2/R3/R4. Le corps JSON borné à 80 Kio a exactement :
`command_id`, `production_ref`, `version_ref`, `bundle_sha256`, `selection`.
Command_id : 32 caractères hexadécimaux minuscules. Identités de production et
version canoniques ; bundle_sha256 exact obligatoire. Clés dupliquées refusées.

Deux sélections fermées :

- `{"mode":"NO_MEDIA","reason":"raison explicite"}` ; aucune image produite.
- `{"mode":"LOCAL_DIAGRAM","entries":[...]}` ; une à huit entrées contenant
  exactement `brief`, `required`, `dependency_refs`. Brief VisualBrief 1.0,
  LOCAL_DETERMINISTIC et COURSE_LOCAL_DIAGRAM_V1 ; pas de source importée, URL,
  chemin, octets PNG arbitraires ou rendu distant dans cette voie. Le renderer
  déterministe existant décide seulement des octets du diagramme décrit.

Les briefs restent liés aux capacités/notions exactes du contexte conservé et
aux dépendances du bundle courant. Une indication RESOLVED_ADMITTED conservée
dans ce contexte ne réatteste pas les extraits historiques. Le cours expliqué
P0 peut recevoir ce successeur ; le chapitre riche COURSE est refusé
explicitement par PRODUCTION_MEDIA_LOCAL_P0_REQUIRED et garde sa voie actuelle.

Un service Application reçoit deux callbacks composés : saved_source pour
obtenir le parent par Application, publish_child pour enregistrer le nouvel
enfant dans le cycle P0 existant. Aucun accès store, SQL ou filesystem métier.
Le publish est effectué une seule fois après les contrôles ; l'enfant devient
lisible/modifiable/sauvegardable par les actions P0 et saved canoniques. Le
contrat de callback impose parent exact et absence de conflit de version. Le
service marque command_id avant rendu/publication ; un résultat incertain ne
rejoue pas le worker. Même commande/même corps restitue le résultat antérieur ;
une substitution du corps est refusée. Pas de sauvegarde implicite.

Le résultat contient view élève exacte, identités du parent/enfant, validations
locales, disponibilités d'export par public, sources=RESERVE, autorité
NONE_RESTORED, provider_attempts=0 et promotion=NOT_PERFORMED. Aucun bundle
professeur n'est transmis sur cette route. Les erreurs sortantes sont des
codes bornés sans texte d'infrastructure ; le transport local conserve nonce,
origine et politique d'accès déjà appliqués par le serveur.

## Objets, retour arrière et contrôles

Objets S5 : commande/inbound média, nouveau service work_orchestration,
endpoint HTTP compagnon, tests ciblés. Composition/activation et publication
dans P0CreationService : raccord S2 coordonné ; registre compagnon : coordonné
avec S4. Aucun nouveau framework, permission ou dépendance.

Retour arrière : ne plus composer la capacité ; conserver les versions déjà
créées. Aucun retour en arrière d'une bibliothèque ou modification historique.

Tests : parent rouvert sans extrait, lineage et parent immuables, réserves et
provenance conservées, NO_MEDIA complet, diagramme puis sauvegarde/réouverture
et export exact via Application ; refus mauvais hash/version/public/capacité,
COURSE riche, clés supplémentaires/octets/URL/path, source importée ; double
commande/ID substitué/rendu incertain ; enfants périmés refusés lors d'une
révision de dépendance. Ruff/mypy sur le delta et régression média concernée.
Ces preuves locales ne qualifient ni génération libre ni sémantique ni Word.
