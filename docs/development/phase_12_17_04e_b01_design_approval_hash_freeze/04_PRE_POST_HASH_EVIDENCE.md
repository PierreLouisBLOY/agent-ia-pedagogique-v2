# Phase 12.17.4E-B01 — Preuve de stabilité PRE/POST

## Périmètre et méthode

- baseline liée : `6d0d66380757d7502fd967cd0246c5b6ff91d5f8` ;
- population : les 40 chemins historiques inscrits dans
  `03_HISTORICAL_HASH_FREEZE.json` ;
- algorithme : SHA-256 sur les octets de chaque fichier ;
- capture PRE : `2026-09-02T17:17:45.3647865Z`, avant les écritures B01 ;
- capture POST : `2026-09-02T17:20:29.8565507Z`, après l'ADR et le registre B01 ;
- ordre de l'agrégat : ordre des entrées du registre JSON, chaque ligne étant
  encodée comme `path<TAB>sha256<LF>` ;
- SHA-256 agrégé PRE :
  `ee220e8deaee46b3e5c0f43932238600b4a54ab941ceb80f1b175995b2565ab5` ;
- SHA-256 agrégé POST :
  `ee220e8deaee46b3e5c0f43932238600b4a54ab941ceb80f1b175995b2565ab5`.

## Résultat exhaustif

