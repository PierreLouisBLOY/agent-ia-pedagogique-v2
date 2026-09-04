# Phase 12.17.8-B01 — Disposition des sept artefacts post-rebound

All seven are canonical gate evidence, must be versioned now, are included in B01, and target `12.17.8-B01`.

| Path | SHA-256 | Purpose | Canonical | Version | Include | Rationale |
|---|---|---|---|---|---|---|
| `01_OWNER_ATTESTATION_BINDING.md` | `77b6cec06d081ebfef1f91ca0f06fa19313438671ef2ae338a289bf0cb5fa445` | bind owner decisions | TRUE | TRUE | TRUE | required provenance |
| `02_REPO_INVENTORY_REBOUND_172.json` | `098e5d9f42e0091a2fe426763f869f591ed652dc171ce79a4a76742339d67aec` | authoritative 172 inventory | TRUE | TRUE | TRUE | exact staging source |
| `03_FIVE_MINIMIZATION_TARGETS.md` | `705fe6492a15de2576d4b9916cc23c62815aafd0ff1156bff02f38106129119e` | bind original five targets | TRUE | TRUE | TRUE | approved minimization trace |
| `04_OBSERVABILITY_DECISION_BINDING.md` | `ad891d67ccb527cc576b860bc40baa099a6432053a9efe8ff3b3b5ffa49328ec` | bind OBS-A | TRUE | TRUE | TRUE | later B03 entry evidence |
| `05_12_17_8_ENTRY_GATE.md` | `5250fb35f60da4cf1fa863f6688ba44568e11f4c5c37cb8dec285d967a655d42` | open B01 gate | TRUE | TRUE | TRUE | execution authorization chain |
| `06_FINAL_HANDOFF.md` | `b5b6ebc6aa5a9da7ccce8d9e202310ba467559608bb09a5e88d622542176c751` | 12.17.7B handoff | TRUE | TRUE | TRUE | gate continuity |
| `MANIFEST_SHA256.txt` | `cb45f7f0d91b8e5fa0dd70e2a625aa52f81b262cd3542c4ed43a4d5bdf1065d7` | package integrity | TRUE | TRUE | TRUE | verifies the six siblings |

```text
POST_REBOUND_7_DISPOSITION = 7/7
POST_REBOUND_7_VERSIONED = 7/7
POST_REBOUND_7_DEFERRED = 0
```
