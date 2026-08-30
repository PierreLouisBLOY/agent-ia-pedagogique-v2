# ADR-P12-064 — Politique homogène explicite du juge Anthropic

- Statut : Accepté
- Date : 2026-08-30
- Phase : 12.16-G2-R3B-R4-R1

## Contexte

Le premier appel de la matrice R4 a reçu une réponse Anthropic avec
`stop_reason=max_tokens`, `output_tokens=512` et aucun bloc texte. La limite de
512 tokens a donc été épuisée avant la production du résultat structuré. La
télémétrie historique ne permet pas d'affirmer que tous ces tokens étaient des
thinking tokens.

Le transport envoyait jusqu'alors ni paramètre `thinking`, ni
`output_config.effort`. Avec Claude Sonnet 5, cela active implicitement
l'adaptive thinking au niveau d'effort `high`. Le transport ne comptait pas les
thinking blocks et ne conservait pas
`usage.output_tokens_details.thinking_tokens`.

Les cinq scores Anthropic historiques ont été produits sous cette politique
implicite. Les mélanger à de nouveaux scores issus d'une politique explicite
rendrait la population finale hétérogène.

## Décision

Le scorer Anthropic privé adopte la politique suivante :

```text
thinking = adaptive explicite
effort = low explicite
max_tokens = 2048
retry = 0
```

La requête SDK utilise `thinking: {type: adaptive}` et
`output_config.effort: low`, sans outil et sans streaming. Le transport compte
séparément les text blocks et thinking blocks et conserve uniquement le nombre
de thinking tokens. Aucun contenu de raisonnement, header, body, request ID ou
secret n'est conservé.

Les cinq scores Anthropic historiques restent intacts et deviennent
`DIAGNOSTIC_ONLY_NOT_FINAL_CALIBRATION`. La population de calibration finale
sera recalculée uniformément sur les 76 slots Anthropic originaux : 48 anchors
initiaux, 16 répétabilités et 12 scores de sorties sélectionnées. Les 20
résultats OpenAI historiques restent réutilisables uniquement pour alimenter les
projections des six productions selected-output.

Un canary one-shot doit d'abord valider la nouvelle politique sur le slot
`cal.score.anchor.scn-01.c.organization-utility.r1`. Les 75 autres appels sont
conditionnés à un canary PASS hash-valid et à de nouvelles approbations
financière et de transfert externe.

## Options examinées

### Thinking désactivé, 512 tokens

Rejeté. Cette option réduit le coût mais supprime le raisonnement du juge et
constitue un changement méthodologique trop fort.

### Adaptive explicite, effort low, 2048 tokens

Retenu. Le raisonnement est conservé, l'effort est borné pour une tâche de
classification courte et la sortie dispose d'un headroom multiplié par quatre.

### Adaptive implicite high avec une limite supérieure

Rejeté. Le niveau `high` implicite reste coûteux, non explicite et inadapté à
une calibration volumique homogène.

## Conséquences

- Les contrats publics du harness, `EvaluationScorerPort` et `ScorerOutcome`, ne
  changent pas.
- Les extensions restent privées au transport et au scorer Anthropic.
- Les constructeurs privés conservent des defaults compatibles avec les tests
  et fakes existants.
- Le coût maximal devient 0.036480 USD par appel selon les bornes gelées.
- Le canary demande un plafond de 0.045600 USD avec marge de 25 %.
- La completion conditionnelle de 75 appels demande un plafond de 3.420000 USD.
- Aucun ancien ledger n'est modifié et aucun record terminal n'est rappelé.
- Cette décision n'accorde aucune autorité métier au scorer et n'autorise aucun
  appel provider par elle-même.

## Garde-fous

- Un appel, un effet ; aucun retry ou rerun automatique.
- `STARTED` après interruption reste ambigu et bloque la reprise.
- Un résultat terminal n'est jamais rappelé.
- Arrêt au premier échec technique.
- Ledgers R2 et R3 distincts et ignorés par Git.
- Aucune base SQLite n'est transférée.
- Les approbations liées aux anciennes matrices ne sont pas réutilisées.
