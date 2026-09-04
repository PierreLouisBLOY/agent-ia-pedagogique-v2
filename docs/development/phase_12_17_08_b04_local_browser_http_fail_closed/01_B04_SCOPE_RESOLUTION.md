# 12.17.8-B04 — Résolution du scope

```text
PHASE = 12.17.8-B04
B04_CANONICAL_TITLE = Contrat HTTP local-browser fail-closed
ENTRY_HEAD = 2650ae7616fc7067e6c6341f854a10efee633d6f
ENTRY_WORKTREE = CLEAN
PHASE_12_17_08_B03 = PASS
OBSERVABILITY_READINESS = PASS
B04_ENTRY_GATE = READY
FINDINGS = CF-HTTP-001
ROOT_CAUSE = absence de serveur laissant la cible loopback non encodée
```

Le scope canonique couvre un DTO de configuration HTTP sans framework, un contrat pur sous la frontière inbound API, les tests sécurité/architecture et la documentation du handoff. Il encode le bind loopback, le port explicite, les hosts et origins exacts, same-origin par défaut, CORS local strict optionnel, erreurs closes, debug/reload/docs désactivés et réutilisation de l'observabilité B03.

Sont hors scope : serveur, socket, route ou endpoint, framework HTTP, schéma OpenAPI, frontend, endpoint `/api/v2`, use case métier, exposition fournisseur, accès SQLite, appel réseau, B05 et 12.18.

La politique est un commit atomique contrat+tests+preuves B04, staging littéral, sans push. Le rollback prévu est un `git revert` du commit B04.
