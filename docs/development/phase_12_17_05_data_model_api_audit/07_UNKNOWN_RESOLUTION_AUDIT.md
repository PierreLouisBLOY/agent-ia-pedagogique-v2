# Phase 12.17.5 — Audit des deux UNKNOWN

```text
RESOURCE_STATUS_ACTIVE_CANONICAL = UNKNOWN
CONTEXT_ORIGIN = UNKNOWN
UNKNOWN_SILENTLY_RESOLVED = 0
```

## Resource `ACTIVE/CANONICAL`

Les preuves convergent seulement sur la représentation technique :

- le DDL seed/runtime porte une unique colonne `resource.identity_status` avec
  default `ACTIVE` et sans CHECK ;
- le Domain conserve volontairement `ACTIVE` et `CANONICAL` comme valeurs
  distinctes de `ResourceIdentityStatus` ;
- le mapper encode et décode les deux sans équivalence ;
- les tests prouvent leur distinction et READ-15 prouve `ACTIVE` sur le fixture
  canonique ;
- la migration 001 ne touche pas `resource`.

Aucune preuve owner n'établit si les deux valeurs sont deux états d'une même
dimension ou deux dimensions différentes. Le statut reste `UNKNOWN` et aucune
migration n'est autorisée.

## `ContextOrigin`

`ContextOrigin.RUNTIME` est un VO technique Application. Le mapper le valide et
retourne volontairement `None`; `ContextStore` écrit `notes=NULL`. Le DDL
seed/runtime ne contient aucune colonne d'origine et la migration 001 ne touche
pas `pedagogical_context`.

Il n'existe ni besoin produit approuvé, ni sémantique de stockage univoque, ni
contrat de lecture. Le statut reste `UNKNOWN`; la note pédagogique ne doit pas
être détournée en métadonnée technique.
