# Phase 12.17.4 — Architecture provider cible

## Décision de design

L'implémentation active de calibration sera un package offline top-level
`calibration_tooling/`. Elle ne sera ni du runtime produit `backend`, ni un
fichier de production sous `tests`, ni une extension du core provider-neutral
`evaluation_harness`.

Cette nouvelle frontière exige un ADR accepté avant implémentation, car elle
ajoute un package top-level. L'ADR devra prolonger ADR-P12-049 et ADR-P12-058,
sans assouplir leurs interdictions.

## Avant

```text
backend/
  adapters/outbound/openai/                 # transport produit actif
  adapters/outbound/generation/openai/      # GenerationPort actif
  adapters/outbound/review/openai/          # ReviewPort actif
  infrastructure/config/                    # config provider-neutral/secrets
evaluation_harness/                         # core offline provider-neutral
tests/
  providers/anthropic/                      # transport/scorer opérationnels mal placés
  calibration/pedagogical/                  # runners/parsers V4/V5.x historiques
```

## Après proposé

```text
calibration_tooling/
  contracts/
    models.py             # call identity, projection ref, terminal outcome
    policy.py             # blind/strong-only/one-shot/fail-closed/no-threshold
    errors.py             # codes fermés, messages sûrs
  application/
    ports.py              # transport/ledger/clock; réutilise EvaluationScorerPort
    service.py            # orchestration sans SDK ni filesystem implicite
  adapters/
    anthropic/
      contracts.py
      mapping.py
      parser.py
      transport.py
      scorer.py
  runtime/
    configuration.py      # profils injectés et autorisation explicite
    authorization.py      # vérification one-shot et allowlist
    budget.py             # coût/plafond exact, aucun retry implicite
    ledger.py             # effets terminaux/ambigus, hors Git
    runner.py             # seul moteur actif
    composition.py        # seul endroit qui assemble le provider
    cli.py                # point d'entrée actif unique
  observability/
    events.py             # événements techniques bornés
    redaction.py          # aucun prompt, secret, chemin ou thinking content

tests/
  unit/calibration_tooling/
  integration/calibration_tooling/
  architecture/test_calibration_tooling_boundary.py
  calibration/pedagogical/                  # V4/V5.x inchangés
  providers/anthropic/                      # V4/V5.x inchangés
```

Les `__init__.py` ne doivent réexporter que la surface publique minimale. Les
noms ci-dessus sont prévus ; aucun fichier n'est créé dans cette gate.

## OpenAI

OpenAI est déjà correctement matérialisé pour le produit sous
`backend/adapters/outbound/openai`, `generation/openai` et `review/openai`.
12.17.4E ne crée pas de copie OpenAI dans `calibration_tooling` et n'effectue
aucun appel provider. Si un futur besoin de calibration OpenAI est autorisé, un
adapter `calibration_tooling/adapters/openai/` implémentera les ports du tooling
sans importer un runner V4/V5.x ; la réutilisation éventuelle du transport
produit devra être décidée par ADR et injectée par composition.

## Anthropic

Le transport et le scorer historiques ne sont pas déplacés. Les nouveaux
`transport.py` et `scorer.py` sont écrits à partir des contrats durables :

- sortie structurée stricte ;
- blind scoring et sémantique strong-only ;
- adaptive thinking explicite, effort low et borne de sortie configurée quand
  une matrice ultérieure l'autorise ;
- zéro retry implicite ;
- arrêt fail-closed sur état ambigu ;
- aucun contenu de raisonnement conservé ;
- credential révélé uniquement à la frontière transport.

La parité porte sur les invariants, pas sur une copie octet-à-octet du code
historique.

## Ports et direction de dépendance

```text
runtime.cli
  -> runtime.composition
  -> application.service
  -> evaluation_harness.scoring.EvaluationScorerPort
  -> calibration_tooling.application.ports

adapters.anthropic -> application ports + contracts
runtime.configuration -> backend.infrastructure.config (types sûrs uniquement)
backend -X-> calibration_tooling
evaluation_harness -X-> calibration_tooling
calibration_tooling -X-> tests
calibration_tooling -X-> tests.calibration / tests.providers
```

`EvaluationScorerPort` et `ScorerOutcome` restent les contrats publics de
scoring. Les ports nouveaux sont strictement techniques : client transport,
ledger one-shot et horloge. Ils n'accordent aucune permission ou validation
métier.

## Erreurs communes

`contracts/errors.py` définit un enum fermé, par exemple :

```text
CONFIGURATION_INVALID
CREDENTIAL_UNAVAILABLE
AUTHORIZATION_REQUIRED
AUTHORIZATION_CONSUMED
IDENTITY_MISMATCH
TRANSFER_SCOPE_MISMATCH
BUDGET_EXCEEDED
PROVIDER_UNAVAILABLE
RESPONSE_INVALID
LEDGER_AMBIGUOUS
```

Les exceptions publiques ne contiennent que le code. Aucun corps HTTP, header,
request id, prompt, payload pédagogique, secret ou chemin local n'est inclus.
Le narrowing est explicite (`NoReturn` pour les helpers qui lèvent), ce qui
ferme la cause de `MYPY-002` à `MYPY-005` dans le nouveau graphe.

## Télémétrie commune

La télémétrie accepte seulement : `run_ref`, `call_ref`, workload, provider code
opaque, modèle opaque, état, durée, compteurs de tokens, coût borné et code
d'erreur fermé. Elle refuse les contenus, les arguments de requête, les valeurs
de credential et les chemins. Les événements sont injectés vers les sinks
existants ; ils ne sont jamais des faits métier ou des autorisations.

## Secrets et dépendances

- Les valeurs sont résolues au dernier moment via
  `backend.infrastructure.config.secrets.ProviderSecretValue`.
- Aucun accès à l'environnement à l'import.
- Le secret n'entre ni dans un dataclass sérialisable, ni dans le ledger, ni
  dans la télémétrie.
- Aucun SDK Anthropic n'est ajouté sans décision canonique et revue des
  dépendances. Le transport reste construit contre un client injecté jusque-là.
- Aucun provider n'est appelé par la migration architecturale elle-même.

## Tests de frontière requis

1. aucun import de `tests` depuis `backend`, `evaluation_harness` ou
   `calibration_tooling` ;
2. aucun import de `calibration_tooling` depuis `backend` ou
   `evaluation_harness` ;
3. aucun SDK dans les contracts/application ;
4. aucun secret dans repr, str, logs ou artifacts ;
5. retries effectifs égaux à zéro ;
6. état `STARTED` sans résultat terminal traité comme ambigu et bloquant ;
7. une autorisation consommée ne peut pas être réutilisée.
