# Outil de résolution et politique de source

L'outil existant `pip` a été conservé. Une seule fenêtre réseau B05 a résolu les trois
ensembles avec la cible explicite `win_amd64`, Python `3.12`, implémentation `cp`, ABI
`cp312` et `--only-binary=:all:`. L'index a été forcé sur le simple index public PyPI.

```text
OWNER_B05_DEPENDENCY_RESOLUTION = APPROVED
OWNER_ATTESTATION_TIMESTAMP = 2026-09-05T02:56:14+02:00
OWNER_BASELINE_BINDING = b63a1463046141512739e4c8f4618ab967002c78
DEPENDENCY_RESOLUTION_OPTION = B05_DEP_RESOLUTION_A_CONTROLLED_ONE_TIME_NETWORK
NETWORK_RESOLUTION_USED = TRUE
NETWORK_ACCESS_AFTER_RESOLUTION = FALSE
NETWORK_SOURCE_COUNT = 1
NETWORK_SOURCE = PUBLIC_PYPI_SIMPLE_INDEX
PRIVATE_PACKAGE_INDEX_COUNT = 0
GIT_OR_ARBITRARY_URL_DEPENDENCY_COUNT = 0
UNEXPECTED_SDIST_COUNT = 0
PROVIDER_CALLS = 0
```

Le bundle owner utilisé a le SHA-256
`69e8ed9b1a37a29c511793fdbd64e3e95505861d361cd4a570bc4b36913d18a7` et son
manifeste interne est `7/7 PASS`. Les wheels restent dans une racine temporaire privée
hors dépôt ; aucun artefact binaire n'est versionné.
