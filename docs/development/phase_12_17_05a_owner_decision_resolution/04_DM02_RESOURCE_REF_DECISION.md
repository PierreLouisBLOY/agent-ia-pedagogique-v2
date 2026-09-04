# DM-02 — Borne et syntaxe de `resource_ref`

## Problème et preuves

Le contrat Domain/Application exige actuellement une chaîne non vide, sans borne ni syntaxe sûre pour un futur segment de route. Les longueurs prouvées sont 10, 16, 44 et 49. Dans le seed et le runtime, les 1 399 valeurs agrégées ont une longueur de 44, le préfixe `resource-assessment:` et aucun `/`, `?`, `#` ou espace. Une borne à 128 existe comme précédent technique pour des identifiants sûrs ailleurs dans le dépôt; elle n'est pas encore une autorité métier sur `resource_ref`.

Finding couvert : `DMAPI-003`.

## Options exactes du registre

### Option A

> Approve a resource-owned safe opaque identifier matching ^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$

- Règle : 1 à 128 caractères; premier caractère alphanumérique; suite alphanumérique ou `.`, `_`, `:`, `-`.
- Preuve/compatibilité : couvre toutes les formes observées de longueur 10 à 49 et exclut les séparateurs URL dangereux observés comme absents.
- API : path parameter borné et sûr; validation avant le use case.
- Persistence : validation portée par le bounded context et réutilisée par les mappings; aucune modification SQLite attendue.
- Migration data requise : **FALSE** selon les données actuellement inspectées; revalidation exhaustive read-only avant activation.
- Tests : longueurs 1/128/129, premier caractère, alphabet autorisé, `/ ? #`, espaces, contrôles, formes seed/runtime et références legacy.
- Risque : rejeter une famille externe non inventoriée; la valeur 128 reste une nouvelle règle owner malgré son précédent technique.

### Option B

> Approve a closed, versioned union of known identifier families

- Règle : allowlist versionnée des familles connues, notamment `resource-assessment:<24 hex>` et `resource:runtime:<32 hex>`, avec traitement explicite du legacy.
- Preuve/compatibilité : précision maximale pour les deux générateurs prouvés; les références de tests `resource:1` et `resource:missing` nécessitent une décision de compatibilité.
- API : validation très stricte et versionnée.
- Persistence : décodage/validation par famille dans le bounded context.
- Migration data requise : **CONDITIONAL_ON_DISCOVERED_LEGACY_VALUES**.
- Tests : un jeu positif/négatif par famille, version inconnue, casse hexadécimale et legacy.
- Risque : fort couplage aux générateurs actuels et coût d'évolution pour chaque nouvelle famille.

### Option C

> Approve only a 1..128 length bound plus rejection of path, query, fragment, whitespace and control characters

- Règle : enveloppe 1 à 128; refus de `/`, `?`, `#`, whitespace et contrôles; reste de l'alphabet ouvert.
- Preuve/compatibilité : couvre toutes les formes observées et le précédent de borne 128 avec moins de restrictions syntaxiques.
- API : réduit les risques de routage, logging et entrées non bornées.
- Persistence : contrôle Domain/Application simple; schéma inchangé.
- Migration data requise : **FALSE** selon les valeurs observées.
- Tests : bornes, caractères interdits, Unicode/autres caractères autorisés selon le contrat exact.
- Risque : accepte davantage de formes ambiguës ou difficiles à normaliser que l'option A.

### Option D

> Defer the contract and keep READ-15 blocked

- Règle : aucune nouvelle règle.
- Compatibilité/persistence : aucun changement.
- API : aucun endpoint public utilisant ce path parameter ne peut être ouvert.
- Migration data requise : **FALSE**.
- Tests : dette de validation conservée.
- Risque : `DMAPI-003` reste ouvert et 12.17.6 reste bloquée.

## Recommandation Codex

```text
DM_02_RECOMMENDATION = OPTION_A
DM_02_CONFIDENCE = MEDIUM
```

Raison : l'option A offre une règle déterministe, compatible avec toutes les preuves locales et appropriée à un segment d'API. La confiance reste moyenne car la borne et l'alphabet deviennent une nouvelle autorité métier et aucun inventaire externe exhaustif n'est disponible.

La règle approuvée doit appartenir au bounded context ressource, puis être consommée par Application, persistence et le futur adaptateur HTTP; elle ne doit pas être spécialisée dans `shared_kernel`. Aucune option n'est sélectionnée automatiquement.
