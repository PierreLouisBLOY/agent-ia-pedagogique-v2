# Phase 12.17.5 — Gate d'entrée 12.17.6

```text
12_17_6_ENTRY_GATE = BLOCKED
BLOCKING_FINDINGS_COUNT = 5
P0_BLOCKERS = 1
P1_BLOCKERS = 3
P2_SUPPORTING_BLOCKERS = 1
```

## Motifs

1. la migration 001 retire le CHECK non négatif de `document.size_bytes` ;
2. elle retire quatre defaults canoniques de `document` ;
3. `resource_ref` n'a pas de borne/format de contrat pour le futur HTTP ;
4. la sémantique publique de `Resource.identity_status` reste indéterminée entre
   `ACTIVE` et `CANONICAL` ;
5. aucun test de migration ne détecte la perte de defaults/contraintes.

## Prochaine sous-étape recommandée

Ouvrir un lot de remédiation strictement borné **avant 12.17.6** :

- spécifier une migration corrective candidate qui restaure exactement le DDL
  canonique de `document` tout en conservant le CHECK SHA-256 ;
- obtenir l'approbation owner avant toute migration ;
- tester la candidate sur une copie runtime fraîche authentifiée ;
- fixer le contrat de borne de `resource_ref` ;
- obtenir une décision owner sur la sémantique exposable de
  `ACTIVE/CANONICAL`, sans inférence depuis les valeurs SQLite.

Cet audit ne crée ni n'exécute ce lot et ne commence pas 12.17.6.
