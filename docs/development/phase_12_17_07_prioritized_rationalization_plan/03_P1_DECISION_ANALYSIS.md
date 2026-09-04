# Phase 12.17.7 — Analyse du P1 unique

## Identification exacte

```text
SOURCE_FINDING_ID = REPO-001
CANONICAL_FINDING_ID = CF-REPO-001
SEVERITY = P1
OWNER_DECISION_NEEDED = TRUE
MUST_FIX_BEFORE_12_18 = TRUE
TARGET = 12.17.8-B01
```

Scénario : un clone propre ou une livraison perd des ADR, décisions, preuves et un guard d'architecture qui n'existent que dans le worktree local.

Impact : provenance, reproductibilité de release et capacité d'audit sérieusement incomplètes. Il ne s'agit pas d'une vulnérabilité runtime directe.

Mitigations existantes : les fichiers sont conservés localement; les 126 éléments d'origine ont été inventoriés exhaustivement; les 11 preuves 12.17.5C sont identifiées séparément; aucun secret, binaire SQLite ou fichier temporaire n'a été trouvé dans ces 126 éléments.

## Périmètre au moment de la future exécution

Si aucun drift n'intervient, le lot B01 devra réconcilier exactement :

- 126 éléments historiques inventoriés par 12.17.6 ;
- 11 preuves 12.17.5C ;
- 15 artefacts d'audit 12.17.6 ;
- 13 artefacts de planification 12.17.7 ;
- total attendu : 165 chemins non suivis.

Ce total est une précondition, pas une autorisation de staging. Tout écart impose un nouvel inventaire et bloque B01.

## Option set propriétaire

### Option A — Minimisation puis consolidation exacte — recommandée

Minimiser les chemins privés dans les cinq éléments de preuve identifiés, régénérer uniquement les manifestes transitivement affectés, prouver l'équivalence sémantique, puis versionner les 165 chemins exacts dans un commit documentaire/provenance dédié. Aucun push automatique.

Les cinq chemins concernés sont :

- `docs/development/phase_12_17_03d_external_sqlite_evidence/10_DESKTOP_PROJECT_V2_DISCOVERY.md` ;
- `docs/development/phase_12_17_03d_external_sqlite_evidence/12_READ_ONLY_INTEGRITY_EVIDENCE.md` ;
- `docs/development/phase_12_17_03d_external_sqlite_evidence/14_IMMUTABILITY_PRE_POST.md` ;
- `docs/development/phase_12_17_03d_external_sqlite_evidence/16_FINAL_HANDOFF.md` ;
- `docs/development/phase_12_17_04_rationalization_design_gate/12_FINDINGS_AND_RISKS.json`.

Les remplacements autorisables doivent être des tokens non privés (`<CANONICAL_SEED_PATH>`, `<LOCAL_PROJECT_ROOT>`) sans modifier les checksums observés du seed, les résultats, les décisions ou les timestamps déjà attestés.

### Option B — Conservation byte-exacte

Versionner les 165 chemins tels quels, y compris les cinq preuves contenant des chemins privés historiques. Cette option préserve les manifestes sans rebind, mais inscrit durablement des localisateurs personnels inutiles au runtime.

### Option rejetée pour la gate

Conserver ces éléments uniquement en local ne ferme pas le risque de clone/livraison incomplet et ne peut donc pas satisfaire 12.18.

## Remédiation exacte après décision

1. Vérifier `HEAD`, branche, absence de staged/tracked drift et liste exacte des 165 chemins.
2. Appliquer l'option propriétaire aux cinq preuves privées; ne toucher à aucun autre contenu.
3. Recalculer les manifestes affectés et documenter chaque transition SHA si Option A.
4. Scanner l'allowlist pour secrets, SQLite/sidecars, outputs runtime et chemins privés résiduels selon l'option.
5. Exécuter les guards de manifestes, architecture, historique, mypy applicable et suite globale.
6. Stager uniquement l'allowlist approuvée; prouver `STAGED_FILES_EXACT_MATCH = TRUE`.
7. Créer un seul commit de provenance, puis vérifier le worktree selon la politique finale. Aucun push sans ordre séparé.

## Verdict

Le plan est complet mais l'option A/B change matériellement les bytes et la confidentialité documentaire. La sélection ne peut pas être inventée.

`P1_DISPOSITION = OWNER_DECISION_REQUIRED_BEFORE_12_17_8_B01`
