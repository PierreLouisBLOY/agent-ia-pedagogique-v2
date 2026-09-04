# Phase 12.17.6 — Sécurité des entrées et du filesystem

## Gardes établis

- `SandboxRelativePath` refuse chemins vides, absolus, UNC, URI réseau, `file:`, backslashes, contrôles Unicode, non-NFC, `:`, `~`, caractères Windows réservés, segments `.`/`..`, longueur et profondeur excessives.
- Le profil local autorise seulement `.docx`, `.md`, `.pdf`, `.txt` en entrée et `.docx`, `.pdf`, `.txt` en sortie, avec 25 MiB par entrée, 50 MiB par sortie et 20 fichiers au total.
- Symlinks, chemins réseau, contenu actif et contenu exécutable sont refusés.
- Le routeur exige une résolution et une inspection via une frontière de confiance, refuse les résultats hors cibles autorisées, puis réinspecte chaque sortie après exécution.
- Les arguments et résultats outils rejettent les clés d'autorité et les formes sensibles, y compris chemins absolus privés et credentials.
- `CREATE` exige une cible absente ; `WRITE` exige un fichier existant compatible. Une sortie réussie doit produire exactement les chemins déclarés.

## Surfaces absentes

Le port `SandboxFilesystemPort` indique explicitement qu'aucune implémentation concrète n'est fournie. Le module `materialization_export` est structurel. Aucun code d'extraction ZIP/TAR n'est présent. Il n'existe donc pas d'import/export produit actuellement exploitable, mais les garanties de résolution physique de symlink/junction, de TOCTOU et d'écriture atomique ne sont pas démontrables en production.

## Verdict

`PATH_TRAVERSAL_STATUS = PASS_CONTRACT_LEVEL`

`IMPORT_EXPORT_SAFETY_STATUS = PARTIAL_NO_CONCRETE_IO_ADAPTER`

Finding associé : `FILE-001`, non bloquant pour le plan 12.17.7 mais à corriger avant exposition réelle.
