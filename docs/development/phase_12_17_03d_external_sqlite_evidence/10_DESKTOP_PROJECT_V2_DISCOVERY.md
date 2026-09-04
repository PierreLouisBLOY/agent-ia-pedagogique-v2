# Phase 12.17.3D — Desktop Project V2 discovery

## Result

```text
PHASE_12_17_03D_DESKTOP_PROJECT_SQLITE = PASS
PROJECT_FOLDER_PATH = <LOCAL_PROJECT_ROOT>
SQLITE_PATH = <CANONICAL_SEED_PATH>
SQLITE_EXISTS = TRUE
```

The Windows desktop was resolved with `[Environment]::GetFolderPath('Desktop')`; no hard-coded desktop assumption was used.

## Locator resolution

The prompt's initial root locator, `<LOCAL_PROJECT_ROOT>\base_pedagogique_v2.sqlite`, was checked first and was absent. Execution stopped without searching elsewhere. The owner then supplied this exact locator directly:

`<CANONICAL_SEED_PATH>`

That specific file exists. No recursive search, alternate drive lookup or substitute selection was performed.

The physical filename has the owner-supplied `01_` prefix, while the prompt's documentary name omits it. This locator variance is recorded rather than hidden. The supplied file was accepted as the inspection candidate only after its size and SHA-256 matched the canonical identity exactly.
