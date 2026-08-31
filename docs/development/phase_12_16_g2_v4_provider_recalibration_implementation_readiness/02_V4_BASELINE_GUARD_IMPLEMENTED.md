# 12.16-G2-V4 — Garde de baseline implémentée

## Résultat

`V4_BASELINE_GUARD = PASS` sur les tests hors ligne.

Avant credentials, resolver ou executor réel, la garde vérifie :

1. l'ascendance du commit `a3de3a86f5ddd9afea10d71a277854458a7d4b5f` ;
2. la propreté du worktree pour un live réel ;
3. l'exécution sans erreur de `build_closure_payload(root)` ;
4. le formulaire `5748b0f223b3039b463f975de8d99772a9f18ad729535a73bd27dfcfc27042a6` ;
5. le corpus `9c8e262028f1d63fa50963f2f8bcb742e4c24d4e106a73244861416f826ca034` ;
6. trace, Gate A, Gate B, prévalidation humaine et statut méthodologique PASS.

Chaque invariant possède un arrêt fail-closed distinct. Les tests couvrent séparément commit absent, worktree dirty, clôture invalide, formulaire, corpus, trace, Gate A, Gate B, statut humain et statut méthodologique.

Le point d'entrée `run_live_calibration()` exécute cette garde et les autres gates avant d'instancier `RealCalibrationExecutor`. L'absence actuelle d'approbation propriétaire arrête également avant cette construction.
