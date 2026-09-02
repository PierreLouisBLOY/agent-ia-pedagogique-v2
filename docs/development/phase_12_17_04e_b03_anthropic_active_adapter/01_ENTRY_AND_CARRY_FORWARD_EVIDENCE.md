# Phase 12.17.4E-B03 — Entrée et carry-forward

## Bundle d'exécution

- archive : `PHASE_12_17_04E_B03_ANTHROPIC_ACTIVE_ADAPTER.zip` ;
- SHA-256 archive :
  `a39551f5100771b064860fd70c18e3b17219fa9630d733896783ead47d9a3174` ;
- manifeste interne : `6/6 PASS` ;
- instruction exécutée : B03 uniquement, sans B04.

## Gate d'entrée

```text
PHASE_12_17_04E_B02 = PASS
B03_ENTRY_GATE = READY
HEAD = 16d1e90ea8629fa419a93759e4c30ff1c0cb96f0
B02_MANIFEST_SHA256 = 3ea8adb798bfa210608129e98628dc562faa29ca1c375abdb1f6cd972a14fd27
B01_MANIFEST_SHA256 = de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e
ADR_P12_068_STATUS = ACCEPTED
HISTORICAL_FREEZE_PRE = 40/40 PASS
PREEXISTING_DRIFT = 7/7 STABLE
```

Le carry-forward B01 comprend les huit documents référencés par son manifeste,
le manifeste lui-même, l'ADR et son guard, soit `11/11`. Tous les hashes sont
identiques. Les onze fichiers restent non commités et hors du diff B03.

Le manifeste B02 vérifie `11/11`. Le commit B02 exact est le HEAD d'entrée.

## État externe

Les fichiers utilisateur non liés déjà présents dans le worktree sont
préservés. Le seed SQLite n'a été ni ouvert ni modifié ; seul son invariant
documentaire `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134`
est reporté. Aucun credential réel n'a été résolu et aucun provider n'a été
appelé.
