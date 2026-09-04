# Rotation, rétention et flush

```text
FORMAT = NDJSON
PATH_CLASS = <V2_DATA_ROOT_LOCAL>/logs/observability.ndjson
ROTATION_SIZE_BYTES = 5242880
MAX_TOTAL_LOG_FILES = 5
RETENTION_DAYS = 14
MAX_SHUTDOWN_FLUSH_SECONDS = 2
```

La racine est injectée et validée comme locale. Les racines réseau, Drive/OneDrive et lecteurs non locaux sont rejetés par la primitive B02 ; une racine située dans un checkout Git est également rejetée avant toute création. Répertoire et fichiers sont durcis owner-only, ouverts en append avec no-follow lorsque la plateforme le permet, puis `fsync` après chaque ligne complète.

La rotation intervient avant qu'un append ne dépasse 5 MiB. L'actif plus quatre archives constituent les cinq fichiers maximum. La purge supprime uniquement les archives strictement plus anciennes que quatorze jours, à l'initialisation et pendant les écritures. Le writer ne conserve aucun handle persistant ; le flush est donc synchrone et le shutdown mesure explicitement le délai maximum de deux secondes.

Les échecs d'écriture, flush ou close sont absorbés par le sink, incrémentent un compteur borné et dégradent son état de santé sans interrompre le flux appelant.
