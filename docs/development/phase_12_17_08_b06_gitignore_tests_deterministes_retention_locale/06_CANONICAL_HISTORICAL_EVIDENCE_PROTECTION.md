# Protection des preuves

Les 209 chemins de l'allowlist de staging B01 restent suivis. Les 1 001 chemins canoniques suivis PRE (docs, architecture, database, requirements) restent non masqués.

Le guard dédié vérifie les 40 entrées du freeze B01 avec le helper historique existant, sans modifier ce helper ni les preuves. Les sept dérives préexistantes sont reconnues par le freeze ; aucune réparation rétroactive n'est autorisée. Le fichier de freeze lui-même est comparé à la baseline B05.

Le diff attendu ne touche aucun manifest antérieur, aucune migration ni lock B05. ENVIRONMENT.md est la seule documentation existante modifiée, conformément au périmètre B06.

CANONICAL_B01_TRACKED = 209/209
HISTORICAL_FREEZE = 40/40 PASS (tests ciblés)
KNOWN_PREEXISTING_DRIFTS = 7/7 PRESERVED
HISTORICAL_MANIFEST_CONTENT_CHANGES = 0
HISTORICAL_EVIDENCE_DELETIONS = 0
