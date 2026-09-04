# 12.17.8-B03 — Résolution du scope

```text
PHASE = 12.17.8-B03
B03_CANONICAL_TITLE = Observabilité minimale locale
ENTRY_HEAD = 2a0ec8f6e24d61e05228119869791999277bfef4
ENTRY_WORKTREE = CLEAN
PHASE_12_17_08_B02 = PASS
B03_ENTRY_GATE = READY
FINDINGS = CF-OBS-001
ROOT_CAUSE = contrats existants sans destination persistante ni câblage de lifecycle
OPTION = OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S
```

Le scope canonique couvre `backend/infrastructure/observability/`, les points de composition sans serveur, `calibration_tooling/observability/`, les tests unitaires, intégration et architecture, ainsi que la documentation de configuration. Il impose le sink NDJSON local, douze familles de signaux, la rotation/rétention, un flush borné et l'isolation des défaillances.

Sont hors scope : création d'un serveur ou d'une route HTTP, appel fournisseur réel, résolution de credential, écriture dans le seed ou la base utilisateur, export réseau, modification métier, B04 et 12.18.

La politique de livraison est un commit atomique code+config+tests+preuves B03, staging littéral et aucun push. Le rollback est un `git revert` du commit B03 ; aucune suppression de logs utilisateur n'est autorisée par ce lot.

La prochaine étape canonique est `12.17.8-B04 — Contrat HTTP local-browser fail-closed`. Son entrée exige B01 PASS et l'absence d'implémentation HTTP concurrente. B04 n'est pas démarré ici.
