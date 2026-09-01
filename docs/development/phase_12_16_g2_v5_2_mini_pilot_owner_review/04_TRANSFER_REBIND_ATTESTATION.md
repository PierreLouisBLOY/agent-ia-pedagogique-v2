# Phase 12.16-G2-V5.2 — Ré-attestation de transfert approuvée

## Statut effectif

```text
PEDAGOGICAL_TRANSFER_AUTHORIZED_FOR_V5_2_MINI_PILOT = TRUE
LIVE_PROVIDER_RECALIBRATION_AUTHORIZED = FALSE
```

Cette ré-attestation a été reçue explicitement le `2026-09-01`. Elle autorise le
transfert pédagogique dans le seul périmètre ci-dessous, mais n'autorise aucun
appel live.

## Liaison canonique

- Baseline : `c534b488276eabfa9f82b379282a043cdc0f4b65`.
- Gate V5.2 : `8dc0bdb7ca57c586ac8db887fcb7078e16377e1f8ae30f2d153096ce630c7eea`.
- Scope pédagogique :
  `c65e6460969d3eee4a5fb6a5d99e0a9bfbf3a253efc111ebb64e4af788df0e93`.
- Provider futur unique : `ANTHROPIC_ONLY`.
- Nombre maximal de nouvelles projections : `3`.

## Allowlist de transfert exacte

1. `cal.score.anchor.scn-06.weak.marking-scheme-coherence.r1`
   - call-spec : `a3646f66bd0d274cf30daf3024bbad5d204bb0d8182963460107243a0d81b707`;
   - projection : `8faf88c7f863294591d8ed3c47812db1d69edd8c38aafc98a1345f431f1af2dc`.
2. `cal.v5.pairwise.anchor.scn-06.strong-vs-mixed.marking-scheme-coherence.r1`
   - call-spec : `691794a224c1f440225dca29dddf34aff90c6556210c583263b006607509c196`;
   - projection : `e2eba2625bc6674de898918b330abdab198faceec8f9ec90313ab68983cab0d8`.
3. `cal.v5.pairwise.anchor.scn-01.strong-vs-mixed.clarity.r1`
   - call-spec : `d4143eca0ac6ba40152eecdc5c37cfa7c2f74b3cda39774db79feec54689c0ca`;
   - projection : `8cfea454d79472cd04f9274f8e960db4fa7c7e69b562b7b9f9d673c01acc9b0d`.

Seules les projections pédagogiques minimisées correspondant exactement à cette
allowlist sont autorisées au transfert dans le cadre du mini-pilote V5.2. Les deux
résultats carry-forward Strong et Mixed ne doivent être ni rappelés ni retransmis.
Aucun fichier brut, base SQLite, document source complet, chemin local, credential,
secret, donnée personnelle ou contenu hors scope n'est admis.

Toute différence de baseline, gate, scope, call ID, call-spec ou projection rend
l'attestation inapplicable et ferme la gate.
