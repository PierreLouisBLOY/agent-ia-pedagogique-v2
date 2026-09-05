# Seed, runtimes temporaires et migration 002

## Identité et absence de dérive

SHA authentifié avant SQLite : `38ca8b3fe5c4fd14e9a4cc60a252e7eb03b1f8a8b5fc26ef62251d2b73e35134` ; 105553920 octets. WAL préexistant vide, SHM préexistant 32768 octets, journal absent.

Les snapshots JSON bruts PRE/POST sont identiques, y compris présence, taille, mtime_ns, SHA, device et inode. Leur comparaison est faite avant conversion numérique susceptible de perdre de la précision. Les empreintes minimisées sont en 13. Aucun checkpoint, suppression ni changement de permissions.

## Correction attestée

`test_seed_gate_is_exact_and_read_only` conserve son nom et son refus de CREATE TABLE. Il authentifie le jeu de fichiers, appelle le lecteur existant avec `readonly=True, immutable=True`, ferme explicitement la connexion et contrôle le jeu principal/sidecars en finally. Le fixture de module authentifie aussi avant inspection et contrôle après utilisation.

Huit régressions couvrent identité manquante/taille/hash, URI ro+immutable avec caractères spéciaux, fermeture, rejet d'écriture et détection d'une dérive WAL/SHM/journal sur doubles/fixtures. Aucun défaut du lecteur runtime n'a changé.

Résultats : test réel ciblé PASS, puis **24/24 tests seed réels PASS dans le global**, dont les parcours SQLite Application/Search/RAG et les deux runtimes du retrieval. Le premier risque d'ouverture non immutable n'a jamais été présenté comme une écriture constatée.

## Migration disponible versus déploiement

- 001 inchangée : `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102`.
- 002 inchangée : `e43b6267a5c4e0686739d4c0ea68d22e74f354bd9cbffb3f89b673e5bd0fe893`.
- Fresh/existing/replay/checksum/rollback/recovery testés sur runtimes temporaires, sans migration du seed. Les résultats sélectionnés et les preuves 05B compatibles sont liés en 13 et dans le snapshot 08.
- Runtime utilisateur : 002 **NOT_APPLIED_LAST_ATTESTED** ; aucune nouvelle inspection physique ni migration. Un succès sur copie ne prouve pas son déploiement.

```text
CANONICAL_SEED_OBSERVED_PRE_POST_DRIFT = 0
CANONICAL_SEED_OR_SIDECAR_MODIFICATION_PERFORMED = 0
USER_RUNTIME_ACCESS_BY_B07 = 0
USER_RUNTIME_WRITES = 0
USER_RUNTIME_MIGRATION_002_PERFORMED = FALSE
REAL_SEED_TEST_SUITE_B07 = 24/24 PASS
```
