# Phase 12.17.8-B01B — Exact binding of 18 EOF files

Every file had exactly two trailing EOL sequences before normalization and was untracked, unstaged evidence in the B01 allowlist.

| # | Path | Source phase | PRE SHA-256 | Manifest | Blank EOF | B01A-related |
|---:|---|---|---|---|---|---|
| 1 | `phase_12_17_03_business_rule_audit/01_BUSINESS_RULE_SOURCE_CATALOG.md` | 12.17.3 | `34062abcc8f18e9a4fd9ecbd31902a6d72e612ef9bacab2a5939040efee0d57d` | 12.17.3 business-rule | TRUE | FALSE |
| 2 | `phase_12_17_03d_external_sqlite_evidence/11_PHYSICAL_IDENTITY_EVIDENCE.md` | 12.17.3D | `3db40abb16720e96809257111db717316f21bac8212e6b985fa170dea0660b2d` | 12.17.3D | TRUE | TRUE — shared manifest |
| 3 | `phase_12_17_03d_external_sqlite_evidence/13_OD05_OD06_SCHEMA_EVIDENCE.md` | 12.17.3D | `94721d309fefba1cbf3fad09508a2c036d34431d070a831b45db449b11b72d90` | 12.17.3D | TRUE | TRUE — shared manifest |
| 4 | `phase_12_17_03d_external_sqlite_evidence/15_GATE_RECALCULATION.md` | 12.17.3D | `528b38bb1d79ad0efef31ce52d68b8459138d1a13bafaf9539e64e99a34f2d2b` | 12.17.3D | TRUE | TRUE — shared manifest |
| 5 | `phase_12_17_04e_b01_design_approval_hash_freeze/05_PREEXISTING_DRIFT_REGISTER.md` | 12.17.4E-B01 | `eba2a9993fab5904a0fd7a75e4fe4e496c13f57a2c262723dc6a6478f2d6ef20` | 12.17.4E-B01 | TRUE | FALSE |
| 6 | `phase_12_17_04e_b01_design_approval_hash_freeze/07_B02_ENTRY_GATE.md` | 12.17.4E-B01 | `1c9edc2f86e5c161644b7103d1bf603c42c0748db174d7c27458d417062172d7` | 12.17.4E-B01 | TRUE | FALSE |
| 7 | `phase_12_17_06_security_observability_repo_hygiene/02_RUNTIME_ATTACK_SURFACE.md` | 12.17.6 | `a33a77dc68ef1b29b7a1e33b63f4fb07b462078a2fe18e820b899bb27901049c` | 12.17.6 | TRUE | FALSE |
| 8 | `phase_12_17_06_security_observability_repo_hygiene/03_HTTP_LOCAL_BROWSER_SECURITY.md` | 12.17.6 | `9dab465b268799fe2a178237708548dcd6a1acb08b3146d929ddc1573b1ec7f0` | 12.17.6 | TRUE | FALSE |
| 9 | `phase_12_17_06_security_observability_repo_hygiene/04_INPUT_FILESYSTEM_SECURITY.md` | 12.17.6 | `6ce0da43052c6ce09536389150272cbd4b9632133407dd0474911159d4c60864` | 12.17.6 | TRUE | FALSE |
| 10 | `phase_12_17_06_security_observability_repo_hygiene/05_SQLITE_SECURITY_AUDIT.md` | 12.17.6 | `1dcfa10a6f090af93ece20f184bcd5028f82376e2839bebe037f34bd81812a57` | 12.17.6 | TRUE | FALSE |
| 11 | `phase_12_17_06_security_observability_repo_hygiene/06_SECRET_PROVIDER_SECURITY.md` | 12.17.6 | `a05e59a2cce062dea3de07d27354e2c7b3014db58f26f249eeb9ac476b28f270` | 12.17.6 | TRUE | FALSE |
| 12 | `phase_12_17_06_security_observability_repo_hygiene/07_LOGGING_OBSERVABILITY_AUDIT.md` | 12.17.6 | `06eecd09c702126968dbc2b7dec8defa1448e2bbd390699a5bdbdfa0251fc422` | 12.17.6 | TRUE | FALSE |
| 13 | `phase_12_17_06_security_observability_repo_hygiene/09_GITIGNORE_AND_PRIVATE_PATH_AUDIT.md` | 12.17.6 | `2a5229b251be59c0070cde25aa4dd9f4d8267e7b6e43832e1fd64cb10621fec3` | 12.17.6 | TRUE | FALSE |
| 14 | `phase_12_17_06_security_observability_repo_hygiene/10_DEPENDENCY_CONFIG_AUDIT.md` | 12.17.6 | `a31ba45e7882c3b4afe96f36114d35ab86dbb6d8f846728b35f6b362d74bb8ef` | 12.17.6 | TRUE | FALSE |
| 15 | `phase_12_17_06_security_observability_repo_hygiene/11_OBSERVABILITY_GAP_MATRIX.json` | 12.17.6 | `ca959c412307a454a1a1e37cd5017f970b852bae96a257611c14ad4100e4493f` | 12.17.6 | TRUE | FALSE |
| 16 | `phase_12_17_06_security_observability_repo_hygiene/12_FINDINGS_REGISTER.json` | 12.17.6 | `003d70392289d3b0b09fcc7ffc44490ffe8875f4d088335a3e9ed6efadbc1d70` | 12.17.6 | TRUE | FALSE |
| 17 | `phase_12_17_06_security_observability_repo_hygiene/13_12_17_7_ENTRY_GATE.md` | 12.17.6 | `645cf6ace8242f4a331aee70f382f1b0180a2d9c3f351dc8bb99ac7e15de773e` | 12.17.6 | TRUE | FALSE |
| 18 | `phase_12_17_06_security_observability_repo_hygiene/14_FINAL_HANDOFF.md` | 12.17.6 | `483285a89c79ca44baa12f2e6235640383fd5fd2e0ac1b1c60e702cb381dade3` | 12.17.6 | TRUE | FALSE |

All paths are relative to `docs/development/`. `EOF18_BOUND = 18/18`.
