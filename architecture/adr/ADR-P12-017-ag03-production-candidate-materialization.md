# ADR-P12-017 — Materialisation des candidats de production AG-03

## Statut

Accepte pour la Phase 12.8-D.

## Contexte

La frontiere 12.8-C produit un `GenerationPortResult` technique apres avoir
prepare et revalide un appel provider-neutral. Ce resultat ne constitue pas le
contrat canonique C-08 : il ne porte ni l'identite caller-supplied du candidat,
ni le metadata canonique adapte au statut observe, et ne doit acquerir aucune
autorite de validation ou de promotion.

## Decision

AG-03 expose `generate_production` pour CAP-G01 et `transform_production` pour
CAP-G02. Chaque operation delegue exactement une preparation et une execution au
`GenerationCoordinator`, puis retourne le `PreparedGenerationCall` et le
`GenerationPortResult` exacts.

La materialisation est une operation explicite ulterieure. Le caller fournit un
`ContractMeta[AgentResultStatus]` et une nouvelle `production_id`, car AG-03 ne
doit inventer ni identite, ni horodatage, ni lineage runtime. Le build revalide
la chaine C-07, appel prepare, resultat technique et metadata avant de construire
le `ProductionCandidate` C-08 existant.

`GenerationPortResult.execution_metadata` reste une donnee technique non fiable.
Avant toute construction C-08, un controle deterministe parcourt recursivement
ses mappings et collections et refuse le vocabulaire reserve a la validation,
l'approbation, la promotion, la confiance, la qualite canonique, aux gates et aux
permissions. Le refus est fail-closed ; aucune cle n'est filtree silencieusement.

Seuls les resultats `SUCCEEDED` et `PARTIAL` materialisent un candidat, avec un
statut canonique respectivement `SUCCEEDED` ou `PARTIAL`. Les resultats
`REFUSED` et `INSUFFICIENT_EVIDENCE` sont des issues nominales sans contenu et ne
produisent aucun candidat.

Une transformation cree toujours un nouveau candidat avec une `production_id`
caller-supplied. Elle conserve seulement le `target_ref` exact dans la lineage ;
elle ne charge, ne mute et ne parse pas la production cible et n'invente aucune
relation parent.

## Consequences et limites

- Le candidat reste dans l'etat canonique `CANDIDATE`.
- Le controle authority-free ne declare pas la metadata `SAFE` ou `TRUSTED` ; il
  bloque uniquement un vocabulaire d'autorite ferme.
- Les references de preuve utilisees restent un sous-ensemble de C-07.
- Aucune validation, review, promotion ou persistance n'est realisee.
- CAP-G03 et les contrats de correction sont differes a 12.8-E.
- Le grounding semantique, les controles pedagogiques et le hardening sont
  differes a 12.8-F.
- Le provider concret et le wiring runtime sont differes ; aucun dispatcher,
  retry ou fallback n'est introduit.
