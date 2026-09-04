# Phase 12.17.5C — Exactitude du staging

Le snapshot PRE avait un index vide et `HEAD` égal à
`576d6bd6dcf5082740c4192842b7c87ccbc1f246`. L'allowlist a été reconstruite
depuis les handoffs B02→B07 et confrontée au worktree.

Le premier `git diff --cached --check` a révélé un LF terminal superflu dans
le nouveau fichier d'erreur B05. La correction d'un octet a été appliquée
uniquement après l'autorisation propriétaire dédiée et a atteint exactement le
SHA-256 approuvé.

```text
ALLOWLIST_COUNT = 116
STAGED_COUNT = 116
DOCUMENTARY_COUNT = 84
TECHNICAL_COUNT = 32
UNEXPECTED_STAGED = 0
MISSING_STAGED = 0
UNSTAGED_APPROVED_PATHS = 0
SQLITE_OR_SIDECAR_STAGED = 0
HISTORICAL_GUARD_STAGED = 0
EOF_NORMALIZATION = APPROVED_EXACT_SHA_TRANSITION
GIT_DIFF_CACHED_CHECK = PASS
STAGED_FILES_EXACT_MATCH = TRUE
```

Les 126 entrées de worktree antérieures et hors scope ont été conservées sans
staging.
