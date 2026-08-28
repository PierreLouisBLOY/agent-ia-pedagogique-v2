# ADR-P12-058 — Fondation provider-neutral de configuration et calibration

## Statut

Accepté pour la Phase 12.16-B.

## Contexte

La suite pédagogique canonique 12.15 est fermée sans provider, modèle, SDK ni
réseau. Les ports Generation, Review et EvaluationScorer existent déjà, mais
aucune configuration technique ne permet encore de décrire des profils, leurs
limites ou leur routage sans introduire des objets fournisseur dans les couches
runtime, Application ou Domain.

La résolution future d'un credential doit en outre rester distincte de toute
configuration sérialisable. Les limites d'un appel provider ne doivent pas
détourner le budget Recovery, le timeout du harness ou le contexte pédagogique.

## Décision

1. Les contrats de configuration provider-neutral appartiennent exclusivement
   à `backend/infrastructure/config/`. Les adaptateurs outbound concrets seront
   ajoutés dans des lots ultérieurs.
2. Les identités de profils et codes sont des valeurs opaques, bornées et sans
   enum de fournisseur ou modèle réel.
3. `ProviderWorkloadKind` est un vocabulaire de routage technique distinct de
   `CapabilityId`. Il ne confère ni ownership, permission, gate ou autorité.
4. Les workloads B couvrent génération, correction, review et scoring. Le
   workload embedding reste différé à 12.16-F pour ne pas revendiquer une
   capacité sémantique absente.
5. Les limites d'invocation, la limite monétaire exacte en microunits et les
   limites de fenêtre de contexte sont des types techniques dédiés. Elles ne
   réutilisent ni `BudgetSpec`, ni `EvaluationDeadline`, ni
   `pedagogical_context`.
6. Un profil provider ne contient qu'un code, une référence logique de
   credential et son activation. Un profil modèle contient ses limites et ses
   workloads techniques compatibles.
7. Une route possède un modèle primaire et une chaîne de fallbacks ordonnée.
   B valide cette donnée mais n'implémente aucun retry, switch ou fallback.
8. `ProviderCredentialRef` est une référence sûre. La valeur résolue est
   encapsulée par `ProviderSecretValue`, dont `repr` et `str` sont redacted et
   dont la révélation exige `reveal_for_transport()`.
9. Le resolver d'environnement ne lit rien à l'import : il consomme un mapping
   explicitement injecté et échoue avec des codes fermés sans valeur brute.
10. Le snapshot effectif est immutable, déterministe et ne contient que des
    références de credentials, jamais une valeur résolue, un client, un prompt
    ou un header.
11. Le loader est un parseur stdlib strict d'un mapping contrôlé. Il ne charge
    aucun secret et refuse toute clé inconnue.
12. Les ports Generation, Review et EvaluationScorer, le capability registry,
    Recovery, l'observabilité et le harness restent inchangés.
13. Aucun provider ou modèle n'est sélectionné. La baseline reste offline-first
    et `[project].dependencies` reste vide.

## Conséquences

12.16-C pourra comparer des providers et modèles actuels sans changer les
frontières d'autorité. Les adaptateurs D/E pourront mapper leurs objets SDK vers
les ports existants, et H/I pourront calibrer limites, fallback, recovery et
observabilité à partir de données mesurées. Toute introduction d'un provider
réel, d'un SDK, d'une nouvelle autorité ou d'une valeur secrète dans le snapshot
effectif exige un lot ultérieur explicite et une revue de cette décision.
