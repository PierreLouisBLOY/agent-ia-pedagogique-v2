# Phase 12.17.8-B02 — Design de frontière de chemins

La primitive `backend.infrastructure.filesystem.security` applique dans cet ordre : chemin absolu, refus réseau/synchronisé pour les data roots, inspection de chaque composant existant, résolution physique, confinement physique, snapshot identité/état et erreur sans chemin local.

Les alias Windows valides, y compris une forme 8.3, sont acceptés lorsque leur résolution physique reste sous la racine. Un chemin lexical avec `..` qui sort de la racine reste refusé après normalisation et confinement physique.

`LocalSandboxFilesystemAdapter`, placé sous `backend/adapters/outbound/filesystem/`, lie un `SandboxRootRef` opaque à une racine absolue trusted. Les seules données retournées au runtime sont celles de `ResolvedSandboxPath`; aucun chemin OS absolu ne traverse le port.

L'inspection concrète vérifie extension, signature/MIME, taille, contenu actif DOCX et signatures exécutables. La lecture utilise un descripteur no-follow lorsque la plateforme le permet, compare l'identité avant/après ouverture et refuse tout changement d'état. La publication écrit un temp privé dans le répertoire cible, `fsync`, publie sans écrasement, puis réinspecte.

```text
PHYSICAL_CONTAINMENT = FAIL_CLOSED
ABSOLUTE_PATH_DISCLOSURE_ACROSS_PORT = 0
NETWORK_OR_SYNC_RUNTIME_ROOT = DENY
VALID_WINDOWS_PATHS = PRESERVED_AFTER_PHYSICAL_CONFINEMENT
```
