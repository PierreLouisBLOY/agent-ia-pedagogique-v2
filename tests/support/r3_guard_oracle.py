"""Independent, closed R3 owner-approved oracle; no runtime authorization."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

R3_BASELINE = "817ad474d93c78c602a22bd30cf77fe7621e68b1"
R3_MANIFEST = "b9f90be754a2e7dc359087675e23ec4284673e9e5336fe742ecf286a1ddba211"
R3_CONTRACT = "docs/development/phase_12_18_h2_r3_review_modify/R3_HTTP_LOCAL_V1.json"
R3_PATHS = (
    "backend/adapters/inbound/api/routes.py",
    "backend/adapters/inbound/api/server.py",
    "backend/adapters/outbound/persistence/conversation_memory.py",
    "backend/infrastructure/composition/factories/conversation.py",
    "backend/infrastructure/composition/factories/local_browser.py",
    "backend/adapters/inbound/cli/local_browser.py",
    "frontend/index.html",
    "frontend/app.js",
    "frontend/styles.css",
    "tests/architecture/test_local_browser_product_boundary.py",
    "tests/architecture/test_local_search_product_boundary.py",
    "tests/architecture/test_resource_ref_contract_fitness.py",
    "tests/architecture/test_security_recovery_observability_e2e_fitness.py",
    "tests/architecture/test_conversation_product_boundary.py",
    "tests/unit/test_local_browser_product_routes.py",
    "backend/modules/pedagogical_design/contracts/dto/assessment_bundle.py",
    "backend/modules/pedagogical_design/contracts/dto/assessment_revision.py",
    "backend/modules/pedagogical_design/domain/policies/assessment_revision.py",
    "backend/modules/pedagogical_design/ports/outbound/assessment_revision.py",
    "backend/modules/pedagogical_design/ports/inbound/revise_assessment.py",
    "backend/modules/pedagogical_design/application/commands/revise_assessment.py",
    "backend/modules/validation_control/contracts/dto/deterministic_validation.py",
    "backend/modules/validation_control/domain/policies/assessment_checks.py",
    "backend/modules/validation_control/ports/inbound/validate_assessment.py",
    "backend/modules/validation_control/application/commands/validate_assessment.py",
    "backend/modules/work_orchestration/contracts/dto/r3_review_modify.py",
    "backend/modules/work_orchestration/ports/inbound/r3_review_modify.py",
    "backend/modules/work_orchestration/ports/outbound/r3_store.py",
    "backend/modules/work_orchestration/ports/outbound/r3_job.py",
    "backend/modules/work_orchestration/application/services/r3_review_modify.py",
    "backend/adapters/inbound/application/r3_review_modify.py",
    "backend/adapters/inbound/api/r3_review_modify.py",
    "backend/adapters/outbound/generation/assessment_revision.py",
    "backend/adapters/outbound/review/assessment_review.py",
    "backend/adapters/outbound/system/r3_job.py",
    "backend/infrastructure/composition/bindings/r3_agents.py",
    "backend/infrastructure/composition/bootstrap/r3_worker.py",
    "backend/infrastructure/composition/factories/r3_review_modify.py",
    "tests/support/r3_synthetic.py",
    "tests/support/r3_fakes.py",
    "tests/support/r3_guard_oracle.py",
    "tests/unit/test_assessment_bundle.py",
    "tests/unit/test_assessment_deterministic_validation.py",
    "tests/unit/test_assessment_revision.py",
    "tests/unit/test_r3_review_mapping.py",
    "tests/unit/test_r3_generation_mapping.py",
    "tests/unit/test_r3_commands.py",
    "tests/unit/test_r3_routes_security.py",
    "tests/unit/test_r3_assets.py",
    "tests/integration/test_r3_product.py",
    "tests/integration/test_r3_http.py",
    "tests/integration/test_r3_jobs.py",
    "tests/architecture/test_r3_product_boundary.py",
    "tests/architecture/test_r3_guard_non_regression.py",
    "architecture/adr/ADR-conversational-review-modify-product-boundary.md",
    "docs/development/phase_12_18_h2_r3_review_modify/R3_HTTP_LOCAL_V1.json",
    "docs/development/phase_12_18_h2_r3_review_modify/IMPLEMENTATION_EVIDENCE.md",
    "docs/development/phase_12_18_h2_r3_review_modify/LIVE_SCOPE_PROPOSAL.json",
    "docs/development/phase_12_18_h2_r3_review_modify/MANIFEST_SHA256.txt",
)
R3_ROUTES = (
    (
        ("GET",),
        "/api/v2/resources/{resource_ref}",
        None,
    ),
    (
        ("GET",),
        "/api/v2/search",
        None,
    ),
    (
        ("GET",),
        "/api/v2/conversation",
        None,
    ),
    (
        ("POST",),
        "/api/v2/conversation/messages",
        None,
    ),
    (
        ("POST",),
        "/api/v2/conversation/generations",
        None,
    ),
    (
        ("GET",),
        "/api/v2/productions/{production_ref}/versions/{version_ref}",
        None,
    ),
    (
        ("POST",),
        "/api/v2/conversation/assessment-preparations",
        None,
    ),
    (
        ("POST",),
        "/api/v2/conversation/reviews",
        None,
    ),
    (
        ("GET",),
        "/api/v2/conversation/reviews/{review_ref}",
        None,
    ),
    (
        ("POST",),
        "/api/v2/conversation/validations",
        None,
    ),
    (
        ("POST",),
        "/api/v2/conversation/modifications",
        None,
    ),
    (
        ("GET",),
        "/api/v2/conversation/operations/{operation_ref}",
        None,
    ),
    (
        ("GET",),
        "/api/v2/productions/{production_ref}/versions/{version_ref}/assessment",
        None,
    ),
    (
        (
            "GET",
            "HEAD",
        ),
        "/",
        "index.html",
    ),
    (
        (
            "GET",
            "HEAD",
        ),
        "/assets/app.js",
        "app.js",
    ),
    (
        (
            "GET",
            "HEAD",
        ),
        "/assets/styles.css",
        "styles.css",
    ),
)
PRE_HASHES = {
    "backend/adapters/inbound/api/routes.py": "a0b28cbddca5a161867e1436e93814e78058482ca42309b47f78f3609719dcc7",
    "backend/adapters/inbound/api/server.py": "9c52906d5aa2842fb143ec2340bf9981a9d8c1a1bb53e225290ad23b5d38d9ab",
    "backend/adapters/outbound/persistence/conversation_memory.py": "d22e0357f52ee3ae9c107f379a141ecdd54fb729333aab279ac2e4f3766abf4c",
    "backend/infrastructure/composition/factories/conversation.py": "db2cfbbc46a370ff402c585f76a2faf929635609ff6c11c18372a6f47f74462f",
    "backend/infrastructure/composition/factories/local_browser.py": "187d25613d9234264f13d9a555c67c229f09cd072dd4b1cf1a52d3aaf277aa39",
    "backend/adapters/inbound/cli/local_browser.py": "5aad3a77581f3d4fa1b1b1860d429115363cac182a7e7091713c39abba3236b4",
    "frontend/index.html": "94a5613bdbfb8e6c76f20c6934f4b63442f354262f9b7960bae63dc86eff833f",
    "frontend/app.js": "172da3bee09ff7da73bd08ec09b9850fbcc8cfb02868d422d3063f44708ff61e",
    "frontend/styles.css": "6de4e923bb067ad4cff3844de2a489b143788b760f1624995f6639710186829a",
    "tests/architecture/test_local_browser_product_boundary.py": "0314ac3cbfe75ef65391ce8b3520117d01ebdde7307c5b9388253b27e347b256",
    "tests/architecture/test_local_search_product_boundary.py": "d0b3781596cba9001bb18ee6b03a0a77f0084e119a83d8bfe8c4200eec6e20e0",
    "tests/architecture/test_resource_ref_contract_fitness.py": "30129394db8ba1bbc3ca220824d6e0e8bd1c9894cab9f8a4e7214e2d6e50b227",
    "tests/architecture/test_security_recovery_observability_e2e_fitness.py": "252af97bf10d13e6279c54b0084019fe911bcad3634476c1acf59ed3d05d5554",
    "tests/architecture/test_conversation_product_boundary.py": "c58e8f8feb14f455a6ba14b5bcafea2d7e853b9df239e78f6cbb8305a141e442",
    "tests/unit/test_local_browser_product_routes.py": "56c91b80ab76ffe8db5eb6356de1f18743522f1ebf5453eb4b00c5910cf80499",
}
READ_ONLY = {
    "backend/agent_runtime/agents/review/review_agent.py": "34ee91cbedaf2360d4e4f8d41a1aeb56b4deb4c039b96153640f6a5e9228f959",
    "backend/agent_runtime/agents/review/review_model.py": "3f5846c458a5ef132ef1fea7e9feb09c127ba16c6dd90d0fa1ad5c4e1e079bc9",
    "backend/agent_runtime/agents/review/review_ports.py": "42ad6ad7516a9c4bef42c15295a16af8e724d3163197ef114f25bee0dfd31d22",
    "backend/agent_runtime/contracts/review/review_result.py": "58b9cb3e93d5711035c8ae85906dffdb5c93a3bc49af3e0f0d0a3137c22fced9",
    "backend/agent_runtime/contracts/review/finding.py": "1ebc6cfc0d429a62f6abe1c35b23b23533cf1932d5d0792fc339ba1e420bda37",
    "backend/agent_runtime/agents/generation/generation_agent.py": "187a3fd2565ed7a94e392830bcf5ecde0e82cf38823a0665d92967f4b5bec42c",
    "backend/agent_runtime/agents/generation/generation_model.py": "b943f3a660691ff68f197ad53e1d1b1bc9f90501cc29c39f9c045fad62184128",
    "backend/agent_runtime/registry/capabilities.py": "4467bc96d8e8df81ee8a5a66b24853d43b3ca569972fc55a3552c9dfea8bb5bf",
    "backend/modules/work_orchestration/contracts/dto/production_read_view.py": "a01e51387c11c6749c57f1f1d25a41121e72cc3d5d1e0c713c7ec57800a96b70",
    "backend/modules/work_orchestration/contracts/dto/conversation.py": "4a08dc4b38b5507b0266996e0459a6c103a353fa8fd3d1b7ed20c6daf1e1bf00",
    "backend/modules/work_orchestration/application/services/conversation.py": "ea1d7f9b18b13660f9a7d0e0abd0b43a3ccd0548ba0b39dbc3651d109437d2f6",
    "backend/modules/work_orchestration/application/queries/read_production.py": "443b14bf8669277bb9f99c4f6bdae68f1135581cf694e0d6ac9a49a797e6cddb",
    "backend/modules/pedagogical_design/contracts/dto/conversation_draft.py": "367232b6f91e1b07ddff2a58a5300c69067b66ed98838d28eef193045c1c89ee",
    "backend/adapters/inbound/application/production.py": "5367785f507da237f5fd408294c76fb5698fbb6aead78addd171513b27515aa0",
    "backend/adapters/inbound/api/production.py": "2260eb2b36a48da075f70bbe3197103b8590de94fb8cee0de87f49c882a905f1",
    "backend/adapters/inbound/api/local_browser.py": "03686d1539e4826fb7fc7fe9f936f704989f454460ef23539b20a1e3e543c4ef",
    "backend/adapters/outbound/generation/openai/adapter.py": "8854f9b5dea7d9ddb713d27211a77fe36dff4577ee080f63f5f71925fccc3088",
    "backend/adapters/outbound/generation/openai/mapping.py": "ace7fe0d46f38dd03270160259e2858e86d9bfe98ba57c8492213c29f7f855b7",
    "backend/adapters/outbound/openai/transport.py": "9d46fc6874ab05693e3159893caa3f2c21602613d150ae35c430fec45dd8c7d1",
    "backend/adapters/outbound/openai/contracts.py": "2d9829b1fbf18a2e87dcddff386682e8c92fa976104514bbc11683ae5a2429c2",
    "backend/adapters/outbound/review/openai/adapter.py": "588111262f21075f8731e9d7513e5a93d4f1ed1bf37009f197922c5ccfabda9e",
    "backend/adapters/outbound/review/openai/mapping.py": "78a777f34fd0917644b006179dd6979d30456fa069831982bb050ded8167f62c",
    "tests/architecture/test_repository_hygiene_b06.py": "8ceffb8d460a759ec90371e246aef43d346801ca6fc064c8ba2877d439ae51e9",
    "tests/architecture/test_calibration_tooling_boundary.py": "dfa0f3ad3e7db0c12a6b4ed349f76f722f3e1326133e02f451a28e9c6dd2b39a",
    "tests/architecture/test_pedagogical_calibration_fitness.py": "8083956e2eba2a892d8ada6b47799bff1e5e02515979307200b4ef0dd1039313",
    "tests/calibration/pedagogical/repair_tranche_v4_2.py": "9b85e5496ed9177bfd11fff896b7bd9bd87b4bf919216c6327172a784cf952d9",
    "tests/architecture/test_openai_generation_adapter_fitness.py": "2035c17b4d2b26cd406ffe1d6f2b80bd1979036748073b607a2554861ad269c5",
    "tests/architecture/test_openai_review_anthropic_scorer_fitness.py": "e5bc143a181dca1d95b47e88091284a4b618978e55ea045aeffcadea60d92ee3",
    "tests/architecture/test_review_boundary_fitness.py": "b8eaa8ce884fba2fc12eeae0eb331086599f58564c2052ca67c1d8d89c4b5385",
    "tests/architecture/test_local_browser_http_boundary_fitness.py": "0c9d07e647ec0fd6c37b032f6731d11498f33de8a7587e2e60beaa06edcf230d",
    "tests/architecture/test_canonical_contract_boundaries.py": "6a5472d7fe7c656c022f2f9a08baa0d7666353b2a4cd7e358376fdbce90fc228",
    "docs/development/ENVIRONMENT.md": "b0eac827ddc3eda533a3587da1c65e9bc2ba4c638f0da3db85eb477655ab7701",
    "architecture/adr/ADR-conversational-generation-product-boundary.md": "a5576aab15c17b269b62b7efb52f5e8baf1d15e5c92762f78b0b0fe68a387a82",
    "docs/development/phase_12_18_h2_r2_generation/CONVERSATION_HTTP_LOCAL_V1.json": "b65f7927ff0b8605be3038600f365ada359680596051a57ddae5282d81ce5332",
    "docs/development/phase_12_18_h2_r2_generation/IMPLEMENTATION_EVIDENCE.md": "f9aa511c0a05367a34f9326c4f29123607779b62c256dbf563ba443f2504460b",
    "docs/development/phase_12_18_h2_r2_generation/LIVE_GENERATION_SCOPE.json": "ea3b57a7309e639554be5fc417349ce6eac228c384db71da221b38acbab544fa",
    "docs/development/phase_12_18_h2_r2_generation/MANIFEST_SHA256.txt": "212c8cbf6ef21145d8fd73add3b607fe55274c66462876c0c5d99fa07f26b0ee",
}
PREPARATION = {
    "docs/development/phase_12_18_h1_audit_cumulatif/01_BASELINE_ET_PERIMETRE.md": "1a220b89864c0b01634996b04b4784e38faee5fe7fea596f65c51ce8d0d9cecb",
    "docs/development/phase_12_18_h1_audit_cumulatif/02_MATRICE_CUMULATIVE_12_1_12_17.json": "3f1120df875476dc1f140ae394de27831d517c8b4d49ec07c8271075c42029b3",
    "docs/development/phase_12_18_h1_audit_cumulatif/03_ETAT_INTEGRATION_PRODUIT.md": "1d844c64b5e44dd798de3fb81807b1a8a7098f4cc7fa9d5eeeabf87432b8f811",
    "docs/development/phase_12_18_h1_audit_cumulatif/04_ECARTS_ET_PREPARATION_RECETTE.json": "af7e112116448cb076244349bf1de9cdd823ed2071ddeadda84bda4c7821d282",
    "docs/development/phase_12_18_h1_audit_cumulatif/LIVRABLE_12_18_H1_AUDIT_CUMULATIF.md": "c2723ab6f9d943397cc7eb8d36642f76ee555ea36d1ebe96bf31b28a84bfaefd",
    "docs/development/phase_12_18_h1_audit_cumulatif/MANIFEST_SHA256.txt": "259a50779d6c75231e3a3cad8f5d78dc69442b696613719c128fcb4320674ab3",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/01_SOURCES_ET_ECARTS_RECONCILIES.json": "a8dd8edc13d505e504a3983bf5598a834f2fb57ba4fead0d3545f1d2848448d3",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/02_PROPOSITION_EVOLUTION_GUARD.md": "f019d1e74e079ca2ecfc48f77da8ef3bee6904affa59346b48b59d8d9840a80c",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/03_PAQUET_DECISION_ET_PLAN_H2.md": "2e90d55cd1600f71032f197c3aaa61c8aaebb291e792fea5d27a7b89e50a1dad",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/LIVRABLE_H1A_SOURCES_ET_GUARD.md": "398a6e2b68e4deb0c720cb309d33ef41c12644c2b49951749739e3b224afc998",
    "docs/development/phase_12_18_h1a_sources_et_evolution_guard/MANIFEST_SHA256.txt": "2c7f3d2b93e4852f9243f6d6631492fc1d413bfb3ab0df4141672fa1ccd932a8",
    "docs/development/phase_12_18_h2_r2_generation_preparation/01_CONTRAT_R2_GENERATION_CONVERSATIONNELLE.md": "aac3f81f5a3a10017a305f5005dd373ccd598cdaee5815fcdb2c5606050df66f",
    "docs/development/phase_12_18_h2_r2_generation_preparation/02_INVENTAIRE_GUARDS_TESTS_PERMISSIONS_R2.json": "b5ed6c00d616b2f7319f2089637f9f0778c7e3eab601caf73a377de00fdd7699",
    "docs/development/phase_12_18_h2_r2_generation_preparation/03_DECISION_ET_PLAN_EXECUTION_R2.md": "f4dfa5de3ed8674c4ed24aeeeeee6bd3c72f214db427357447a3e7975df815ea",
    "docs/development/phase_12_18_h2_r2_generation_preparation/MANIFEST_SHA256.txt": "359b06ab34aa092831bd0d0eea909fc4b030776eef49414edbe7932f97eb9d6c",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/01_BASELINE_ET_REUTILISATION.md": "86916ecaf2fbfc2f0d98d39ae18636264c2f02049e7e4dae8ff3d254a3f8c31e",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/02_CONTRAT_RECHERCHE_LOCALE_PROPOSE.md": "664df97c350324af087597f7d17ec4e71ab837129a871959ee3305d61e7ebf0b",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/03_INVENTAIRE_FICHIERS_ET_GUARDS.json": "856c7017b6f943c8575895a3844bfa62053c7574272422be3e8e1bbedb53606a",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/04_DECISION_ET_PLAN_IMPLEMENTATION.md": "777e86b5584eebc59990568b4e82985e89901ea6a2e6b58cf4f032b4eda7df4b",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/LIVRABLE_PROPOSITION_RECHERCHE_LOCALE.md": "b03bbb1be99b2698dff717b864ee59e968f3abe2d366e9e7c658aab60ac450d4",
    "docs/development/phase_12_18_h2_recherche_locale_preparation/MANIFEST_SHA256.txt": "7e210975e1c64ecc29aa73bbbaf48c2e4b099501625fd061f33f0ef13d8f15f4",
    "docs/development/phase_12_18_h2_r3_review_modify_preparation/01_CONTRAT_R3_REVIEW_VALIDATION_MODIFICATION.md": "070ce857bcb13692252a3244a2282fad7a5788d429854bef03a803f3ea13fbc5",
    "docs/development/phase_12_18_h2_r3_review_modify_preparation/02_INVENTAIRE_FICHIERS_GUARDS_R3.json": "c9fc7a04ea4295c4fd5e46bbfe52108994c9acb924d80487735a626838cf96f0",
    "docs/development/phase_12_18_h2_r3_review_modify_preparation/03_DECISION_ET_PLAN_EXECUTION_R3.md": "bbb420528134fb9691e59152948fe33c7d318675ef431d8081789e84dbadb5e6",
    "docs/development/phase_12_18_h2_r3_review_modify_preparation/04_SCENARIO_ACCEPTATION_R3.md": "eb24bf80e10bee078cc607a8060ca07b0b32d0f3f8013059534e1224d594a7e1",
    "docs/development/phase_12_18_h2_r3_review_modify_preparation/LIVRABLE_PROPOSITION_R3.md": "5a446f94d8669ce6204048da3474cb26d9dfbf7576f2129430de9da6cecff6f8",
    "docs/development/phase_12_18_h2_r3_review_modify_preparation/MANIFEST_SHA256.txt": "b9f90be754a2e7dc359087675e23ec4284673e9e5336fe742ecf286a1ddba211",
}
GUARDS = {
    "tests/architecture/test_local_browser_product_boundary.py": (
        "route_contract_violations",
        "inventory_violations",
        "test_existing_pure_contracts_and_original_guards_other_tests_preserved",
    ),
    "tests/architecture/test_local_search_product_boundary.py": (
        "test_exact_five_routes_preserve_read15",
        "registry_copy",
        "test_exact_inventory_before_and_after_commit",
        "test_protected_document_mutation_is_rejected",
    ),
    "tests/architecture/test_resource_ref_contract_fitness.py": (
        "test_read15_keeps_one_field_and_deprecations_without_http_implementation",
    ),
    "tests/architecture/test_security_recovery_observability_e2e_fitness.py": (
        "test_later_provider_work_preserves_phase_f_backend_owners",
    ),
    "tests/architecture/test_conversation_product_boundary.py": (
        "test_correction_exact_delta_and_delivered_65_path_snapshot",
        "test_corrective_inventory_guard_has_exactly_one_approved_assertion_delta",
        "assert_r2_guard_nodes_preserved",
        "test_only_closed_r2_routes_and_pure_security_evolution",
        "test_exact_65_path_inventory_at_all_git_states",
        "test_index_cannot_be_hidden_by_clean_working_bytes",
    ),
    "tests/unit/test_local_browser_product_routes.py": (
        "test_registry_has_one_business_operation_and_three_assets",
    ),
}
BACKEND_CREATES = (
    "backend/modules/pedagogical_design/contracts/dto/assessment_bundle.py",
    "backend/modules/pedagogical_design/contracts/dto/assessment_revision.py",
    "backend/modules/pedagogical_design/domain/policies/assessment_revision.py",
    "backend/modules/pedagogical_design/ports/outbound/assessment_revision.py",
    "backend/modules/pedagogical_design/ports/inbound/revise_assessment.py",
    "backend/modules/pedagogical_design/application/commands/revise_assessment.py",
    "backend/modules/validation_control/contracts/dto/deterministic_validation.py",
    "backend/modules/validation_control/domain/policies/assessment_checks.py",
    "backend/modules/validation_control/ports/inbound/validate_assessment.py",
    "backend/modules/validation_control/application/commands/validate_assessment.py",
    "backend/modules/work_orchestration/contracts/dto/r3_review_modify.py",
    "backend/modules/work_orchestration/ports/inbound/r3_review_modify.py",
    "backend/modules/work_orchestration/ports/outbound/r3_store.py",
    "backend/modules/work_orchestration/ports/outbound/r3_job.py",
    "backend/modules/work_orchestration/application/services/r3_review_modify.py",
    "backend/adapters/inbound/application/r3_review_modify.py",
    "backend/adapters/inbound/api/r3_review_modify.py",
    "backend/adapters/outbound/generation/assessment_revision.py",
    "backend/adapters/outbound/review/assessment_review.py",
    "backend/adapters/outbound/system/r3_job.py",
    "backend/infrastructure/composition/bindings/r3_agents.py",
    "backend/infrastructure/composition/bootstrap/r3_worker.py",
    "backend/infrastructure/composition/factories/r3_review_modify.py",
)


def git_bytes(root: Path, reference: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{reference}:{path}"], cwd=root, check=True, capture_output=True
    ).stdout


def hash_variants(raw: bytes) -> set[str]:
    return {
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest(),
    }


def active_inventory(
    root: Path, *, changed: set[str] | None = None, indexed: set[str] | None = None
) -> list[str]:
    from tests.support.r3_cap_a01_guard import PATHS as CAP_PATHS
    from tests.support.r3_cap_a01_guard import violations as cap_violations
    from tests.support.r3_d3_scope_guard import PATHS as D3_PATHS
    from tests.support.r3_d3_scope_guard import violations as d3_violations
    from tests.support.r3_editorial_correction_guard import PATHS as EDITORIAL_PATHS
    from tests.support.r3_editorial_correction_guard import violations as editorial_violations
    from tests.support.r3_locator_materialization_guard import PATHS as LOCATOR_PATHS
    from tests.support.r3_locator_materialization_guard import violations as locator_violations
    from tests.support.r3_parse_observability_guard import (
        PATCH_PATHS,
        active_source_matches,
        patch_violations,
    )
    from tests.support.r3_portable_clone_guard import PATHS as PORTABLE_PATHS
    from tests.support.r3_portable_clone_guard import private_preparations
    from tests.support.r3_portable_clone_guard import violations as portable_violations
    from tests.support.r3_prepare_contract_alignment_guard import PATHS as SUCCESSOR_PATHS
    from tests.support.r3_serializer_8192_guard import CREATES as SERIALIZER_CREATES
    from tests.support.r3_serializer_8192_guard import PATHS as SERIALIZER_PATHS
    from tests.support.r3_serializer_8192_guard import violations as serializer_violations

    doc = json.loads((root / R3_CONTRACT).read_text("utf-8"))
    assert doc["baseline_commit"] == R3_BASELINE
    assert doc["package_manifest_sha256"] == R3_MANIFEST
    assert doc["approved_inventory"] == list(R3_PATHS)
    indexed = set() if indexed is None else indexed
    if changed is None:
        changed = set()
        for args in (
            ["diff", "--name-only", R3_BASELINE, "--"],
            ["diff", "--cached", "--name-only", R3_BASELINE, "--"],
            ["ls-files", "--others", "--exclude-standard"],
        ):
            result = subprocess.run(
                ["git", *args], cwd=root, check=True, capture_output=True, text=True
            )
            changed.update(result.stdout.splitlines())
            if "--cached" in args:
                indexed.update(result.stdout.splitlines())
    violations = sorted(changed - set(R3_PATHS) - set(PREPARATION) - set(PATCH_PATHS)
                        - set(SUCCESSOR_PATHS) - set(SERIALIZER_PATHS) - set(CAP_PATHS) - set(LOCATOR_PATHS) - set(EDITORIAL_PATHS) - set(PORTABLE_PATHS) - set(D3_PATHS))
    if changed & (set(LOCATOR_PATHS) - set(R3_PATHS) - set(SUCCESSOR_PATHS) - set(SERIALIZER_PATHS) - set(CAP_PATHS)):
        violations += locator_violations(root, changed=changed & set(LOCATOR_PATHS))
    if changed & (set(CAP_PATHS) - set(R3_PATHS) - set(SUCCESSOR_PATHS) - set(SERIALIZER_PATHS)):
        violations += cap_violations(root, changed=changed & set(CAP_PATHS))
    violations += ["MISSING_R3_PATH:" + p for p in sorted(set(R3_PATHS) - changed)]
    violations += ["PROTECTED_DOCUMENT_INDEXED:" + p for p in sorted(indexed & set(PREPARATION))]
    violations += list(private_preparations(root).errors)
    violations += d3_violations(root)
    violations += portable_violations(root)
    for path, digest in READ_ONLY.items():
        file = root / path
        if not file.is_file() or not active_source_matches(root, path, digest):
            violations.append("PROTECTED_DOCUMENT_CHANGED:" + path)
    if changed & set(SERIALIZER_CREATES):
        violations += serializer_violations(root)
        violations += ["SERIALIZER_MISSING:" + p for p in sorted(set(SERIALIZER_PATHS) - changed)]
    violations += editorial_violations(root)
    violations += patch_violations(root)
    if changed & (set(PATCH_PATHS) - set(R3_PATHS)):
        violations += ["PARSE_PATCH_MISSING:" + p for p in sorted(set(PATCH_PATHS) - changed)]
    if changed & (set(SUCCESSOR_PATHS) - set(R3_PATHS)):
        violations += ["PREPARE_SUCCESSOR_MISSING:" + p for p in sorted(set(SUCCESSOR_PATHS) - changed)]
    return violations


def assert_guard_scope(
    root: Path, *, baseline_root: Path | None = None, paths: tuple[str, ...] | None = None
) -> None:
    from tests.support.r3_parse_observability_guard import assert_guard_extension

    repository = baseline_root or Path(__file__).resolve().parents[2]
    for path in paths or tuple(GUARDS):
        raw = git_bytes(repository, R3_BASELINE, path)
        assert PRE_HASHES[path] in hash_variants(raw)
        before = ast.parse(raw)
        after = ast.parse((root / path).read_text("utf-8"))
        old = {n.name: n for n in before.body if isinstance(n, ast.FunctionDef)}
        new = {n.name: n for n in after.body if isinstance(n, ast.FunctionDef)}
        assert old.keys() == new.keys(), path
        extra = set()
        if path == "tests/architecture/test_conversation_product_boundary.py":
            assert_guard_extension(root, path, repository=repository)
            extra = {"assert_r2_generation_source_lineage"}
        for name in old.keys() - set(GUARDS[path]) - extra:
            assert ast.dump(old[name]) == ast.dump(new[name]), (path, name)

        def declarations(tree):
            return [
                ast.dump(n)
                for n in tree.body
                if not isinstance(n, (ast.FunctionDef, ast.ImportFrom))
                and not (
                    isinstance(n, ast.Assign)
                    and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id in {"_EXPECTED_ROUTES", "R3_BASELINE"}
                )
            ]

        assert declarations(before) == declarations(after), path
        old_imports = {ast.dump(n) for n in before.body if isinstance(n, ast.ImportFrom)}
        new_imports = {ast.dump(n) for n in after.body if isinstance(n, ast.ImportFrom)}
        assert old_imports <= new_imports, path
        assert all(
            n.module == "tests.support.r3_guard_oracle"
            for n in after.body
            if isinstance(n, ast.ImportFrom) and ast.dump(n) not in old_imports
        ), path
        if "resource_ref_contract" in path:
            name = GUARDS[path][0]
            assert [ast.dump(n) for n in old[name].body[:-1]] == [
                ast.dump(n) for n in new[name].body[:-1]
            ]
            expected = ast.parse("assert ROUTE_SPECS == " + repr(R3_ROUTES)).body[0]
            assert ast.dump(new[name].body[-1]) == ast.dump(expected)
        if path == "tests/unit/test_local_browser_product_routes.py":
            name = GUARDS[path][0]
            assert [ast.dump(n) for n in old[name].body[1:]] == [
                ast.dump(n) for n in new[name].body[1:]
            ]
            assert ast.dump(new[name].body[0]) == ast.dump(
                ast.parse("assert len(ROUTE_SPECS) == 16").body[0]
            )
        if "security_recovery_observability" in path:
            name = GUARDS[path][0]
            original = old[name]
            candidates = [
                n
                for n in ast.walk(original)
                if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == "h2_conversation_owner_files"
            ]
            assert len(candidates) == 1
            candidates[0].value.elts.extend(ast.Constant(p) for p in BACKEND_CREATES)
            assert ast.dump(original) == ast.dump(new[name]), path
        if "local_browser_product_boundary" in path:
            name = "test_existing_pure_contracts_and_original_guards_other_tests_preserved"
            assert [ast.dump(n) for n in old[name].body[-2:]] == [
                ast.dump(n) for n in new[name].body[-2:]
            ]
