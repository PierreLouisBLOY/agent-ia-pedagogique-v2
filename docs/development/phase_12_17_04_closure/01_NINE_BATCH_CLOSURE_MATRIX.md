# Phase 12.17.4 — Matrice de clôture des neuf batches

```text
BATCHES_PASS = 9/9
ROOT_CHANGES_COVERED = 9/9
EXECUTION_CHAIN = COHERENT
```

| Batch | Titre canonique | Root changes | Statut | Commit | Manifest | Tests et gates | Invariants | Findings résiduels | Handoff |
|---|---|---|---|---|---|---|---|---|---|
| B01 | Frontière et lock historique | RC-02 | PASS | `NONE_APPROVED_CARRY_FORWARD` | 8/8, `de4903fa...66e8e` | freeze 40/40 ; guard 5/5 | runtime actif séparé des preuves historiques ; zéro réécriture | deux fichiers cités par le récit mais absents du freeze | B02 READY |
| B02 | Contrats et runner unique | RC-03, RC-05 partiel | PASS | `16d1e90ea8629fa419a93759e4c30ff1c0cb96f0` | 11/11, `3ea8adb7...fd27` | targeted 36/36 ; architecture 11/11 ; actif 0/19 | runner/parser actif unique, provider-neutral, budget et autorisation fail-closed | dette historique 15/10 isolée | B03 READY |
| B03 | Adapter Anthropic actif | RC-01 | PASS | `711ebec196d7a2ea2bb0acf1cfd23812fd56e0e7` | 11/11, `28a11159...0437` | targeted 63/63 ; pertinent 38/38 ; architecture 17/17 | adapter hors `tests/`, client injecté, zéro retry et zéro live | dette historique 15/10 isolée | B04 READY |
| B04 | Composition, imports et CLI | RC-04 | PASS | `cdbcb0457487594745becd9055ac6479127b4ed3` | 9/9, `e9079caa...389f` | targeted 80/80 ; architecture 22/22 ; actif 0/39 | composition injectée, entrée unique, provider désactivé par défaut | aucun nouveau finding | B05 READY |
| B05 | Fermeture typing et dépréciation active | RC-05 | PASS | `2069f0ad0cf532946021716fcbb45709f0d6134d` | 10/10, `d40d57e3...25a9` | targeted 89/89 ; architecture 26/26 ; actif 0/41 | 15/15 diagnostics absents du graphe actif sans modifier l'historique | dette historique 15/10 conservée | B06 READY |
| B06 | Vocabulaires et mappings owners | RC-06 | PASS | `757254675d51ace6c1173cc21217580ae2509ba9` | 11/11, `45194e42...6c05` | targeted 127/127 ; architecture 33/33 ; backend 0/671 | dix vocabulaires possèdent un owner ; aucune migration | Resource ACTIVE/CANONICAL et ContextOrigin UNKNOWN | B07 READY |
| B07 | Configuration de chemins | RC-07 | PASS | `3592ce67855ec65e7adc93d256c9a8043bd978aa` | 12/12, `57432238...b1a4` | targeted 146 PASS, 18 skips conditionnels ; architecture 42/42 | configuration portable, conflits refusés, aucun chemin privé suivi | anciens alias maintenus pendant leur fenêtre | B08 READY |
| B08 | Cycle seed/runtime et sidecars | RC-08 | PASS | `054ba2c7eb19f1be4eb048f94e554022db631dc1` | 14/14, `180db0af...a54` | direct 16/16 ; gates réelles 19/19 ; architecture 46/46 | seed immutable, runtime distincte, migration 001 allowlistée et idempotente | créateur seed WAL/SHM, Resource et ContextOrigin UNKNOWN | B09 READY |
| B09 | Legacy review et handoff API | RC-09 | PASS | `68522d135bb36af98e5cbf44a8e4d3f1d595565f` | 15/15, `14cecf88...8f45` | documentaire 4/4 ; architecture 50/50 ; global 4725/24/0 | rétrospectif non rétroactif, API handoff-only, READ-15 Resource-only | cinq findings propagés | 12.17.4_CLOSURE READY |

Le commit de gate `325ea3397507c0f3d94b9c1ef75c20ca47592d80`
ferme les sept échecs globaux entre B08 et B09. Il ne constitue pas un dixième
batch fonctionnel. B01 reste volontairement non commité et exclu du commit de
clôture conformément à sa politique carry-forward.
