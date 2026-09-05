# Rétention locale sans suppression

Les 203 unités locales reçoivent une disposition explicite de conservation ; les quatre unités logiques de règles Git reçoivent une disposition corrective testée. Total : 207/207.

Les 41 chemins immédiats exacts de .tmp sont :

- .tmp/__pycache__
- .tmp/live_micro_canary_v5_1.py
- .tmp/live_mini_pilot_v5_1.py
- .tmp/live_pairwise_v5_2_2.py
- .tmp/live_pairwise_v5_2_3.py
- .tmp/live_pairwise_v5_2_4.py
- .tmp/live_semantic_pilot_v5.py
- .tmp/live_v42_once.py
- .tmp/pycache-b01-pre-historical
- .tmp/pytest-12-17-02a-20260902
- .tmp/pytest-12-17-02a-diagnose-20260902
- .tmp/pytest-12-17-02a-final-20260902
- .tmp/pytest-12-17-5-contracts
- .tmp/pytest-b07-cumulative
- .tmp/pytest-b07-direct
- .tmp/pytest-b07-final
- .tmp/pytest-b07-final-direct
- .tmp/pytest-r4-r3-r1-targeted
- .tmp/pytest-r4-r3-r1-targeted-rerun
- .tmp/pytest-r4-r4-postflight
- .tmp/pytest-r4-r4-postflight-final
- .tmp/pytest-v3-human-final-a959
- .tmp/pytest-v4-3-metric-analysis
- .tmp/pytest-v4-architecture-targeted
- .tmp/pytest-v4-disposition
- .tmp/pytest-v4-final-global
- .tmp/pytest-v4-final-global-rerun
- .tmp/pytest-v4-human-reconciliation
- .tmp/pytest-v4-implementation-targeted
- .tmp/pytest-v4-implementation-unit
- .tmp/pytest-v4-implementation-v4
- .tmp/pytest-v4-legacy-debt
- .tmp/pytest-v4-legacy-debt-2
- .tmp/pytest-v4-owner-config-targeted
- .tmp/pytest-v4-owner-config-targeted-2
- .tmp/pytest-v4-provider-plan-final
- .tmp/pytest-v4-real-gates
- .tmp/pytest-v5-scorer-redesign-reduced
- .tmp/reconcile_live_semantic_pilot_v5.py
- .tmp/restore_r4_r4_ledger_offline.py
- .tmp/run_r4_r4_continuation.py

Chaque sous-arbre est lié à un digest de métadonnées dans l'inventaire. Les descendants complets restent dans les rapports privés hors dépôt : ne pas versionner des copies d'outputs, du bytecode ou d'éventuels segments de chemins machine présents dans des caches anciens.

Les noms et l'absence de suivi Git suffisent à classifier ces éléments comme locaux, pas à certifier leur contenu, leur origine, leur reproductibilité ou leur inutilité. Aucune prétention de « stale prouvé » n'est faite. Tous restent protégés de suppression ; aucune dépendance runtime à un artefact supprimé ne peut être introduite puisqu'aucun artefact n'est supprimé.

Commande de maintenance : `python -m tests.support.repository_hygiene --older-than-days 30`, avec PYTHONDONTWRITEBYTECODE=1. Sortie JSON par défaut sur stdout ; --output accepte uniquement un nouveau fichier hors dépôt. Age = indication de revue uniquement. Aucune option de suppression, aucun contenu lu, liens/jonctions non suivis, erreurs explicitement conservées.

TEMP_CACHE_REMOVED = 0
TEMP_CACHE_RETAINED = 203
DESTRUCTIVE_ACTIONS = 0

L'inventaire historique du plan (3 134 fichiers .tmp, 44 cache, 747 artefacts) n'est pas assimilé à l'état courant. La différence de volume est signalée, pas effacée pour satisfaire une gate.

## Anomalie de validation identifiée puis corrigée

Le premier passage global a exécuté le test préexistant test_writing_r1_outputs_does_not_mutate_historical_proofs, qui appelait write_r1_outputs(ROOT). Il réécrivait trois documents et le manifeste local artifacts/calibration/12.16-g2-r4-r4/reusable_results_manifest.json avec des écritures atomiques temporaires dans le dépôt. Aucun changement de contenu suivi n'a été constaté par Git. Le manifeste local a gardé sa taille (40 982 octets), mais son mtime et celui du répertoire parent ont changé ; l'inventaire ne prétend pas à une empreinte de contenu PRE de ce fichier ignoré. La conformité sémantique au renderer est vérifiée par le test existant.

Le test a été isolé dans tmp_path et renforcé, sans altérer le moteur ni les preuves. Les originaux ne sont pas remis artificiellement à leur ancien mtime. Le contrôle POST distingue cette anomalie diagnostique de l'absence de nouvelle pollution et de l'invariance après correction. Aucune suppression de donnée locale n'a été effectuée comme remédiation.

## Comparaison finale

203 unités PRE/POST, aucune ajoutée ni retirée ; 20 664 fichiers et 2 994 répertoires conservés. .tmp reste à 41 entrées immédiates (31 répertoires, dix fichiers), 1 673 répertoires descendants et 4 587 fichiers. Hors la trace diagnostique artifacts décrite ci-dessus, les empreintes de métadonnées PRE/POST sont identiques. La comparaison entre l'état après diagnostic et l'état après isolation finale ne relève aucune dérive. REPO_TEMP_POLLUTION = 0.
