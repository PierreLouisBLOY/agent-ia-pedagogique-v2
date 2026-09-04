# Phase 12.17.5B-B05 — Contrat canonique `resource_ref`

La source de vérité appartient au bounded context Resource :

```text
RESOURCE_REF_REGEX = ^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$
RESOURCE_REF_MIN_LENGTH = 1
RESOURCE_REF_MAX_LENGTH = 128
CONTRACT_OWNER = backend.modules.resource_library.domain
```

`ResourceRef` est un Value Object immuable. Il exige une chaîne ASCII dont le
premier caractère est alphanumérique et autorise ensuite uniquement lettres,
chiffres, `.`, `_`, `:` et `-`. La validation utilise `fullmatch` avec le mode
ASCII.

Les violations syntaxiques lèvent l'erreur Domain typée
`InvalidResourceRefError`. Un type non chaîne lève un `TypeError` déterministe.
Aucun message ne contient la valeur rejetée.

Les bornes 1, 128 et 129, chaque ponctuation autorisée, les quatre ponctuations
interdites en première position, espaces, séparateurs URL, contrôles et Unicode
hors contrat sont couverts par tests.

```text
RESOURCE_REF_CONTRACT_STATUS = IMPLEMENTED
DOMAIN_STATUS = PASS
CANONICAL_IMPLEMENTATION_SHA256 = f33c591de1774cb937e0bdc7d622efbd32f28be6e048669dae67d3e336da634d
```
