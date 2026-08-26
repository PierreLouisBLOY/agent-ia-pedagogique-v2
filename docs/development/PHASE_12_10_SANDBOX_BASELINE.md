# Baseline Phase 12.10-C - Sandbox policy boundary

## Statut et perimetre

Le lot C descend directement du commit B
`907614a6c20758565530d84b63ca5f224bf7a4a8` sur la branche
`phase12/12-10-routing-gates-sandbox`.

Il livre seulement :

```text
SandboxProfile + SandboxProfileRegistry
+ SandboxRelativePath + SandboxRootRef + ResolvedSandboxPath
+ SandboxPolicy + SandboxFilesystemPort
```

Il ne livre aucun ToolRouter, UseCaseRouter, GateEngine, handler, adapter
filesystem, I/O, subprocess, shell, reseau, provider ou integration runtime.

## Frontiere d'autorite

Le sandbox ne cree aucune autorisation. Il borne une operation technique apres
un ALLOW produit par les policies capability et tool. Il ne connait aucun
PermissionScope et ne choisit ni tool, capability, profile, root, gate ou
handler depuis des arguments non trusted.

## Profile baseline

| Champ | Valeur |
| --- | --- |
| ID | `sandbox.local_file_transform.v1` |
| Inputs | `.docx`, `.md`, `.pdf`, `.txt` |
| Outputs | `.docx`, `.pdf`, `.txt` |
| MIME | PDF, DOCX OpenXML, Markdown, texte brut |
| Input max | 25 MiB |
| Output max | 50 MiB |
| Fichiers max | 20 |
| Symlinks | interdits |
| Active/executable content | interdit |
| Network paths | interdits |

HTML, archives, scripts, executables, formats Office a macros et shortcuts sont
absents de l'allowlist. Un MIME declare ne constitue jamais une preuve du type
reel.

## Chemin relatif canonique

`SandboxRelativePath` accepte uniquement une forme relative conservee telle
quelle avec `/`. Il refuse :

- chemins absolus Unix ou drives Windows ;
- UNC, URI reseau et `file://` ;
- backslashes, colons et `~` ;
- segments vides, `.` et `..` ;
- NUL/control chars et Unicode non NFC ;
- noms Windows reserves et trailing dots/spaces ;
- plus de 1 024 caracteres, 32 segments ou 255 caracteres par segment.

Aucun chemin hostile n'est nettoye puis accepte.

## Root et frontiere filesystem

`SandboxRootRef(run_id, root_id)` contient seulement des identifiants opaques.
Le mapping vers un root OS est hors `agent_runtime`.

`SandboxFilesystemPort` est un Protocol `resolve`/`inspect` sans implementation.
Son resultat `ResolvedSandboxPath` transporte un token canonique opaque et des
metadata trusted, dont la preuve de confinement et le statut symlink. Aucun
absolute path n'entre dans les modeles.

## SandboxPolicy

Operations fermees :

```text
READ
WRITE
CREATE
```

Dispositions : `ALLOW` et `DENY`.

Codes :

```text
ALLOW
UNKNOWN_PROFILE
INVALID_RELATIVE_PATH
ABSOLUTE_PATH_FORBIDDEN
TRAVERSAL_FORBIDDEN
NETWORK_PATH_FORBIDDEN
SYMLINK_FORBIDDEN
ROOT_MISMATCH
PATH_MISMATCH
EXTENSION_FORBIDDEN
MIME_FORBIDDEN
INPUT_TOO_LARGE
OUTPUT_TOO_LARGE
FILE_COUNT_EXCEEDED
ACTIVE_CONTENT_FORBIDDEN
EXECUTION_FORBIDDEN
INVALID_METADATA
```

READ exige des metadata observees trusted. WRITE/CREATE verifient les bornes et
formats declares, qui devront etre controles a nouveau sur la sortie concrete
par la future implementation. Toute demande `EXECUTE` est refusee.

## Binding B vers C

Les deux ToolDescriptors B `tool.render_document` et `tool.convert_format`
referencent exactement `sandbox.local_file_transform.v1`. La preuve transverse
est portee par un test d'integration ; aucun import inverse n'existe depuis le
registry sandbox.

## Rationalisation

L'audit des validators, registries, modeles de metadata et scanners existants
ne trouve aucune primitive partageant a la fois la semantique, les invariants et
la frontiere d'autorite filesystem de C.

```text
RATIONALIZATION = NO_SAFE_CONSOLIDATION_REQUIRED
```

## Validation

Resultats executes avec Python 3.12.13 :

- `tests/unit/test_sandbox_profiles.py` : 22 PASS ;
- `tests/unit/test_sandbox_policy.py` : 24 PASS ;
- `tests/unit/test_sandbox_paths.py` : 39 PASS ;
- binding integration B vers C : 3 PASS ;
- fitness architecture sandbox : 8 PASS ;
- regression ciblee B+C : 149 PASS ;
- suite globale : 2 505 PASS ;
- `compileall` : PASS ;
- Ruff : PASS ;
- mypy : PASS sur 533 fichiers source ;
- dependencies runtime : `[]`.

L'audit securite et Git final complete cette matrice avant le commit de
cloture.

## Suite

Le prochain lot autorise est 12.10-D. Aucun routing ou handler n'est commence en
C.
