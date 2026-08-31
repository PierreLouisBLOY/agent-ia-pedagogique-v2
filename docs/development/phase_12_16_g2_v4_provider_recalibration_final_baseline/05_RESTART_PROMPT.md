# Prompt de reprise — après baseline finale offline 12.16-G2-V4

Reprendre sur la branche `phase12/12-16-provider-model-calibration` depuis la baseline locale validée le 2026-08-31.

La configuration est approuvée : matrice `f159f200bf45d9df631007dd742e6ea9cc44a3e487ed76180f92c1392cd6245e`, pricing `31f2a9287845da8986448f62abe312b2290af5e9578ff61643d1cb0045bfe1b8`, 102 appels maximum et plafond `3.251640 USD`. La suite globale offline est verte : `4445 passed, 3 skipped`.

Maintenir impérativement `LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE`. Ne résoudre aucun credential, ne construire aucun transport, n'effectuer aucun appel fournisseur et ne modifier aucune route runtime sans autorisation propriétaire live distincte et explicite.

Ne pas commit ni pousser sans instruction explicite du propriétaire.
