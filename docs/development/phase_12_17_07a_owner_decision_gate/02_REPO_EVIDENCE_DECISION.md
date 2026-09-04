# Phase 12.17.7A — Décision REPO-001

```text
FINDING = REPO-001 / CF-REPO-001
AFFECTED_BATCH = 12.17.8-B01
OWNER_DECISION_SOURCE_SHA256 = 3a0b957e69de662b89e3cb9bea47a2b56f6cd27f20e733858392d21210fdfbce
DECISION_STATUS = NOT_APPROVED
```

## Option A — recommandée

`REPO_EVIDENCE_DECISION = OPTION_A_MINIMIZE_FIVE_AND_CONSOLIDATE_165`

Impact : remplacer uniquement les localisateurs personnels dans cinq preuves par `<CANONICAL_SEED_PATH>` ou `<LOCAL_PROJECT_ROOT>`, sans modifier seed hash, résultats, décisions ni timestamps. Recalculer les manifestes 12.17.3D et 12.17.4 design directement affectés, puis prouver l'équivalence et consolider tous les éléments approuvés.

- direct existing-file change surface : cinq preuves + deux manifestes ;
- confidentialité : chemin personnel non inscrit durablement dans Git ;
- provenance : transitions SHA explicites et vérifiables ;
- exécution : le suffixe `165` est conservé comme vocabulaire figé; les 172 inputs attendus après ce paquet doivent être rebondés avant B01 ;
- findings/lots : ferme CF-REPO-001 dans B01; contribue aux gates finales 2, 13, 14, 15 et 16 ;
- confiance : `HIGH` ; la minimisation est bornée et l'équivalence est testable.

Rollback futur : avant commit, conserver une copie de récupération hashée hors dépôt des cinq bytes originaux; après commit, utiliser `git revert <commit-B01>`. La restauration des originaux locaux, si demandée, vient uniquement de cette copie vérifiée. Aucun reset/history rewrite.

## Option B

`REPO_EVIDENCE_DECISION = OPTION_B_BYTE_EXACT_CONSOLIDATE_165`

Impact : conserver et versionner les preuves byte-exactes, y compris leurs chemins personnels historiques.

- direct existing-file change surface : aucune minimisation et aucun rebind des deux manifestes ;
- confidentialité : les localisateurs personnels entrent dans l'historique Git sans bénéfice runtime ;
- provenance : simplicité et préservation des SHA actuels ;
- exécution : même rebind à 172 inputs avant B01 ;
- findings/lots : ferme CF-REPO-001 dans B01, mais conserve une dette de minimisation documentaire acceptée ;
- confiance : `MEDIUM` ; techniquement simple, mais le coût de confidentialité est durable.

Rollback futur : `git revert` annule l'état courant mais ne purge pas les chemins privés de l'historique. Une purge réelle exigerait une réécriture destructive hors scope; l'option n'offre donc pas de rollback de confidentialité complet.

## Recommandation

Choisir `OPTION_A_MINIMIZE_FIVE_AND_CONSOLIDATE_165`. Elle ferme le P1 sans rendre permanents des localisateurs personnels et conserve une chaîne de preuve vérifiable.

Le présent document ne sélectionne aucune option et n'autorise ni modification, ni staging, ni commit.
