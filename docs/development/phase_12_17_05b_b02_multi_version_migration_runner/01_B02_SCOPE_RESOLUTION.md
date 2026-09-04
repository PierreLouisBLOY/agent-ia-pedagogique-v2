# Phase 12.17.5B-B02 — Résolution du périmètre B02

## Lot exécuté

```text
BATCH = B02
CANONICAL_TITLE = Runner de migrations multi-versions
BASELINE_COMMIT = 576d6bd6dcf5082740c4192842b7c87ccbc1f246
B01_ENTRY_GATE = READY
OWNER_DECISION_USED = DM-01 OPTION_A
```

Le lot remplace le chemin d'exécution limité à la seule migration `001` par un registre ordonné et vérifié, sans créer de nouvelle migration. Le contrat accepte une séquence versionnée, authentifie chaque ressource par SHA-256, valide l'historique du ledger comme préfixe ordonné, applique seulement les versions manquantes et s'arrête au premier échec.

## Dans le périmètre

- runner et registre de migrations SQLite ;
- compatibilité de l'injection historique par `Path` ;
- contrat de composition acceptant un registre explicite ;
- tests unitaires, d'intégration locale et d'architecture associés ;
- bases SQLite synthétiques et temporaires exclusivement.

## Hors périmètre

- création ou application de la migration `002` ;
- implémentation de `resource_ref` ;
- implémentation des dimensions `ACTIVE` ou `CANONICAL` ;
- résolution de `ContextOrigin` ;
- modification du seed ou d'une base runtime utilisateur ;
- évolution d'API, appel fournisseur ou secret ;
- démarrage de la Phase 12.17.6.

```text
MIGRATION_002_CREATED = FALSE
DM_02_EXECUTED = FALSE
DM_03_EXECUTED = FALSE
CONTEXT_ORIGIN = UNKNOWN
PROVIDER_CALLS = 0
```
