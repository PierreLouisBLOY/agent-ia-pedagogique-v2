# État PRE observabilité

```text
HEAD_PRE = 2a0ec8f6e24d61e05228119869791999277bfef4
BRANCH = phase12/12-16-provider-model-calibration
WORKTREE_PRE = CLEAN
PERSISTENT_LOCAL_SINK_PRE = ABSENT
STARTUP_SHUTDOWN_COMPOSITION_PRE = ABSENT
CALIBRATION_DEFAULT_SINK_PRE = NULL
PROVIDER_CALLS_PRE = 0
```

Le dépôt contenait des contrats de télémétrie privacy-safe, des serializers allowlistés et des sinks failure-isolated, mais aucune composition de production ne sélectionnait une destination locale persistante ni une politique de lifecycle. Aucun serveur HTTP n'existait ; B03 ne devait donc fournir qu'un contrat d'instrumentation réutilisable.

Snapshots protégés :

| Élément | Classe de chemin | Taille | SHA-256 PRE |
|---|---|---:|---|
| seed canonique | fichier externe read-only explicitement identifié | 105553920 | `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` |
| runtime utilisateur | runtime local utilisateur, non ouvert par B03 | 105553920 | `de6186a26c1054731a7c0702baa133a8dc995b102417151f6538935ba04d1fb1` |

Les sidecars WAL/SHM préexistants étaient présents pour les deux bases ; aucun journal rollback n'était présent. Aucun journal utilisateur B03 n'existait avant l'exécution.
