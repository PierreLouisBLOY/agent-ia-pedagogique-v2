# Phase 12.17.5B-B05 — Tests ciblés

| Sélection | Résultat |
|---|---:|
| contrat `ResourceRef`, Application, persistence, READ-15 et handoff | `67/67 PASS` |
| régression B02/B03/B04 et guards B08 | `62/62 PASS` |
| total ciblé final | `129/129 PASS` |
| architecture B05 | `12/12 PASS` |
| architecture carry-forward | `17/17 PASS` |

La sélection B05 couvre :

- valeurs valides aux bornes 1 et 128 ;
- longueur 129, ponctuation initiale, espaces, `/`, `?`, `#`, contrôles et
  Unicode hors contrat ;
- erreur typée et message sans valeur rejetée ;
- invalid-ref avant lookup et not-found séparé ;
- payload exact READ-15, rejet de `version_ref` et `include` ;
- propagation DTO/port/adapters sans deuxième regex ;
- mapping SQLite sans modification de la valeur ;
- gate réelle SCN-01 sur runtime temporaire et seed inchangé ;
- handoff B09 toujours documentaire, sans endpoint ni SQL direct.

Une première invocation de la gate réelle a rencontré l'alias legacy hérité
pointant vers un lecteur non accessible. Après liaison explicite des deux noms
de configuration au même seed vérifié, la sélection finale complète a passé
`67/67`. Ce diagnostic local n'a produit aucune écriture SQLite.
