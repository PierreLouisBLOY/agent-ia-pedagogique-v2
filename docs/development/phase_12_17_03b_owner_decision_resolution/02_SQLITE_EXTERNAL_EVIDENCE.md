# Phase 12.17.3B — SQLite external evidence

## Verdict

```text
EXTERNAL_SCHEMA_EVIDENCE = MISSING
EXPECTED_SQLITE_PATH = NOT_DOCUMENTED_IN_AUTHORIZED_12_17_3A_SOURCES
EXPECTED_SQLITE_SHA256 = NOT_DOCUMENTED_IN_AUTHORIZED_12_17_3A_SOURCES
LOCAL_FILE_AVAILABILITY = NOT_EVALUABLE_WITHOUT_UNAMBIGUOUS_IDENTITY
ACTUAL_SQLITE_SHA256 = NOT_COMPUTED
ACTUAL_TABLE_COUNT = NOT_CHECKED
SQLITE_FILE_OPENED = FALSE
SQLITE_WRITE_OR_MIGRATION = FALSE
```

`06_EXTERNAL_EVIDENCE_REQUIREMENTS.md` exige un locator absolu fourni par le propriétaire, le SHA-256 attendu et la taille du seed exact. Ces trois éléments ne sont pas documentés dans les sources autoritatives 12.17.3A ; aucun fichier local ne peut donc être identifié sans ambiguïté.

Conformément au prompt, aucun substitut, ancienne base ou chemin connu par analogie n’a été recherché ou utilisé. L’inventaire annoncé `98 tables / 20 indexes / 7 triggers / 2 views` reste une attente documentaire, pas une observation vérifiée dans ce lot.

## OD-05 — Preuve du schéma externe

`EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE`

### DECIDABLE_NOW

- Choisir A : autoriser ultérieurement une introspection read-only liée à l’identité exacte.
- Choisir B : accepter explicitement l’écart de preuve pour ce cycle.
- Choisir C : fournir ultérieurement un export schema-only signé et minimisé.
- Choisir DEFER : conserver toutes les affirmations structurelles bloquées.

### CONDITIONAL_ON_SQLITE_EVIDENCE

- valider le nombre réel de tables/indexes/triggers/vues ;
- confirmer PK, FK, unicité, checks, nullabilité et indexes des neuf règles affectées ;
- confirmer les préconditions de la migration locale sans l’exécuter ;
- passer un mapping de `EXTERNAL_SCHEMA_EVIDENCE_REQUIRED` à vérifié.

Éléments de schéma nécessaires : structures `resource`, `document`, notion/contexte, session/task/production, validation, qualité, promotion et audit ; contraintes de transition/identité/lignée ; cible exacte de la migration SHA-256.

## OD-06 — Propriété des littéraux/defaults

`EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE`

### DECIDABLE_NOW

- Le propriétaire peut choisir A, B ou C comme modèle d’ownership, ou DEFER.
- Il peut interdire immédiatement que les littéraux d’adapter soient interprétés comme autorité métier.
- Il peut fixer le principe que `shared_kernel` ne reçoit aucun vocabulaire métier spécialisé.

### CONDITIONAL_ON_SQLITE_EVIDENCE

- aligner chaque enum/value object sur les valeurs et contraintes réellement stockées ;
- déterminer si une traduction adapter suffit ou si une migration est nécessaire ;
- valider les transitions et valeurs par défaut ;
- clôturer `CR-015 ALIGN_DATA_MODEL`.

Éléments nécessaires : colonnes, defaults et contraintes associées aux dix familles notion, document, resource, context, session, task, production, validation, quality/promotion et audit.

## OD-07 — READ-15 version/include

`EXTERNAL_SCHEMA_EVIDENCE_REQUIRED = TRUE`

### DECIDABLE_NOW

- Option A, dépréciation du scope actif : décidable sans SQLite.
- Option B, noms réservés avec rejet fail-closed : décidable sans SQLite.
- DEFER : décidable sans SQLite, mais reste bloquant pour READY sans exclusion explicite du scope.
- Le besoin produit et l’autorité de `OD-01` peuvent être décidés sans ouvrir la base.

### CONDITIONAL_ON_SQLITE_EVIDENCE

- Option C seulement : définir la résolution de `version_ref`, les relations incluses, leur cardinalité et l’allowlist ;
- vérifier si le modèle externe contient version, lignée et relations nécessaires ;
- déterminer si une migration serait requise ;
- concevoir le mapping Application/API sans inventer la structure.

Éléments nécessaires : identité/version de resource, tables ou relations de version/lignée, relations candidates pour `include`, contraintes d’intégrité et indexes de lookup.

## Condition pour une future vérification

Une nouvelle étape de preuve devra fournir explicitement : chemin absolu, SHA-256 attendu, taille, autorisation read-only et périmètre schema-only. Sans ces éléments, l’état reste `MISSING` et aucune option conditionnelle ne peut être déclarée satisfaite.
