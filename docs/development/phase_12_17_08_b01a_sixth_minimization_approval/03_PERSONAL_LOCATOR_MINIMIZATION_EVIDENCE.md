# Phase 12.17.8-B01A — Personal locator minimization evidence

Only these four fields changed in `PHYSICAL_EVIDENCE.json`:

| Field | Canonical POST representation |
|---|---|
| `discovery.desktop_path` | `<LOCAL_DESKTOP_ROOT>` |
| `discovery.project_folder_path` | `<LOCAL_PROJECT_ROOT>` |
| `discovery.initial_prompt_path` | `<LOCAL_PROJECT_ROOT>\\base_pedagogique_v2.sqlite` |
| `discovery.owner_supplied_exact_path` | `<CANONICAL_SEED_PATH>` |

All existence flags, fail-closed search evidence, filenames, size, checksums, timestamps, integrity results, schema evidence, sidecar evidence and scope counters remain unchanged.

```text
PERSONAL_LOCATORS_BEFORE = 4
PERSONAL_LOCATORS_AFTER = 0
PREVIOUS_MINIMIZATION_TARGETS = 5/5
NEWLY_APPROVED_TARGETS = 1/1
TOTAL_MINIMIZATION_TARGETS = 6/6
```
