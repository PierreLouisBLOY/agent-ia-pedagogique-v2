# ADR LU-PRODUIT-01 — statut administratif local à la réception

Date : 2026-10-12. Statut : REVIEWED_BEFORE_IMPLEMENTATION, qualification du successeur requise.
Parent : bd847eb2ce3be8d53c2c936e16725bcae40839e7.

## Décision et portée

Le marqueur CANDIDATE exigé par CreateP0Candidate est une propriété locale de la ressource.
Le schéma et les instructions fournisseur ne doivent pas rendre ce statut dépendant d'une
formulation proposée. Le binder bind_p0_content valide d'abord le DTO P0Production complet.
Si aucune limitation ne contient exactement CANDIDATE, il ajoute une unique limitation
administrative déterministe, puis reconstruit et revalide le DTO.

Les limites fournisseur et tous les champs pédagogiques, identités, contextes, références,
lineage et provenance restent intacts. Le DTO dérivé et les contrôles liés ont leurs propres
empreintes ; la réponse capturée et la requête fournisseur demeurent historiques et immuables.
Un marqueur existant conserve la production identique. Des limitations vides/invalides restent
refusées ; 15 deviennent 16, 16 sans marqueur restent refusées sans troncature.

Le garde Application, le scanner de contenu partagé, les politiques COURSE/autorité, le wire,
schéma/prompt, tarifs, paramètres et contrôles financiers ne changent pas. L'ajout ne vaut
ni validation pédagogique, ni certification officielle d'une source, ni promotion.

## Revue préalable et preuves

Prototype privé et ADR relus avant la source : avis distinct FAVORABLE_LIMITED,
SHA-256 957036d7603976c3218b21f3b2b9494dcd3da3e85f774d5bea9590a7296f6520.
ADR privée 9e5adb232b2d98f069844636e23ef1cec31c2a759bf1fa84e7dcb9d4f699d4d8 ;
prototype f2b831b10ed112847d2fbe5bd55a2396ee61b583cc0e32ad2deed97da30b2d27.
27 tests synthétiques du prototype ont réussi ; 16 probes distincts complémentaires ont réussi.
Ces comptes ne constituent pas la qualification des sources réelles ni celle d'une ressource réelle.
Le reçu technique propriétaire confirme la cause de réception sans texte fournisseur brut.

## Couverture et versionnement

Tests positifs et négatifs : six familles, garde historique reproduit sans statut, intégralité
du contenu conservée, hash dérivé, idempotence, frontière 15→16, limitations invalides, identités,
contexte/lineage, barème et preuve. Rejouer les tests de projection, des contrôles agentiques et
de récupération Application applicables, lint/typecheck et contrôles exacts du delta.

Les propriétaires modifiés sont p0_content.py, ce document et test_p0_candidate_status_binding.py.
Le registre, manifeste et pin de manifeste du scanner suivent uniquement la succession LU
déjà admise et relue : revues de propriétaires et des trois contrôles avant leur activation,
scanner inchangé hors MANIFEST_SHA256, anciennes preuves/exclusions/pins conservés.

## Retour arrière et limites de récupération

Conserver le parent, package/copie adoptés et preuves historiques ; ne pas modifier la copie P1
adoptée ni réécrire un reçu, profil, permission, slot ou LOCK. Le correctif reste hors live.
Ce changement n'active aucun nouveau profil/transport et ne renouvelle aucun droit/quota/fenêtre.

La publication d'une capture historique avec le lecteur successeur exige une composition
hors live explicitement qualifiée, avec identités historique/courante distinctes, contrôle
PARSED+CONSUMED en plus de confirmed(), même wire reconstitué et garde intact, refus d'ambiguïté,
UNKNOWN, substitution et conflit de version. Elle n'est pas qualifiée par cet ADR du binder.
La ressource réelle, ses exports et la recette enseignante restent à vérifier séparément.
