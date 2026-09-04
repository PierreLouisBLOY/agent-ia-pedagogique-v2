# Phase 12.17.5A — Analyse de borne pour `resource_ref`

## Preuves disponibles

`resource_ref` traverse le Domain, l'Application et le futur contrat READ-15 comme une chaîne opaque non vide. Aucun de ces contrats n'impose aujourd'hui de longueur maximale ni de syntaxe sûre pour un segment de chemin.

Les formes observées dans le dépôt sont :

| Famille observée | Exemple structurel | Longueur observée |
|---|---|---:|
| test historique | `resource:1` | 10 |
| test d'absence | `resource:missing` | 16 |
| seed canonique | `resource-assessment:` + 24 caractères hexadécimaux | 44 |
| génération runtime | `resource:runtime:` + 32 caractères hexadécimaux | 49 |

L'inspection agrégée du seed et du runtime montre 1 399 identifiants, tous de longueur 44, tous préfixés `resource-assessment:`, sans `/`, `?`, `#` ni espace. Aucun contenu pédagogique ni identifiant de ligne n'a été exporté.

Le dépôt possède par ailleurs un précédent technique de borne à 128 caractères pour des identifiants sûrs du harness d'évaluation. Ce précédent n'est pas une autorité métier sur `resource_ref`, mais il établit qu'une enveloppe 128 est déjà comprise et testable dans le codebase.

## `DM-02` — Options à arbitrer

### Option A — Identifiant opaque sûr, 1 à 128 caractères — recommandée

Contrat proposé : `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`.

- couvre toutes les formes observées de longueur 10 à 49 ;
- exclut séparateurs de chemin, query, fragment, espaces et caractères de contrôle ;
- conserve les deux générateurs actuellement visibles ;
- réutilise une enveloppe technique existante sans prétendre qu'elle est déjà canonique pour la ressource.

Confiance : **moyenne**. La compatibilité observée est forte, mais la borne et l'alphabet deviennent une règle métier/API nouvelle et nécessitent une approbation propriétaire explicite.

### Option B — Union fermée de familles versionnées

Autoriser uniquement des formes nommées, par exemple la famille seed `resource-assessment:<24 hex>` et la famille runtime `resource:runtime:<32 hex>`, avec un traitement explicite des références legacy de tests.

Avantage : contrat très précis. Risque : couplage aux générateurs présents, rupture des références legacy et coût de versionnement à chaque nouvelle famille. Confiance : **moyenne-faible** sans inventaire externe exhaustif.

### Option C — Borne seule avec exclusion des caractères URL dangereux

Accepter 1 à 128 caractères, tout en refusant `/`, `?`, `#`, espaces et contrôles.

Avantage : compatibilité maximale avec d'éventuelles familles non observées. Risque : laisse passer une syntaxe plus large et moins canonique que nécessaire. Confiance : **moyenne**.

### Option D — Reporter et garder READ-15 bloqué

Ne pas définir de nouvelle règle tant qu'une autorité externe n'est pas disponible. Confiance : **élevée** sur la conséquence : aucun endpoint public utilisant ce path parameter ne doit alors être ouvert.

## Emplacement recommandé de la règle

Si l'option A, B ou C est approuvée, la règle doit être portée par le bounded context propriétaire de `resource_ref`, puis consommée par :

- les Value Objects/requests Application ;
- le mapping de persistence ;
- l'adaptateur HTTP futur ;
- les tests de limites et de caractères interdits.

Elle ne doit pas être enfouie uniquement dans le routeur HTTP ni placée comme concept spécialisé dans `shared_kernel`.

## Impact migration

Aucune migration n'est justifiée par les données actuellement observées pour l'option A : toutes les valeurs seed/runtime respectent le contrat proposé. Une vérification read-only exhaustive doit néanmoins précéder son activation. Toute valeur non conforme découverte ultérieurement exige une décision de remédiation distincte et fail-closed.
