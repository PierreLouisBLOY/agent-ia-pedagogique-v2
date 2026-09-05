# Réinstallation et validation offline

Six environnements Python 3.12 vierges ont été créés hors dépôt : deux runtime, deux
calibration et deux dev. Les ensembles installés et leurs `pip freeze` normalisés sont
identiques par paire. Un des environnements dev reconstruit a ensuite exécuté les
24 tests dependency/config/alias : `24 passed`.
Le même venv dev a ensuite reçu le lock calibration depuis le wheelhouse offline ;
`pip check` et 41 tests d'intégration/transport Anthropic sur doubles ont passé sans
credential ni appel fournisseur.

Trois incidents méthodologiques, sans modification du résultat, sont consignés :

1. `venv` a refusé une première racine temporaire exprimée par l'alias Windows 8.3 ;
   aucune installation n'avait démarré et les preuves ont été reprises dans une racine
   longue distincte ;
2. un premier smoke runtime a demandé l'ancien import `httpx` après un `pip check`
   réussi ; le dépôt et le SDK résolu utilisent `httpx2`, puis les deux clean installs
   runtime ont été rejouées intégralement avec cet import ;
3. la suite globale a exclu explicitement la gate SQLite réelle non conditionnelle afin
   de respecter l'absence d'accès seed B05 ; les 23 autres gates réelles SQLite ont été
   ignorées faute de configuration V2.

```text
OFFLINE_REINSTALL = PASS
CLEAN_DEV_TARGETED = 24 passed
CLEAN_DEV_PLUS_CALIBRATION_TARGETED = 41 passed
NETWORK_USED_DURING_REINSTALL = FALSE
PROVIDER_CLIENTS_CONSTRUCTED = 0
CREDENTIALS_RESOLVED = 0
CANONICAL_SEED_ACCESS = 0
```
