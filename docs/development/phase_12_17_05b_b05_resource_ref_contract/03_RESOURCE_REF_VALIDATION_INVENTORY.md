# Phase 12.17.5B-B05 — Inventaire des validations `resource_ref`

## Avant B05

| Chemin | Validation | Owner | Écart au contrat DM-02/A |
|---|---|---|---|
| `application/dto/input/get_resource.py` | chaîne non vide | Application | longueur/charset absents |
| `application/dto/output/resource_view.py` | chaîne non vide | Application | longueur/charset absents |
| `ports/outbound/resource_store.py` | chaîne non vide | port Resource | longueur/charset absents |
| `adapters/inbound/application/resource_library.py` | type `str` et non vide | inbound | longueur/charset absents |
| `adapters/outbound/resource_library/sqlite.py` | chaîne non vide | adapter | longueur/charset absents |

Ces cinq validations acceptaient notamment `/`, `?`, `#`, espaces, Unicode
hors contrat et plus de 128 caractères. Elles étaient cohérentes entre elles
sur le seul « non vide », mais divergentes du contrat propriétaire approuvé.

```text
RESOURCE_REF_VALIDATOR_COUNT_BEFORE = 5
DIVERGENT_RESOURCE_REF_VALIDATORS_BEFORE = 5
```

## Après B05

Une unique validation exécutable réside dans
`backend/modules/resource_library/domain/value_objects/resource_ref.py`.
Les autres couches reçoivent ou construisent `ResourceRef` et ne possèdent
plus de regex ni de politique de caractères autonome.

Le garde `_text` de l'adaptateur vérifie seulement la forme technique de la
ligne SQLite avant de construire le Value Object; il ne définit pas un contrat
concurrent. Trois regex syntaxiquement identiques déjà présentes dans des
bounded contexts techniques distincts restent hors de l'ownership Resource et
ne sont pas réutilisées implicitement.

```text
RESOURCE_REF_VALIDATOR_COUNT_AFTER = 1
DIVERGENT_RESOURCE_REF_VALIDATORS_AFTER = 0
```
