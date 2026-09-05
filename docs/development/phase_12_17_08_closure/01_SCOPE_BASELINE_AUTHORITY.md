# 12.17.8-B07 — Périmètre, baseline et autorité

Baseline de référence : `0404852a3be77381bf7b7c903ee6309e2547487e`. Baseline technique corrigée et testée : `f28b29f0964d2642b74eb7098f90359d15fb4f0c`.

Le propriétaire a explicitement autorisé le correctif limité du test seed, sa non-régression, les preuves et un commit local borné, puis la reprise B07. Le bundle de reprise (SHA `a800457b1fb42e5ec0f18c49240b723eb9e3ec51f6c4ab76b2cf60f9f8500869`, quatre entrées vérifiées) confirme cette séquence ; il ne crée pas de permission supplémentaire.

## Périmètre appliqué

- B07 conserve le titre canonique **Ré-audit transverse et clôture**, sept lots et seize gates.
- L'exception technique porte seulement sur le test identifié et ses huit régressions. Les quatre fichiers du commit correctif sont listés en 13 ; le code applicatif est inchangé.
- Le seed est authentifié par SHA avant toute ouverture SQLite du test, puis ouvert read-only + immutable. Les lecteurs runtime gardent leur comportement existant.
- Configuration de validation uniquement dans le processus : même valeur seed, runtimes et caches temporaires hors dépôt. L'accord préalable « Oui, uniquement pour la validation B07 » est conservé.
- Aucun seed/sidecar/utilisateur modifié, aucune migration utilisateur, configuration persistante, opération fournisseur, résolution réseau, suppression, push ou merge.
- La transaction suivante est documentaire uniquement. Elle ne réécrit aucun manifeste historique et ne touche aucun des 40 fichiers gelés.
- 12.18 ne doit pas commencer. La clôture de 12.17.8 ne vaut pas clôture implicite de toute la Phase 12.17.

## Sources et chaîne d'autorité

Plan canonique `phase_12_17_07_prioritized_rationalization_plan/09_12_17_8_BATCH_EXECUTION_PLAN.md`, gates 10, registre 02, dispositions 08 et handoff 12 ; décisions 12.17.7A/7B et rebindings B01A/B01B ; handoffs B01-B06 ; preuves 05B/05C ; AGENTS.md et ENVIRONMENT.md. Les chemins de paquets sont relatifs à `docs/development/`.

L'état initial propre comportait 2240 fichiers suivis. Le premier passage B07 a été interrompu préventivement : 14/16 gates, sans commit de clôture. Le snapshot historique `08_MACHINE_EVIDENCE.json` reste inchangé ; il ne constitue pas le résultat final. Le correctif autorisé a ensuite créé la baseline de 2243 fichiers suivis. Le nouveau passage complet, distinct du premier, est documenté en `13_RESUMED_GLOBAL_EVIDENCE.json`.

## Condition de validité du dossier final

Les verdicts de clôture prennent effet uniquement après le commit documentaire local et la vérification de propreté postcommit décrits en 14. Aucun worktree encore staged/untracked n'est présenté comme propre. Le commit porteur du paquet ne contient aucun changement du graphe technique exécuté.
