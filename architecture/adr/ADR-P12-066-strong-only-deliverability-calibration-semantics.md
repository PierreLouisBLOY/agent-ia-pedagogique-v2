# ADR-P12-066 — Sémantique strong-only de livraison et de calibration

- Statut : Accepté
- Date : 2026-08-30
- Phase : 12.16-G2-V3-STRONG-ONLY-ANCHOR-REMEDIATION-A

## Contexte

Le corpus `12.16-g1-v2` est clôturé comme
`CLOSED_FAILED_HUMAN_PREVALIDATION_BASELINE`. Sa revue humaine confirme que les
huit contenus STRONG sont structurellement valides et reçoivent `16/16`
appréciations `TRES_SATISFAISANT`. En revanche, la relation ternaire complète ne
remplit pas la gate prévue : `4/16` ordres stricts, `15/16` ordres faibles, une
inversion et seulement `11/16` critères perceptiblement différenciés.

Le produit ne doit pas livrer un contenu intermédiaire ou faible. La décision
durable porte donc sur la frontière de livrabilité, pas sur la transformation
d'un libellé humain en règle métier. ADR-P12-065 reste l'historique exact de la
version v2 et n'est pas modifié rétroactivement.

## Décision

La politique de livraison est `STRONG_ONLY`. Dans la calibration primaire, un
anchor STRONG représente un `DELIVERY_CANDIDATE`; les tiers MIXED et
WEAK_BUT_STRUCTURALLY_VALID représentent des
`NON_DELIVERABLE_NEGATIVE_CONTROL` distincts.

La séparation primaire est :

```text
STRONG > MIXED
STRONG > WEAK_BUT_STRUCTURALLY_VALID
```

L'ordre relatif MIXED/WEAK et l'objectif ternaire strict restent calculés pour
le diagnostic de sévérité, la construction de cas négatifs et les futures
remédiations. Ils sont secondaires et non bloquants dès lors que les deux
contrôles sont humainement séparés de STRONG.

Les libellés `TRES_SATISFAISANT`, `SATISFAISANT`, `FRAGILE` et `INSUFFISANT`
ne deviennent ni seuil runtime, ni autorité métier, ni contrat de livraison.
Un résultat de scorer n'est pas un résultat runtime; un model judge n'est pas
un validateur de domaine; un fournisseur n'est pas une autorité; une route de
modèle n'approuve aucune gate.

Le corpus `12.16-g1-v3` reste un owner test-only. V1 et v2 demeurent immuables.
Le GateEngine, les routes runtime, les adaptateurs fournisseurs et les contrats
métier ne sont pas modifiés dans ce lot. Toute calibration fournisseur reste
interdite tant que la prévalidation humaine delta v3 et une autorisation
propriétaire ultérieure ne sont pas acquises.

## Conséquences

- Les huit contenus STRONG v3 restent pédagogiquement byte-equivalent à v2.
- Les contrôles négatifs sont révisés seulement lorsque la preuve v2 ne sépare
  pas le contrôle de STRONG sur au moins un critère du scénario.
- Un manifeste par hash justifie tout carry-forward et toute révision.
- La gate humaine v3 bloque sur STRONG contre chacun des deux contrôles, sur la
  structure et sur l'absence de non-évaluable.
- Les relations MIXED/WEAK restent publiées comme diagnostic secondaire.
- Aucun seuil de release produit n'est adopté et aucun appel live n'est
  autorisé par cette décision.

## Options écartées

- Continuer d'exiger `STRONG > MIXED > WEAK` comme gate primaire : rejeté, car
  cette relation dépasse la frontière de livrabilité décidée.
- Fusionner MIXED et WEAK : rejeté, car leurs différences restent utiles aux
  diagnostics et aux stratégies de remédiation.
- Modifier v2 : rejeté, car sa baseline humaine échouée doit rester
  reproductible.
- Propager `STRONG_ONLY` dans le runtime dans ce lot : rejeté, car la
  calibration test-only n'a aucune autorité pour modifier le GateEngine ou la
  politique métier.
