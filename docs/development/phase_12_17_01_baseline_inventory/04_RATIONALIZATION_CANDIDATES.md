# Phase 12.17.1 — Candidats de rationalisation

## Synthèse par domaine

| Domaine | Findings `CANDIDATE` | Clusters principaux |
| --- | ---: | --- |
| Typage | 8 | narrowing, tuples fixes, variables réemployées, casts obsolètes |
| Règles métier | 4 | squelettes Domain, autorité documentaire, enums, validateurs privés |
| Runtime/architecture | 5 | API absente, runners versionnés, provider en tests, parsers parallèles, faible surface Application |
| Données/API | 3 | schéma source externe, DDL inline, records dictionnaires |
| Hygiène repository | 3 | EOF JSON, document dupliqué, volume local ignoré |
| Sécurité | 0 | frontières SQL/provider conformes dans le code backend inspecté |

Deux observations d'hygiène et une observation de sécurité sont `INVENTORIED` sans action proposée. Le registre JSON est l'autorité détaillée pour les `23` candidats et les `3` observations non candidates.

## Duplications et chevauchements majeurs

1. Les runners `live_runner.py` et `live_runner_v4_1.py`, puis les couches V5.1/V5.2.x, portent plusieurs générations de préparation, parsing, budget et persistance de preuves.
2. Les contrats pairwise V5.2.3 et V5.2.4 conservent deux implémentations complètes très proches pour préserver les identités historiques.
3. Les contrôles de plafond optionnel sont dupliqués dans `call_plan.py` et `call_plan_v4_1.py` et produisent le même défaut mypy.
4. Les tuples d'anchors ordonnés sont reconstruits dans catalogues V1/V2/V3/V4 avec la même perte de cardinalité statique.
5. Les validateurs privés utilisent `16` noms répétés dans `50` définitions; une consolidation éventuelle exige d'abord une comparaison sémantique, car l'égalité de nom ne prouve pas l'équivalence.
6. La topologie de treize modules masque le fait que douze sont encore structurels, tandis que règles et comportements se concentrent dans `agent_runtime`, les adapters, les docs et les helpers de calibration.

## Risques prioritaires

- `HIGH` : l'API `/api/v2` n'est pas matérialisée alors qu'elle est décrite comme surface canonique projetée.
- `HIGH` : le schéma de base SQLite à 98 tables est externe au dépôt; seule la migration 001 est versionnée localement, ce qui limite une traçabilité autonome Domain/API/SQLite.
- `HIGH` : la topologie Domain/Application suggère une couverture métier plus large que l'implémentation réelle.
- `MEDIUM` : les helpers live Anthropic se trouvent sous `tests/providers`, ce qui rend ambigu leur statut d'infrastructure durable.
- `MEDIUM` : l'empilement de parsers/runners versionnés augmente le risque de divergence et explique plusieurs incompatibilités V5.x déjà observées.
- `MEDIUM` : quatre erreurs mypy de configuration Anthropic reposent sur un fail-closed insuffisamment exprimé au type checker.

Aucun candidat n'est corrigé, supprimé ou consolidé dans ce lot.
