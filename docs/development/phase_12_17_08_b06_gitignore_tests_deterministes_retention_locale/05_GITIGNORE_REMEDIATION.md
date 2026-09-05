# Quatre familles, sept patterns

| Famille assignée | Patterns ajoutés |
|---|---|
| Backups et leurs manifests | *.bak, *.backup, *.bak.manifest.json, *.backup.manifest.json |
| Temporaires | *.tmp |
| Index en construction | *.building |
| Journaux structurés | *.jsonl |

Les règles des racines locales préexistantes sont conservées. Aucun *.json, *.md, *manifest* ni exclusion du source tree n'est ajouté.

Sept probes positives passent, ainsi que neuf probes négatives : manifests canoniques, preuves JSON, docs Markdown, migrations, package backend/adapters/outbound/artifacts, tests, pyproject et lock dev. La vérification complète de l'absence de masquage porte aussi sur tous les fichiers suivis de docs, architecture, database et requirements.

Un fichier ignoré ajouté de force à l'index reste dans l'inventaire et est rejeté par les guards. Huit cas couvrent DB, sidecar, backup, .env, local.env, log, building, temp.

ASSIGNED_GITIGNORE_FAMILIES = 4
FIXED_GITIGNORE_FAMILIES = 4
NEW_PATTERNS = 7
OVERBROAD_GITIGNORE_PATTERNS = 0
