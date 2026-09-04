# Phase 12.17.7A — Décision observabilité

```text
FINDING = OBS-001 / CF-OBS-001
AFFECTED_BATCH = 12.17.8-B03
DEPENDENCIES = 12.17.8-B02, 12.17.8-B06
OWNER_DECISION_SOURCE_SHA256 = 3a0b957e69de662b89e3cb9bea47a2b56f6cd27f20e733858392d21210fdfbce
DECISION_STATUS = NOT_APPROVED
```

## Option OBS-A — recommandée

`OBSERVABILITY_DECISION = OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S`

Impact : destination locale `<V2_DATA_ROOT>/logs/observability.ndjson`, rotation à 5 MiB, cinq fichiers maximum, rétention maximale 14 jours et flush shutdown borné à 2 secondes. Le sink est injecté, failure-isolated et réutilise les contrats privacy-safe existants.

- données : uniquement métadonnées techniques fermées; prompts, réponses, contenu pédagogique, secrets, chemins, bodies HTTP, rows SQLite et exceptions brutes exclus ;
- exploitation : diagnostic local durable et portable sans réseau ni service système ;
- configuration : data root V2 existant, sous-répertoire privé `logs`; aucun default Desktop/Drive ;
- repo hygiene : la famille « logs structurés » de B06 doit couvrir `*.ndjson` en plus de `*.jsonl`, sans changer le count de quatre familles ;
- findings/lots : ferme CF-OBS-001 dans B03 et contribue aux gates finales 8, 9, 11, 13 et 14 ;
- confiance : `HIGH` ; solution minimale, déterministe et testable sur la cible locale.

Rollback futur : revert du commit B03; arrêter le sink; conserver ou supprimer les logs locaux uniquement selon une autorisation de rétention/destruction séparée. Le rollback code ne supprime aucune donnée utilisateur.

## Option OBS-B

`OBSERVABILITY_DECISION = OBS_B_NATIVE_OS_FACILITY_REQUIRES_DETAILED_DESIGN`

Impact : utiliser une facility native, par exemple Windows Event Log, via un adaptateur d'infrastructure.

- données : mêmes exclusions obligatoires ;
- exploitation : intégration OS potentiellement meilleure, mais permissions, source registration, portabilité et lecture nécessitent un design supplémentaire ;
- configuration : adaptateurs spécifiques à la plateforme et fallback à définir ;
- findings/lots : CF-OBS-001 reste ouvert tant que le design détaillé, les tests et l'ADR éventuel ne sont pas approuvés ; B03 et la gate 12.17.8 restent bloqués ;
- confiance : `MEDIUM_LOW` au stade actuel, faute de contrat détaillé validé.

Rollback futur : revert de l'adaptateur et désenregistrement de la source OS par une procédure explicitement approuvée; aucune suppression automatique d'événements système.

## Recommandation

Choisir `OBS_A_LOCAL_ROTATING_NDJSON_5MIB_X5_14D_FLUSH_2S`. C'est la seule option immédiatement implémentable dans le scope minimal 12.17.8 sans nouveau sous-design.

Le présent document ne sélectionne aucune option et ne crée aucun sink ou fichier de log.
