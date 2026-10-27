# LU-PRODUIT-01 — reprise locale d'une production P0 persistée

État : PROPOSED_FOR_DISTINCT_REVIEW, 11 octobre 2026.
Base : 89ef3edc5f9d09e5f769862833ffa2c1b175c8fb.

## Défaut et décision proposée

Le GET R4 saved rouvre un record authentifié, mais les commandes P0 ne connaissent
que la mémoire de création. Après redémarrage elles refusent sa version exacte.
Relier le P0 existant à un callback Application de lecture des SavedProduction
locaux via la composition existante. Aucun accès SQL/filesystem par P0 ni frontend,
aucun endpoint supplémentaire, aucun alias latest, aucun stockage navigateur.

## Entrées, refus et identité

Le callback ne retourne qu'un SavedProduction typé, LOCAL_APPLICATION, avec bundle
P0 et couple production/version exact. Les imports documentaires restent en lecture
R4 uniquement. Vérifier avant admission en mémoire la lignée entière (32 parents
maximum, même production, absence de cycle, SHA annoncé par la commande exact).
Une erreur refuse atomiquement l'admission ; un record en mémoire de SHA différent
n'est jamais remplacé. Les parents restent immuables.

Les 32 parents sont comptés en plus du record demandé ; le hash fourni par une
commande est toujours celui du bundle P0, distinct du SHA du record saved.
La voie locale utilise un successeur `ReviseSavedP0Candidate` : même validation
de structure/limitations/revendications institutionnelles que CreateP0Candidate,
plus égalité stricte du contexte, des références et de la lignée d'origine avec
le parent authentifié. Elle ne reconstitue aucun extrait brut. Les contrôles
d'extraits de la création et de la révision en session restent inchangés.
Le résultat porte explicitement la réserve HISTORICAL_EVIDENCE_NOT_REVALIDATED ;
la dimension sources reste RESERVE pour ces reprises. Une modification locale
ne prouve ni fidélité sémantique ni actualité des références conservées.

Le plan local est recalculé sur le contexte et le contenu conservés. Les rapports
historiques ne couvrent que leur identité validée par SavedProduction. L'ancienne
provenance et les réserves du parent restent identiques dans sa source sauvegardée.
Une révision crée une nouvelle version, avec preuves d'origine conservées et
contrôles frais ; elle n'hérite pas d'une validation ni d'une revue du parent.

## Autorisations

Aucune restauration de grant, nonce, port fournisseur, quota ni consommation.
Les chemins REVIEW/correction après REVIEW de productions réhydratées restent
fermés (P0_REOPENED_REVIEW_REQUIRES_FRESH_EVIDENCE), y compris leurs enfants.
Le pack brut et les consommations fournisseur historiques ne sont pas persistés
dans le contrat actuel : ne pas les reconstruire depuis leurs empreintes.
Cette continuation permet lecture, modification locale explicite, vérification
structurelle, sauvegarde de l'enfant et export ; aucune qualification live induite.

## Couverture requise

Nominal sur les six familles : sauvegarde, nouvelle composition sans fournisseur,
réouverture, modification locale, enfant, sauvegarde/restart/relecture/export natif.
Mutations : import documentaire, mauvaise production/hash, parent absent/cycle,
conflit de version en mémoire, absence de callback, révision concurrente et refus
REVIEW/correction distante. Contrôler origine, lignée, réserves, absence de copie
des contrôles du parent, et identité de tous les parents après l'opération.

## Retour arrière

Retirer ce raccord de la candidate de développement conserve tous les records
sur disque ; la lecture/export R4 antérieure demeure disponible. Aucun rollback
sur base propriétaire, migration ni modification des sources originales.
