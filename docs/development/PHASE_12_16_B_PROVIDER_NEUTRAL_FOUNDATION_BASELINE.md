# Phase 12.16-B — Fondation provider-neutral

## 1. Parent A/main

12.16-A est fermé. Le parent documentaire exact est
`7ae02ee109bcc6399ec0f71616da6aef07abda81`, commun à `HEAD`, `main` et
`origin/main` au préflight.

## 2. Branche

Le lot B est construit sur
`phase12/12-16-provider-model-calibration`. Il ne modifie pas `main`.

## 3. ADR

[ADR-P12-058](../../architecture/adr/ADR-P12-058-provider-neutral-calibration-foundation.md)
fixe l'ownership `backend/infrastructure/config`, la séparation profils/secrets,
le routage technique sans autorité et l'approche offline-first.

## 4. Modèle de configuration

`schemas/provider.py` définit des identités opaques de profil/provider/modèle,
une version de configuration, des profils provider et modèle, des routes et un
aggregate `ProviderConfiguration`. Les identités sont non vides, limitées à 128
caractères et utilisent un charset sûr. Aucun enum de fournisseur réel n'existe.

## 5. Boundary secrets

`ProviderCredentialRef` désigne seulement une clé logique. Le resolver
d'environnement consomme un mapping explicitement injecté et ne lit aucun
secret à l'import. `ProviderSecretValue` conserve la valeur derrière
`reveal_for_transport()` ; `repr`, `str`, le resolver et les erreurs ne la
révèlent jamais.

## 6. Limites d'invocation

`ProviderInvocationLimits` sépare max input/output/total tokens, nombre maximal
d'attempts et timeout d'appel. Ces champs ne sont ni `BudgetSpec`, ni
`EvaluationDeadline`, et n'ajoutent aucune retry policy.

## 7. Représentation du coût

`ProviderCostLimit` exprime un plafond exact avec un entier en microunits et un
code devise de trois lettres majuscules. Aucun float, tarif ou pricing table
n'est admis.

## 8. Limites de contexte

`ModelContextLimits` distingue fenêtre technique, input provider maximal et
réserve d'output. Leur somme est bornée par la fenêtre. Aucun champ de contexte
pédagogique n'est réutilisé.

## 9. Routes techniques

`ProviderWorkloadKind` couvre `GENERATION`, `CORRECTION`, `REVIEW` et
`EVALUATION_SCORING`. Il est distinct de `CapabilityId`. Une route référence un
modèle primaire et des fallbacks uniques et compatibles.

## 10. Configuration effective sûre

`EffectiveProviderConfiguration` est une dataclass frozen composée uniquement
de profils activés, de routes validées et de références de credentials. Le
builder trie profils et routes, ce qui rend le snapshot déterministe. Aucun
secret résolu, client, prompt, header ou payload provider ne peut y entrer.

## 11. Loader

`load_provider_configuration()` parse un `Mapping[str, object]` contrôlé avec la
stdlib. Les clés sont strictement allowlistées ; une valeur de credential, un
champ inconnu ou un type invalide produit une erreur fermée. Aucun format
YAML/TOML ni chargement implicite de secret n'est introduit.

## 12. Erreurs

`ProviderConfigurationError` et `ProviderSecretError` exposent seulement des
codes fermés. Les mappings source, valeurs secrètes et exceptions provider ne
sont jamais inclus dans leurs messages.

## 13. Anti-duplication

Le lot réutilise les ports Generation, Review et EvaluationScorer. Il ne crée
aucun second capability registry, budget Recovery, timeout d'évaluation,
catalogue d'observabilité ou retry policy. Les limites provider restent une
configuration d'invocation technique.

## 14. Generation, Review et Scoring

`GENERATION_PORT_CONTRACT_CHANGE = NO`

`REVIEW_PORT_CONTRACT_CHANGE = NO`

`HARNESS_DELTA = 0`

Les métadonnées techniques seront mappées par les futurs adaptateurs outbound ;
aucun scorer concret n'est ajouté en B.

## 15. Semantic et CAP-T04

Le workload embedding, tout embedding port, vector store et adaptateur
sémantique sont différés à 12.16-F. `CAP-T04` reste déclaré sans ToolDescriptor
ni implémentation.

`CAP_T04_DECLARED_ONLY = TRUE`

## 16. Observabilité et Recovery

`OBSERVABILITY_CATALOG_DELTA = 0`

`RECOVERY_POLICY_DELTA = 0`

Les métriques provider, fallback, retry et circuit-breaker spécifiques seront
calibrés en H/I sans anticiper leur policy.

## 17. Dépendances et calibration

`[project].dependencies = []` reste exact. Seules dataclasses, enums, protocols,
regex et collections stdlib sont utilisés.

`CALIBRATION_FOUNDATION_USES_EXISTING_HARNESS_CONTRACTS = TRUE`

Aucun threshold, corpus, répétition ou profil de calibration concurrent n'est
créé.

Validations du lot :

- sélection configuration/régressions : 357 `PASS` en 6,74 s ;
- suite globale : 3 927 `PASS`, 21 skips SQLite conditionnels, en 203,62 s ;
- Python : 3.12.13 ;
- Ruff : PASS ;
- mypy backend : PASS, 642 fichiers ;
- mypy evaluation_harness : PASS, 30 fichiers ;
- compileall backend/evaluation_harness/tests : PASS ;
- `git diff --check` : PASS.

## 18. Handoff C

C pourra produire une matrice de recherche actuelle et construire des
configurations candidates à partir de ces contrats, sans provider préselectionné
et sans modifier l'autorité runtime. Aucun appel réseau ni choix de modèle n'est
commencé dans B.
