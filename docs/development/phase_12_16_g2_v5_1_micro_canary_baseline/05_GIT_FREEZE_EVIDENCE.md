# V5.1 micro-canary — Git freeze evidence

- Candidate parent commit:
  `cea1c9da5d31c07f2b7af3e993d47f5b0c92b8ac`
- Freeze commit message:
  `test: freeze v5.1 parser micro-canary baseline`
- Freeze commit contains the V5.1 parser remediation, micro-canary controls,
  targeted tests and evidence packages.
- Baseline commit SHA: obtained from `git rev-parse HEAD` immediately after the
  local freeze commit and reported in the execution handoff.
- Required post-commit worktree state: `CLEAN`.
- Push: `NONE`.

The commit cannot embed its own SHA without changing that SHA; the immutable
identifier is therefore reported after commit creation.
