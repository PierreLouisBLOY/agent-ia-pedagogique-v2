# Phase 12.17.5C — Matrice de provenance B02→B07

La matrice ci-dessous couvre exhaustivement les 116 chemins du commit de
consolidation. Les preuves documentaires sont liées par les manifestes propres à
chaque batch. Les fichiers techniques chevauchants conservent leur provenance
cumulative.

| Fichier | Batch d'origine | Preuve | Stagé/commité |
|---|---|---|---|
| `backend/adapters/inbound/application/resource_library.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/adapters/outbound/persistence/migrations.py` | B02+B03 | B02/09; B03/04,09,11 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/adapters/outbound/persistence/vocabulary.py` | B06 | B06/06,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/adapters/outbound/read_models/sqlite.py` | B06 | B06/05,06,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/adapters/outbound/resource_library/sqlite.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/infrastructure/composition/factories/sqlite.py` | B02+B03 | B02/09; B03/01,09 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/application/dto/input/get_resource.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/application/dto/output/resource_view.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/application/queries/get_resource.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/domain/errors/__init__.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/domain/errors/resource_ref.py` | B05+05C EOF | B05/04,05,11; approved one-byte EOF transition | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/domain/value_objects/__init__.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/domain/value_objects/persistence_vocabulary.py` | B06 | B06/04,05,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/domain/value_objects/resource_ref.py` | B05 | B05/03,04,05,11 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/domain/value_objects/resource_semantics.py` | B06 | B06/04,05,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `backend/modules/resource_library/ports/outbound/resource_store.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `database/migrations/002_restore_document_invariants.sql` | B03 | B03/02,04,11 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/01_B02_SCOPE_RESOLUTION.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/02_RUNNER_BEFORE_AFTER.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/03_MIGRATION_REGISTRY_AND_CHECKSUM_CONTRACT.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/04_001_COMPATIBILITY_EVIDENCE.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/05_TRANSACTION_AND_IDEMPOTENCE_EVIDENCE.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/06_TARGETED_TEST_EVIDENCE.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/07_TYPING_AND_ARCHITECTURE_EVIDENCE.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/08_OWNER_DECISION_CONFORMANCE.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/09_DIFF_AND_COMMIT_EVIDENCE.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/10_B03_ENTRY_GATE.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/11_FINAL_HANDOFF.md` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b02_multi_version_migration_runner/MANIFEST_SHA256.txt` | B02 | B02 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/01_B02_CARRY_FORWARD_EVIDENCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/02_B03_SCOPE_RESOLUTION.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/03_FIVE_INVARIANTS_SOURCE_EVIDENCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/04_MIGRATION_002_IMPLEMENTATION.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/05_FRESH_EXISTING_REPLAY_EVIDENCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/06_SCHEMA_AND_DATA_PRESERVATION.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/07_ROLLBACK_AND_CHECKSUM_EVIDENCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/08_SEED_IMMUTABILITY_EVIDENCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/09_TYPING_ARCHITECTURE_TEST_EVIDENCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/10_OWNER_DECISION_CONFORMANCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/11_DIFF_AND_COMMIT_EVIDENCE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/12_B04_ENTRY_GATE.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/13_FINAL_HANDOFF.md` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b03_corrective_migration_002/MANIFEST_SHA256.txt` | B03 | B03 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/01_B04_SCOPE_AND_WRITE_AUTHORIZATION.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/02_B02_B03_CARRY_FORWARD_EVIDENCE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/03_PATH_AND_PRE_SNAPSHOT.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/04_BACKUP_EVIDENCE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/05_REAL_CHAIN_MIGRATION_EVIDENCE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/06_POSTCONDITION_AND_ROW_PRESERVATION.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/07_RECOVERY_REHEARSAL.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/08_SIDECAR_PRE_POST_EVIDENCE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/09_OWNER_DECISION_CONFORMANCE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/10_TYPING_ARCHITECTURE_TEST_EVIDENCE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/11_DIFF_AND_COMMIT_EVIDENCE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/12_B05_ENTRY_GATE.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/13_FINAL_HANDOFF.md` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/MANIFEST_SHA256.txt` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b04_real_chain_recovery/REAL_CHAIN_EVIDENCE.json` | B04 | B04 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/01_B05_SCOPE_RESOLUTION.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/02_CARRY_FORWARD_EVIDENCE.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/03_RESOURCE_REF_VALIDATION_INVENTORY.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/04_CANONICAL_RESOURCE_REF_CONTRACT.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/05_DOMAIN_APPLICATION_PERSISTENCE_PROPAGATION.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/06_API_HANDOFF_ALIGNMENT.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/07_EXISTING_DATA_CONFORMANCE.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/08_TARGETED_TEST_EVIDENCE.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/09_TYPING_ARCHITECTURE_EVIDENCE.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/10_OWNER_DECISION_CONFORMANCE.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/11_DIFF_AND_COMMIT_EVIDENCE.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/12_B06_ENTRY_GATE.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/13_FINAL_HANDOFF.md` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b05_resource_ref_contract/MANIFEST_SHA256.txt` | B05 | B05 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/01_B06_SCOPE_RESOLUTION.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/02_CARRY_FORWARD_EVIDENCE.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/03_ACTIVE_CANONICAL_USAGE_INVENTORY.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/04_TWO_DIMENSION_SEMANTIC_MODEL.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/05_DOMAIN_APPLICATION_ALIGNMENT.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/06_PERSISTENCE_AND_MIGRATION_BOUNDARY.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/07_API_HANDOFF_ALIGNMENT.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/08_EXISTING_DATA_EVIDENCE.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/09_TARGETED_TEST_EVIDENCE.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/10_TYPING_ARCHITECTURE_EVIDENCE.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/11_OWNER_DECISION_CONFORMANCE.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/12_DIFF_AND_COMMIT_EVIDENCE.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/13_B07_ENTRY_GATE.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/14_FINAL_HANDOFF.md` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b06_active_canonical_semantics/MANIFEST_SHA256.txt` | B06 | B06 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/01_B07_SCOPE_RESOLUTION.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/02_CARRY_FORWARD_AND_BINDING_EVIDENCE.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/03_FIVE_BLOCKERS_FINAL_MATRIX.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/04_MIGRATION_P0_REAUDIT.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/05_RESOURCE_REF_REAUDIT.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/06_ACTIVE_CANONICAL_REAUDIT.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/07_READ15_END_TO_END_REAUDIT.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/08_API_HANDOFF_AND_TEST_COVERAGE.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/09_RESIDUAL_FINDINGS_REGISTER.json` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/10_TYPING_ARCHITECTURE_TEST_EVIDENCE.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/11_DIFF_AND_COMMIT_EVIDENCE.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/12_12_17_6_ENTRY_GATE.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/13_FINAL_HANDOFF.md` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `docs/development/phase_12_17_05b_b07_final_reaudit_gate/MANIFEST_SHA256.txt` | B07 | B07 MANIFEST_SHA256.txt + handoff | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/architecture/test_active_canonical_semantics_fitness.py` | B06 | B06/09,10,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/architecture/test_corrective_migration_002_fitness.py` | B03 | B03/09 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/architecture/test_multi_version_migration_runner_fitness.py` | B02 | B02/07,09 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/architecture/test_resource_ref_contract_fitness.py` | B05 | B05/09,11 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/integration/test_resource_library_application_route.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/integration/test_sqlite_resource_application_e2e_real_gate.py` | B05+B06 | B05/08,11; B06/09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/integration/test_sqlite_runtime_real_gate.py` | B02+B03+B06 | B02/06,09; B03/09; B06/09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/integration/test_sqlite_seed_runtime_lifecycle_real_gate.py` | B02+B03+B06 | B02/06,09; B03/09; B06/09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/unit/test_corrective_migration_002.py` | B03 | B03/09 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/unit/test_multi_version_migration_runner.py` | B02+B03 | B02/09; B03/09 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/unit/test_resource_library_get_resource.py` | B05+B06 | B05/05,08,11; B06/05,09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/unit/test_resource_ref_contract.py` | B05 | B05/08,11 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/unit/test_resource_semantics.py` | B06 | B06/09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/unit/test_sqlite_seed_runtime_lifecycle.py` | B02+B03+B06 | B02/06,09; B03/09; B06/09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |
| `tests/unit/test_sqlite_vocabulary_mappings.py` | B06 | B06/09,12 | YES — commit `e2c43184a272491371b73131170db488cf3157d6` |

```text
MATRIX_ROW_COUNT = 116
DOCUMENTARY_FILE_COUNT = 84
TECHNICAL_FILE_COUNT = 32
STAGED_FILES_EXACT_MATCH = TRUE
OUT_OF_SCOPE_STAGED = 0
```
