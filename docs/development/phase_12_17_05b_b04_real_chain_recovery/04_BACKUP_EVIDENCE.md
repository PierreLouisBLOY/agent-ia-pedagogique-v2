# Phase 12.17.5B-B04 — Preuve de backup

Avant toute écriture sur une cible B04, une image de backup a été créée dans un
répertoire temporaire hors dépôt. La source a été ouverte en
`mode=ro&immutable=1`; aucune opération de checkpoint ou d'écriture n'a été
faite sur la runtime utilisateur.

```text
BACKUP_LOCATION = TEMPORARY_OUTSIDE_REPOSITORY_REDACTED
BACKUP_CREATED = TRUE
BACKUP_SIZE_BYTES = 105553920
BACKUP_SHA256 = 32dfca0e2c3a483af5f487539ce5bf75ce8398f1d73aefc700c9adc282978554
BACKUP_LEDGER = 001:5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102
BACKUP_DOCUMENT_COUNT = 15
BACKUP_INTEGRITY_CHECK = ok
BACKUP_QUICK_CHECK = ok
BACKUP_FOREIGN_KEY_VIOLATIONS = 0
BACKUP_VERIFIED = TRUE
```

Le hash du fichier de backup représente l'image SQLite normalisée produite par
l'API de backup; sa validité est établie par ses contrôles structurels, son
ledger et sa restauration bit-à-bit, pas par une égalité physique avec le seul
fichier `main` de la source.

Après gel des preuves, le backup et les deux copies de validation/recovery ont
été supprimés du répertoire temporaire. Ils ne sont pas récupérables; leurs
hashes et constats minimisés restent dans ce dossier.