| ID | Chemin | SHA-256 PRE et POST | Résultat |
|---|---|---|---|
| HIST-001 | `tests/calibration/pedagogical/anchor_corpus_v2.py` | `bd0c5eff43be20b4f578b99321e076471804f8a3e0e197858b08a3701800be76` | PASS |
| HIST-002 | `tests/calibration/pedagogical/anchor_corpus_v4.py` | `b0a86640502db4ab1d0b623e50faffa45178d9e93b0a24976df3312d460662be` | PASS |
| HIST-003 | `tests/calibration/pedagogical/call_plan.py` | `1272776fb72545cd4ca840d7088c26d7e272d6cc05100eb2344394df3e3b6df6` | PASS |
| HIST-004 | `tests/calibration/pedagogical/call_plan_v4_1.py` | `93f996be10af46fe6313bf49c873bbd752001bd0d816de79c2079cb3f71eb1b2` | PASS |
| HIST-005 | `tests/calibration/pedagogical/legacy_call_plan.py` | `cb7a92ec9fc8d214975cb3ad68f27ab1328866132ca63686b636264e21d31e3a` | PASS |
| HIST-006 | `tests/calibration/pedagogical/live_runner.py` | `8c7f88726f270d65c2080110d25bb421c42da56cd930d43f646343b3e463ba40` | PASS |
| HIST-007 | `tests/calibration/pedagogical/live_runner_v4_1.py` | `bf354170c3c9a864b715ec5c7094e76ef87a1dcb9a20dbb069c3e91be9ee0dca` | PASS |
| HIST-008 | `tests/calibration/pedagogical/metrics.py` | `fd58c668eb32d259f40f05a374db5a952b1d11eaa72f767966888ed2825720a8` | PASS |
| HIST-009 | `tests/calibration/pedagogical/offline_calibration_v5.py` | `328d10c3ef8e3041e0d2dd9919267092dfcf53463c9f725cb432333ea6a23d04` | PASS |
| HIST-010 | `tests/calibration/pedagogical/pairwise_output_contract_v5_2_3.py` | `bde7afa85eaaf0ec0fee4beae9752e4511ae048b79afce26e56c8d8abef023ec` | PASS |
| HIST-011 | `tests/calibration/pedagogical/pairwise_output_contract_v5_2_4.py` | `3f47351e8d188ddd7ed465a3d139cad8fd55c03c274ae259a385eaaf3a953a56` | PASS |
| HIST-012 | `tests/calibration/pedagogical/pairwise_runner_v5_2_2.py` | `ec72fd6d0e8ed7aa3fff0b8d05ce678148041e2be7de8b86478855cbfc57ecf0` | PASS |
| HIST-013 | `tests/calibration/pedagogical/pricing.py` | `fbfa2b166d473b5f036da8005896f986e1af52db11764faf853163129b0c2e40` | PASS |
| HIST-014 | `tests/calibration/pedagogical/protocol.py` | `ab01dfdd6b1b0e704d8465d56a30e686f40f4b5a054780710db3cd55cce6e887` | PASS |
| HIST-015 | `tests/calibration/pedagogical/r2a_diagnostic.py` | `49a6e436619807a60d0adc4cd3290cf4a0ef43b8213c76fb6610c544a9294868` | PASS |
| HIST-016 | `tests/calibration/pedagogical/r3a_plan.py` | `e04bd7a6805d0f07570515aac7434accf614f407ccc001a2dbd66bc5e1ef0497` | PASS |
| HIST-017 | `tests/calibration/pedagogical/r3b_r1_diagnostic.py` | `0d05a17548a0b12c8ced1c2f52f0ff1a3614474ee7e972f37e2abea91ba9a371` | PASS |
| HIST-018 | `tests/calibration/pedagogical/r3b_r3_plan.py` | `3b99dfcc85668e7659182a49b5cc694bd3ce55c51c7681f33eda73064cf1b6c3` | PASS |
| HIST-019 | `tests/calibration/pedagogical/r4_r1_policy.py` | `ace00ca77da871fd7b7862e571a750641f601d3a06f32152e173527ce0c4f960` | PASS |
| HIST-020 | `tests/calibration/pedagogical/repair_tranche_v4_2.py` | `d1e5b40dd1437aad38f5da0db4797e2670da953ee554f09f4aa1b1f078e9a6b6` | PASS |
| HIST-021 | `tests/calibration/pedagogical/reuse_audit.py` | `015e59877624682da8461be0333852dda6caa2469936e7dac23c6cc3d554eeba` | PASS |
| HIST-022 | `tests/calibration/pedagogical/review_contract_v4_2.py` | `81cc15e087169290133c7ecd79ba7c7043935673522229a1d861e86e28ef1a9e` | PASS |
| HIST-023 | `tests/calibration/pedagogical/scorer_contract_v5.py` | `85797a5c2be668444bf5720153d94a01cd8bdf4e1789154874865ecd4d07d4a4` | PASS |
| HIST-024 | `tests/calibration/pedagogical/semantic_gate_v5_2.py` | `f4eaddf64eb255edcfdd011a763cefe83afe96c97a47f90519952ae2bfe02bb3` | PASS |
| HIST-025 | `tests/calibration/pedagogical/semantic_integration_v5.py` | `4347094a9fa31787ca8fc7eb31c848151506a5197457e1ffc4d6e114031b8ca4` | PASS |
| HIST-026 | `tests/calibration/pedagogical/semantic_micro_canary_v5_1.py` | `d3ae157dada67046dc0999b0b13d24dc8be02e14e0471d4a37fc9f4df25b77e4` | PASS |
| HIST-027 | `tests/calibration/pedagogical/semantic_mini_pilot_v5_1.py` | `33eb2a9e085238f88f7f36ae3ca3f51d08301e4accbc4eafad4fc5aaf6c19a1c` | PASS |
| HIST-028 | `tests/calibration/pedagogical/semantic_parser_adapter_v5_1.py` | `4788eac744537c7c0b229abef9d440b4b470a1f1279ceff4f9e68e41955e2115` | PASS |
| HIST-029 | `tests/calibration/pedagogical/semantic_pilot_freeze_v5.py` | `eaed483486a00a7937832795f26b29b1adbc344c4578385fcab33189c5c4a2c1` | PASS |
| HIST-030 | `tests/calibration/pedagogical/test_v4_corrective_attestation_closure.py` | `d5d55942059d5f58160868de6c242fbcc3f0c32c3914e245f78dc549b88a035f` | PASS |
| HIST-031 | `tests/calibration/pedagogical/test_v4_human_disposition_pairwise_reconciliation.py` | `2e819fd11f6ebddb70ce4d27e8498de432453514491a5d144a2e199e3d803e54` | PASS |
| HIST-032 | `tests/calibration/pedagogical/test_v4_provider_recalibration_implementation_readiness.py` | `bcae37cb478d0b1eeedc49463f30157a412b76764a9f2c391dcb22d4b0e34435` | PASS |
| HIST-033 | `tests/calibration/pedagogical/test_v4_provider_recalibration_plan_readiness.py` | `d8fb3909bebee55e9aa4351a6550fb7715864bcf41cac04ff3cc5504b94824f6` | PASS |
| HIST-034 | `tests/calibration/pedagogical/v4_human_disposition_pairwise_reconciliation.py` | `2502e5b872924b400bef4090e25e66126bd1ec1b88072c628fe774c143630e91` | PASS |
| HIST-035 | `tests/calibration/pedagogical/v4_provider_recalibration_implementation_readiness.py` | `5299c018d7b25050b0ee9cb626b3cd561dba59d38fde7b30c9fe7e70858c6ba9` | PASS |
| HIST-036 | `tests/calibration/pedagogical/v4_provider_recalibration_plan_readiness.py` | `34b0c26e69be928eb22b2364adce4880d147f0ad5325f6bf2e4ddc03254e7a8f` | PASS |
| HIST-037 | `tests/providers/anthropic/contracts.py` | `668fa89013fe053201dd971060cd8a1036378f8f863085a8e80ac5baef4e90f8` | PASS |
| HIST-038 | `tests/providers/anthropic/mapping.py` | `970da3e243b7241b858c5ad3d33a01bdb30815b753008a208790b0d9b2e9a633` | PASS |
| HIST-039 | `tests/providers/anthropic/scorer.py` | `3be22f3a4ee19a3e2095f52f459b30d0b204a7e37437b2e5b33ab0ee03a76119` | PASS |
| HIST-040 | `tests/providers/anthropic/transport.py` | `15ecf4b27ac8840dc503201864614a304917d3d43132b159da6a520044787b5b` | PASS |

## Verdict

`PRE_POST_IDENTICAL = 40/40 PASS`

Zéro octet des 40 fichiers historiques n'a été modifié par B01.
