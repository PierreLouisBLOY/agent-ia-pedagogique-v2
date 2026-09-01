# Phase 12.16-G2-V5.1 — Fidélité de la projection Mixed

## Comparaison champ par champ

L'anchor canonique local `cal.v4.scn-06.a74ef2a40cb1` contient exactement trois
sections, dans cet ordre :

1. `instructions` — répondre aux deux questions sans forme de calcul, unité ou
   justification explicitement attendue;
2. `questions` — calcul de TVA sur 200 unités hors taxe à 20 %, puis calcul du TTC;
3. `marking-scheme` — six points globaux si l'ensemble paraît correct, sans
   répartition par question, formule, application numérique, résultat ou unité.

`CalibrationAnchor.candidate_projection()` sérialise ces trois sections dans le même
ordre, sous la forme `[section] contenu`, séparées par un seul saut de ligne.

L'enveloppe canonique reconstruite hors ligne présente :

- le même `observation_id`;
- les mêmes trois sections, le même texte, le même ordre et les mêmes séparateurs;
- `candidate_projection == anchor.candidate_projection()` : `true`;
- hash SHA-256 du seul texte candidat :
  `7013f3516127fcef95bcb846584db26d2b185074713f18a042444e7a8a2a6756`;
- ce même hash dans le ledger sous `source_projection_sha256`;
- hash du payload de transfert complet :
  `67f465002c21186b552ba62289fe49ce765c75f9ccb99a8cad088ece44fa1b7a`,
  identique à l'allowlist et au ledger.

## Effet sémantique

La projection ne supprime aucun élément positif, ne modifie aucune structure et
n'omet aucun barème présent dans l'anchor. Le contexte de scénario et la rubrique
V5 sont ajoutés dans les autres champs du payload; ils ne remplacent pas le candidat.

La faiblesse observée — barème global et absence explicite des quatre attributions
analytiques — appartient donc à l'anchor canonique lui-même.

## Résultat

`PROJECTION_SEMANTIC_FIDELITY = PASS`
