# Phase 12.17.7 — Disposition Git et `.gitignore`

## Disposition des 126 éléments hérités

| Disposition | Nombre | Rationale |
|---|---:|---|
| À versionner comme preuve canonique | 126 | 47 preuves canoniques, 72 artefacts de développement et 7 rapports générés font partie de la traçabilité des décisions et gates. |
| Local-only | 0 | Aucun élément n'est un cache, secret, runtime ou donnée utilisateur. |
| À ignorer | 0 | Les 126 sont des sources/preuves, pas des outputs éphémères. |
| Stale/temp confirmé | 0 | L'audit 12.17.6 n'a établi aucun caractère stale. |
| Evidence à conserver | 126 | Conservation dans Git après la décision propriétaire et la minimisation retenue. |
| Unknown | 0 | Classification 126/126 complète. |

Les cinq documents contenant des localisateurs privés restent comptés parmi les 126 à versionner, mais l'Option A recommandée de `03_P1_DECISION_ANALYSIS.md` les minimise avant le commit. Les bytes originaux ne sont ni supprimés ni archivés par ce plan.

`ORIGINAL_126_ITEMS_DISPOSITIONED = 126/126`

## Disposition des 11 preuves 12.17.5C

| Choix | Nombre |
|---|---:|
| Versionner | 11 |
| Archiver hors Git | 0 |
| Conserver local-only | 0 |
| Supprimer après packaging | 0 |

Rationale : ces onze fichiers attestent l'approbation, les manifestes, la provenance des 116 chemins, l'exactitude du staging, la validation et la clôture de la consolidation `e2c43184…`. Les exclure recréerait précisément le défaut de provenance constaté.

`PHASE_12_17_05C_EVIDENCE_DISPOSITIONED = 11/11`

## Éléments 12.17.6 et 12.17.7

Les 15 artefacts 12.17.6 et les 13 artefacts 12.17.7 sont également des preuves canoniques à versionner dans B01. Sans drift, l'allowlist totale attendue de B01 est donc `126 + 11 + 15 + 13 = 165` chemins. La liste réelle doit être reconstruite et comparée byte-for-byte à `git status --porcelain=v1 -z` avant tout staging.

## Quatre corrections `.gitignore`

| Famille | Patterns planifiés | Garde négative |
|---|---|---|
| Backups et manifests adjacents | `*.bak`, `*.backup`, `*.bak.manifest.json`, `*.backup.manifest.json` | ne pas ignorer `MANIFEST_SHA256.txt`, les JSON de preuve ni `database/migrations/` |
| Temporaires adjacents | `*.tmp` | ne pas ignorer les fixtures explicitement suivies; elles doivent utiliser une extension/source dédiée |
| Construction d'index | `*.building` | ne pas ignorer le code ou les manifestes d'index |
| Logs structurés | `*.jsonl` | ne pas ignorer les JSON/Markdown canoniques |

`GITIGNORE_GAPS_PLANNED = 4`

## Garde de staging/commit future

1. B01 est bloqué tant que l'owner n'a pas choisi Option A ou B.
2. Toute dérive par rapport au total et à l'allowlist attendus bloque le lot; aucun ajout opportuniste.
3. Le staging utilise des chemins littéraux explicitement approuvés, jamais `git add .`.
4. Après staging : secret scan, binary/SQLite scan, manifestes, `git diff --cached --check` et matrice `STAGED_FILES_EXACT_MATCH`.
5. Un commit documentaire/provenance unique; pas de push.
6. B02-B06 utilisent ensuite un commit atomique par lot. B07 crée seulement le commit de clôture si sa gate est verte.

## Artefacts ignorés locaux

Les 3 134 fichiers `.tmp`, 747 fichiers `artifacts` et 44 fichiers de cache ne sont pas des éléments de la disposition Git. B06 fournit un inventaire dry-run et une politique de rétention. Toute suppression effective reste une action destructive distincte soumise à autorisation explicite.

`REPOSITORY_HYGIENE_PLAN = BLOCKED_PENDING_OWNER_OPTION_FOR_B01`
