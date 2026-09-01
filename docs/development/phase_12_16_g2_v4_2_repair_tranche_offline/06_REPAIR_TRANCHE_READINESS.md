# Phase 12.16-G2-V4.2 — Readiness de la repair tranche

## Gate hors ligne

`V4_2_CORRECTIVE_OFFLINE = PASS`

Les invariants suivants sont validés :

- safe report et ledger V4.1 correspondent à leurs SHA-256 attendus ;
- matrice logique V4.2 : 102 calls uniques ;
- carry-forward explicitement démontré : 63 ;
- tranche corrective : 39 calls uniques ;
- partition complète : 63 + 39 = 102 ;
- les trois canaries de famille sont les premiers de leur famille ;
- le Review contract est borné et son hash est verrouillé ;
- pricing et plafond proposé sont recalculés ;
- provenance V4.1/V4.2 reste séparée ;
- aucune autorisation live et aucun plafond approuvé ne sont présents.

## État d'autorisation

`APPROVED_REPAIR_TRANCHE_CEILING_USD = NONE`

`LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`

Le validateur live échoue fermé tant que l'autorisation séparée ne contient pas la
baseline future exacte, le nouveau matrix hash, le pricing hash, un maximum de 39 calls
et un plafond approuvé au moins égal au plafond technique proposé.

## Blockers résiduels avant tout live

1. décision propriétaire explicite sur la tranche de 39 appels, qui remplace
   l'hypothèse initiale de 8 ;
2. freeze/commit ultérieur explicite de cette baseline hors ligne ;
3. approbation exacte du matrix hash, du pricing hash, du nombre d'appels et du plafond ;
4. autorisation de transfert bornée aux projections nécessaires ;
5. autorisation live nouvelle — l'autorisation V4.1 consommée ne peut pas servir.

Aucun de ces blockers n'est contourné par ce lot.
