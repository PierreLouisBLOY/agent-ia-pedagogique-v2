# ADR-P12-026 - Sandbox policy et frontiere filesystem

## Statut

Accepte pour la Phase 12.10-C.

## Contexte

La Phase 12.10-B a etabli des ToolDescriptors locaux pour CAP-T02 et CAP-T03.
Ils declarent le profil `sandbox.local_file_transform.v1`, mais aucun modele de
profil, aucune validation de chemin et aucune frontiere filesystem n'existaient.

Le sandbox doit borner des I/O techniques deja autorisees. Il ne peut ni
selectionner un tool ou une capability, ni accorder une permission, ni resoudre
une gate. L'ordre d'autorite futur reste :

```text
CapabilityAuthorizationPolicy
-> ToolCallPolicy
-> SandboxPolicy
-> ToolRouter/handler
```

## Decision

### Placement

Le package pur `backend/agent_runtime/sandbox/` contient les modeles, le
registry de profiles, la policy et un port filesystem. Il est voisin de
`registry/` et `policy/` car il constitue une frontiere technique transverse,
et non un etat ou un moteur d'execution du runtime.

### Profile baseline

`sandbox.local_file_transform.v1` autorise seulement :

- inputs : `.docx`, `.md`, `.pdf`, `.txt` ;
- outputs : `.docx`, `.pdf`, `.txt` ;
- MIME : PDF, DOCX OpenXML, Markdown et texte brut ;
- 25 MiB par input ;
- 50 MiB par output ;
- 20 fichiers maximum.

Symlinks, contenu actif, contenu executable et chemins reseau sont desactives.
HTML et archives ne sont pas admis. Les extensions actives ou executables
restent explicitement interdites, independamment de l'allowlist.

### Chemins

`SandboxRelativePath` conserve exactement la chaine validee. Il ne nettoie,
ne decode et ne resout rien. Sont refuses avant construction : chemins absolus,
drives Windows, UNC, URI, backslashes, segments vides, `.`/`..`, controls, `~`,
colons, Unicode non NFC, noms Windows reserves, trailing dots/spaces et bornes
de longueur depassees.

Cette validation est lexicale. Elle ne pretend pas prouver le confinement
apres resolution de liens.

### Root et resolution trusted

`SandboxRootRef` ne transporte que `run_id` et `root_id` opaques. La
correspondance avec un chemin OS absolu appartient a un adapter futur hors
`agent_runtime` et ne peut pas provenir d'un tool ou d'un LLM.

`ResolvedSandboxPath` transporte une preuve trusted data-only : root et chemin
exacts, token canonique opaque, confinement, existence, type fichier, symlink,
taille, extension/MIME observes et indicateurs de contenu actif/executable.
Aucun chemin absolu n'est expose.

`SandboxFilesystemPort` declare seulement `resolve` et `inspect`. C ne fournit
aucune implementation, lecture, ecriture ou resolution OS.

### Policy

`SandboxPolicy` ne connait ni ToolCallPolicy, ni PermissionScopeEvaluator, ni
handler. Elle verifie le profile exact, l'operation READ/WRITE/CREATE, le chemin
relatif, la coherence de la resolution trusted, les limites et les formats.
`EXECUTE` n'appartient pas au vocabulaire et toute tentative est refusee.

READ utilise exclusivement les metadata observees trusted pour MIME et taille.
WRITE/CREATE borne les metadata de sortie declarees, sans les traiter comme une
preuve du type produit : D devra inspecter l'artefact concret avant toute
consommation ou promotion.

Un echec ne recopie jamais le chemin hostile dans un reason string.

### Binding B vers C

La coherence est unidirectionnelle : les tests de configuration parcourent le
ToolRegistry et prouvent que chaque LOCAL_FILE_TRANSFORM reference un profile
existant. Le SandboxProfileRegistry n'importe et ne modifie pas le ToolRegistry,
ce qui evite tout cycle.

## Consequences

- C reste data-only et provider-neutral.
- La distinction entre `SandboxOperation` et `PermissionOperation` est
  preservee.
- La policy refuse un symlink et une preuve hors root sans tenter de les
  resoudre lexicalement.
- Le mapping root vers chemin OS, les I/O, handlers, conversions et inspections
  concretes restent differes a D ou a un adapter explicitement autorise.
- Aucun support de format n'est revendique au-dela de l'allowlist de securite ;
  le binding d'un convertisseur concret reste une decision future.

## Rationalisation

Les registries existants donnent une convention locale, mais leurs identifiants
et invariants ne partagent pas la meme autorite. Les modeles evidence,
generation et review traitent du contenu metier/LLM, pas de confinement
filesystem trusted. Aucun validateur de chemin relatif canonique ni modele de
metadata filesystem equivalent n'existe.

Fusionner ces responsabilites creerait un couplage d'autorite premature.

```text
NO_SAFE_CONSOLIDATION_REQUIRED
```
