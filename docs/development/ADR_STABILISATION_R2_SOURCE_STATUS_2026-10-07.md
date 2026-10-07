# ADR — Statuts de consultation générale R2

Statut : revue technique locale avant implémentation ; revue de PR requise.
Entrée : 629fabb6e49c258dd866c43c781172145777b2fc.

MD13 concerne une projection de consultation : CURRENT est la fraîcheur du
passage, CANONICAL/ACTIVE une identité, le cycle de vie et la validation sont
encore d'autres propriétés. Aucun de ces codes n'accorde l'autorité officielle.

Le successeur fermé SEARCH-SOURCE-STATUS-1.0 transporte ces axes séparément.
Les statuts sont lus dans les colonnes natives effectivement disponibles, avec
des noms de tables/champs fermés. Un champ absent reste UNKNOWN. Pour RESOURCE,
le passage ne désigne pas une resource_version exacte : son cycle de vie reste
UNKNOWN / EXACT_VERSION_REQUIRED jusqu'au fetch exact R6 déjà existant. Aucun
choix au maximum de date ni rapprochement par titre n'est ajouté.

La consultation DRAFT reste possible. L'admission de recherche vérifie le statut
courant et les identités du passage ; le fetch les relit. Le snapshot local
conserve le même statut jusqu'à la projection Application/HTTP. Les gardes de
construction institutionnelle et de dispatch P0 gardent leur propre autorité.
La forme historique sans statut reste lisible ; la forme successeure admet
uniquement son champ versionné, pas des clés arbitraires.

La revue exige un DRAFT consultable et visible, une substitution de statut
refusée, un changement entre recherche/fetch rendu visible ou refusé, CURRENT
distinct de PUBLISHED/admission, un schéma réduit explicite UNKNOWN, et le refus
des champs/statuts mal formés. Aucun SQL exécuté directement par l'agent, aucune
mutation de seed, aucun nouvel index aveugle ou migration runtime.
