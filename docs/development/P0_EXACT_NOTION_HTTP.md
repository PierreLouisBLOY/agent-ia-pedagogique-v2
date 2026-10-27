# P0 — sélection de références par notion exacte

Compagnon public `P0-NOTION-EVIDENCE-HTTP-1.0`. Cette adaptation inbound réutilise
`GetExactNotionEvidenceQuery` via `exact_notion_evidence(target)` et le lecteur
Application existant. Elle ne crée aucune autorité, source ou voie SQL pour les
agents. Les tuples historiques READ15/R2/R3/R4 et P0 restent inchangés ; un tuple
GET compagnon distinct est enregistré dans le même registre local fermé.

## Requête

`GET /api/v2/p0/notion-evidence?notion_id=<identifiant encodé une fois>`

`X-Local-Intent: conversation-v1` et les protections Host/Origin/Sec-Fetch-Site
du canal P0 existant restent applicables. Aucune donnée dans le corps GET. Le
seul paramètre est `notion_id`, une identité logique exacte `notion:` bornée à
256 caractères. Aucun alias, chemin, label, sélection arbitraire, version de
remplacement ou fallback n'est interprété. Le budget brut d'URL reste celui
du serveur existant : 8 KiB. Les requêtes invalides sont refusées avant lecture
Application et avant tout accès à la cible.

## Projection

Enveloppe `data` et `meta` avec le contrat compagnon et l'identité de corrélation.
`data` contient `notion_id`, `status=CANONICAL`, `retrieval_path`,
`available_authority=UNKNOWN`, `authority_basis=NOT_ATTESTED_BY_APPLICATION`,
`items` et `exclusions`.

Chaque candidat complet `NOTION`, `PEDAGOGICAL_CONTENT` ou `METHOD` conserve :

- `object_ref`, `object_kind`, `passage_ref`, `version_or_checksum` ;
- les `provenance` et `source_status` natifs, sans transformer CURRENT/ACTIVE,
  REVIEW ou UNKNOWN en admission ; `source_status=null` seulement si la query
  ne possède effectivement aucun statut ;
- l'`excerpt` exact non vide, `excerpt_truncated=false` et son SHA-256 UTF-8 ;
- l'autorité UNKNOWN et `selection={notion_id,passage_ref}` pour la préparation.

Les passages tronqués/vides et les autres types figurent dans `exclusions`,
avec identités/statuts/provenance et raisons explicites. Aucun extrait complet,
réponse, sélection active ou SHA de texte absent n'est inventé pour ces lignes.
Cette candidature d'identité n'est ni une admission de source/transmission, ni
une résolution institutionnelle, ni une preuve d'absence d'oracle. Le parcours
P1 exige ses reçus d'admission distincts et le contexte exact résolu Application.

La préparation utilise la paire exacte retournée et **relit** la notion et le
passage via Application. Une sélection ancienne ne remplace jamais cette
revalidation ; le navigateur n'atteste pas son propre contexte ou son autorité.

## Bornes et refus

Maximum 256 passages ; réponse HTTP maximum 64 KiB, réutilisant la limite de
recherche locale existante. Si une borne est dépassée, la requête reçoit 413 et
une raison précise, sans résultat partiel ni troncature silencieuse pour rentrer
dans le budget. Les sources restent conservées dans la cible.

- 400 `P0_REFERENCE_REQUEST_REJECTED` : requête, méthode ou corps invalide ;
- 404 `P0_NOTION_NOT_FOUND` : identité non canonique ou absente ;
- 413 `P0_REFERENCE_ITEM_LIMIT_EXCEEDED` / `P0_REFERENCE_RESPONSE_LIMIT_EXCEEDED` ;
- 500 projection/erreur Application minimisée : aucun chemin, extrait ou secret
  de l'erreur ne sort ;
- 409 `P0_REFERENCE_NOT_ENABLED` : composition explicite sans lecteur injecté.

La factory normale injecte ce lecteur en lecture seule sur sa cible authentifiée.
La route n'autorise aucun appel fournisseur, COUNT, credential, enrichissement
officiel, promotion ou signature de recette enseignante.
