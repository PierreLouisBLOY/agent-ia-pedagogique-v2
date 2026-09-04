# Phase 12.17.7B — Cinq cibles exactes de minimisation

```text
MINIMIZATION_TARGETS_IDENTIFIED = 5/5
MINIMIZATION_APPLIED = 0/5
OWNER_OPTION = OPTION_A_MINIMIZE_FIVE_AND_CONSOLIDATE_165
TARGET_BATCH = 12.17.8-B01
```

## MIN-01

- **Original identity** : `docs/development/phase_12_17_03d_external_sqlite_evidence/10_DESKTOP_PROJECT_V2_DISCOVERY.md`, SHA-256 `e3209757a7473176fa758c9a3b60313b282007f234e0a5d61ac665a85ba38f7b`.
- **Reason for minimization** : cinq occurrences exposent le profil utilisateur et des localisateurs Desktop qui n'apportent rien au résultat de découverte.
- **Preserved evidence** : locator initial absent, locator ensuite fourni par l'owner, fichier exact trouvé, arrêt fail-closed antérieur et aucune recherche disque globale.
- **Removed redundancy** : ligne de racine Desktop et répétitions des chemins absolus.
- **Resulting canonical representation** : `PROJECT_FOLDER_PATH = <LOCAL_PROJECT_ROOT>` et `SQLITE_PATH = <CANONICAL_SEED_PATH>`; le locator absent devient `<LOCAL_PROJECT_ROOT>/base_pedagogique_v2.sqlite`.
- **Historical source untouched now / after B01** : `TRUE / FALSE`.

## MIN-02

- **Original identity** : `docs/development/phase_12_17_03d_external_sqlite_evidence/12_READ_ONLY_INTEGRITY_EVIDENCE.md`, SHA-256 `72f400f711613a090cd34b7a868ec2b86b0e16d533d86ca557997b3c1a4e8e37`.
- **Reason for minimization** : l'URI SQLite encode le profil et le chemin local complet.
- **Preserved evidence** : ouverture URI read-only avec `mode=ro&immutable=1`, résultats d'intégrité et checksum.
- **Removed redundancy** : composante locale de l'URI.
- **Resulting canonical representation** : `SQLITE_PATH = <CANONICAL_SEED_PATH>` et `READ_MODE = mode=ro&immutable=1` sur deux champs séparés.
- **Historical source untouched now / after B01** : `TRUE / FALSE`.

## MIN-03

- **Original identity** : `docs/development/phase_12_17_03d_external_sqlite_evidence/14_IMMUTABILITY_PRE_POST.md`, SHA-256 `c1ae2ff9b34cb8ccc9488a3f41454acfd36f02f958c58c1ba4cd0be784fc7ecd`.
- **Reason for minimization** : le chemin personnel est répété alors que l'identité utile est le SHA PRE/POST.
- **Preserved evidence** : même fichier logique, snapshots avant/après, taille, timestamps et SHA byte-identiques.
- **Removed redundancy** : locator absolu personnel.
- **Resulting canonical representation** : `<CANONICAL_SEED_PATH>`.
- **Historical source untouched now / after B01** : `TRUE / FALSE`.

## MIN-04

- **Original identity** : `docs/development/phase_12_17_03d_external_sqlite_evidence/16_FINAL_HANDOFF.md`, SHA-256 `774781732408e8486bf8a92aab869a338c39fce95a3e0301dc221a8c50c3c6fb`.
- **Reason for minimization** : trois champs de handoff recopient le profil/Desktop et le chemin complet.
- **Preserved evidence** : seed exact authentifié, preuve read-only, gate et verdict final.
- **Removed redundancy** : `DESKTOP_PATH_RESOLVED` et valeurs absolues de projet/SQLite.
- **Resulting canonical representation** : `PROJECT_FOLDER_PATH = <LOCAL_PROJECT_ROOT>` et `SQLITE_PATH = <CANONICAL_SEED_PATH>`.
- **Historical source untouched now / after B01** : `TRUE / FALSE`.

## MIN-05

- **Original identity** : `docs/development/phase_12_17_04_rationalization_design_gate/12_FINDINGS_AND_RISKS.json`, SHA-256 `08dc0d8da4dd2e9684cf64e04098674a8ea4234a3b5e84e9e7e7385ed6ba9999`.
- **Reason for minimization** : une valeur de preuve transporte un locator Desktop complet, non requis pour la cause RAT-007.
- **Preserved evidence** : constat de non-portabilité, statut DESIGN_READY, contrôle propriétaire OD-08 et cible de configuration V2.
- **Removed redundancy** : unique chaîne de chemin absolu.
- **Resulting canonical representation** : `"<CANONICAL_SEED_PATH>"`.
- **Historical source untouched now / after B01** : `TRUE / FALSE`.

## Manifestes futurs à rebinder

Les cinq cibles sont actuellement couvertes par deux manifestes :

- `docs/development/phase_12_17_03d_external_sqlite_evidence/MANIFEST_SHA256.txt`, SHA-256 actuel `600a4bee4b1b536c93a30eeae0aa02a80ae2e37956b47ee5533cbbb306b63b9a` ;
- `docs/development/phase_12_17_04_rationalization_design_gate/MANIFEST_SHA256.txt`, SHA-256 actuel `1aba15a7e56a15b97b35485f5dc1ba523a5e421f7fcc2644c2c051c7299c71b5`.

B01 doit produire les cinq SHA post-minimisation, les deux transitions de manifestes, une preuve d'équivalence et un scan confirmant zéro localisateur personnel résiduel. Aucun changement n'est effectué en 12.17.7B.
