# Phase 12.17.5A — Analyse sémantique `ACTIVE` / `CANONICAL`

## État des preuves

Le type Domain `ResourceIdentityStatus` expose deux valeurs distinctes, `ACTIVE` et `CANONICAL`. Le mapping de persistence les conserve distinctes et les tests de round-trip démontrent seulement cette fidélité technique. Aucun invariant métier, transition ou règle de sélection n'établit leur relation.

L'inspection read-only agrégée du seed et du runtime donne :

| Valeur | Nombre de ressources |
|---|---:|
| `ACTIVE` | 1 399 |
| `CANONICAL` | 0 |

Les deux bases présentent les mêmes comptes. Le schéma persistant utilise `ACTIVE` comme valeur par défaut et n'impose pas de `CHECK` sur ce vocabulaire. Un test d'intégration crée par ailleurs une ressource `CANONICAL`, ce qui prouve l'acceptation technique de la valeur, pas sa signification métier.

Conclusion de preuve : `ACTIVE` est la seule valeur observée dans les données canoniques courantes. La sémantique de `CANONICAL`, son éventuelle coexistence avec `ACTIVE` et les transitions autorisées restent **inconnues**.

## `DM-03` — Options à arbitrer

### Option A — Deux états exclusifs d'un même cycle de vie

Définir une machine d'état explicite, par exemple `ACTIVE -> CANONICAL`, avec règles d'autorité, réversibilité et effets sur la lecture. Cette option minimise le changement de représentation mais suppose qu'une ressource canonique n'est plus active, hypothèse non prouvée.

Confiance : **faible** sans source métier supplémentaire.

### Option B — Séparer disponibilité et canonicalité — recommandée

Traiter `ACTIVE` comme un état de disponibilité/cycle de vie et représenter la canonicalité dans une dimension séparée, seulement après définition propriétaire de son autorité et de ses transitions.

- aucun des 1 399 enregistrements `ACTIVE` ne doit être reclassé par inférence ;
- aucun backfill `CANONICAL` ne peut être inventé ;
- le champ ambigu ne doit pas être publié par READ-15 tant que sa nouvelle projection n'est pas définie ;
- un changement de schéma éventuel doit utiliser une migration séparée de la corrective `002`.

Confiance : **moyenne**. Les libellés désignent naturellement deux axes différents et les données sont compatibles, mais cette interprétation doit rester une décision propriétaire.

### Option C — Déprécier `CANONICAL`

Conserver uniquement le cycle de vie `ACTIVE` dans la persistence et l'API, puis supprimer progressivement la valeur inutilisée. Cette option correspond aux données observées, mais peut effacer une intention canonique encore non documentée.

Confiance : **moyenne-faible**.

### Option D — Reporter et garder l'exposition bloquée

Conserver le modèle interne actuel sans publier `identity_status` dans READ-15. Cette option évite une hypothèse métier, mais ne résout pas le contrat API audité.

Confiance : **élevée** sur la conséquence de gate.

## Conséquences conditionnelles

| Choix | Code Domain/Application | Migration | API READ-15 |
|---|---|---|---|
| A | machine d'état et invariants | possiblement non, selon contraintes approuvées | état unique documenté |
| B | deux concepts et mappings distincts | probable si une nouvelle colonne est retenue | champs non ambigus, versionnés |
| C | dépréciation puis retrait | possible nettoyage ultérieur | `CANONICAL` absent |
| D | aucun changement immédiat | non | endpoint/field bloqué |

La décision doit précéder toute modification. Une migration issue de `DM-03`, si nécessaire, ne doit pas être fusionnée avec la migration corrective des cinq invariants de `document`.

## `ContextOrigin`

L'audit ne fournit aucune nouvelle preuve métier permettant de résoudre `ContextOrigin`. Le mapper valide actuellement le concept technique disponible puis renvoie `None`; aucune colonne correspondante n'existe dans le schéma observé.

Décision de ce lot :

```text
CONTEXT_ORIGIN_SEMANTICS = UNKNOWN
CONTEXT_ORIGIN_MIGRATION_REQUIRED = FALSE
```

Toute évolution future requiert une source canonique ou une décision propriétaire distincte. Aucune valeur ne doit être inférée à partir du runtime.
