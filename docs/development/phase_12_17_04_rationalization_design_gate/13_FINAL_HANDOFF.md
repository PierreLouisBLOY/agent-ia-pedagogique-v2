# Projet V2 — Phase 12.17.4 — Handoff du design de rationalisation

## Verdict

```text
PHASE_12_17_04_RATIONALIZATION_DESIGN = PASS
BASELINE_COMMIT = 6d0d66380757d7502fd967cd0246c5b6ff91d5f8
OWNER_DECISIONS_RESOLVED = 8/8
EXTERNAL_SCHEMA_EVIDENCE = AVAILABLE
```

La gate a produit un design exécutable. Elle n'a pas commencé l'implémentation.

## Résultats

```text
ACTIVE_RUNTIME_FILES = 659
ACTIVE_TOOLING_FILES = 30
HISTORICAL_IMMUTABLE_FILES = 40
MISPLACED_IMPLEMENTATION_FILES = 2
RUNNER_PARSER_GENERATIONS = 7
TARGET_ACTIVE_GENERATIONS = 1
MYPY_DIAGNOSTICS_MAPPED_15_OF_15 = TRUE
ROOT_CHANGES = 9
SQLITE_VOCABULARY_FAMILIES_MAPPED = 10
MIGRATION_REQUIRED_TRUE = 0
MIGRATION_REQUIRED_UNKNOWN_CANDIDATES = 2
EXECUTION_BATCHES = 9
HISTORICAL_HASHES_EXPECTED_UNCHANGED = 40
```

## Architecture cible

Le tooling de calibration actif est conçu sous `calibration_tooling/`, séparé
du runtime produit, du harness provider-neutral et des preuves sous `tests/`.
Anthropic dispose d'un nouvel adapter actif écrit contre les contrats durables ;
les fichiers historiques ne sont ni déplacés ni modifiés. Les adaptateurs
OpenAI produit restent sous `backend/adapters/outbound/...`. Un ADR de frontière
est obligatoire avant implémentation.

Le point d'entrée actif cible est `calibration_tooling.runtime.cli`, avec un
seul runner. Les sept générations V4/V5.x restent historiques et hors du graphe
actif.

## Typing

Les 15 diagnostics sont mappés. Les sources historiques restent inchangées et
leur ancienne traversée continue d'être publiée comme dette historique
reproductible. La cible `import-driven = 0` concerne le nouveau graphe actif,
sans ignore, exclude ou stub de masquage. Le backend reste ciblé à `0/659`.

## SQLite

Les dix familles ont un owner bounded context et une traduction adapter cible.
Aucune migration n'est requise par le DDL disponible. Deux analyses restent
`UNKNOWN` : la sémantique `ACTIVE/CANONICAL` de Resource et l'origine technique
encodée dans `pedagogical_context.notes`. Elles sont exclues de 12.17.4E jusqu'à
une décision séparée.

La configuration cible utilise une racine de données résolue par l'OS et les
variables `PROJET_V2_DATA_DIR`, `PROJET_V2_CANONICAL_DB` et
`PROJET_V2_RUNTIME_DB`. Le seed demeure read-only et authentifié ; la runtime est
une copie fraîche, seule cible des migrations, WAL/SHM et backups.

`SQLITE_SIDECAR_ATTRIBUTION_UNDETERMINED` reste ouvert : le fichier principal
était inchangé en 12.17.3D, mais l'absence de snapshot PRE interdit d'attribuer
les sidecars vus en POST. La future gate capture PRE/POST et ne supprime jamais
automatiquement les sidecars du seed.

## Écarts explicités

Sept chemins ont déjà divergé des hashes contenus dans d'anciens manifests
12.16. `git log` rattache ces changements au commit de typing 12.17.2A
`6d0d663...`. Les anciens manifests ne sont pas corrigés rétroactivement ; les
sept hashes courants sont gelés avec les 33 correspondances exactes, soit 40
chemins protégés pour l'exécution future.

Deux fichiers opérationnels Anthropic restent mal placés sous `tests/` :
`transport.py` et `scorer.py`. Leur placement est résolu par création d'un
adapter actif indépendant, pas par déplacement.

## API et gouvernance

- CAP-R02, CAP-A01 et CAP-A02 ont trois owners Application distincts et un ordre
  de livraison explicite.
- Le premier `/api/v2` reste Resource READ-15 read-only et appartient à 12.17.5.
- `version_ref` et `include` sont absents du contrat actif ; toute réintroduction
  requiert un contrat versionné.
- La trace `docs/legacy-review` sera rétrospective, explicitement non rétroactive.
- La policy durable reste blind scoring, strong-only, one-shot/fail-closed,
  lignée certifiée et `RELEASE_THRESHOLD = NONE`.

## Blockers

```text
DESIGN_BLOCKERS = NONE
```

Préconditions de l'exécution : accepter l'ADR `calibration_tooling`, capturer le
snapshot des 40 chemins, et laisser les deux migrations `UNKNOWN` hors scope.
Ce sont des gates de lancement, pas des blockers du design achevé.

## Preuve de non-exécution

```text
CODE_FILES_MODIFIED = 0
SOURCE_RULES_MODIFIED = 0
SQLITE_MODIFIED = 0
PROVIDER_CALLS = 0
COMMIT = NONE
PUSH = NONE
IMPLEMENTATION_STARTED = FALSE
```

## Prochaine sous-étape recommandée

Faire relire et approuver ce design, puis ouvrir `12.17.4E-B01` : ADR de la
frontière active et lock machine-readable des 40 hashes. Ne commencer aucun
autre batch avant le PASS de B01.
