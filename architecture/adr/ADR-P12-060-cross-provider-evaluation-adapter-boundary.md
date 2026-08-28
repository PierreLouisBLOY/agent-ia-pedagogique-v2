# ADR-P12-060 — Frontière d'adaptateur d'évaluation cross-provider

## Statut

Accepté pour la Phase 12.16-E, faits provider vérifiés au 2026-08-28.

## Contexte

ADR-P12-059 sélectionne Anthropic Claude Sonnet 5 comme judge primaire du
workload `EVALUATION_SCORING`, distinct des modèles OpenAI de génération,
correction et review. Le cœur `evaluation_harness` est pourtant une bibliothèque
offline, pure, provider-free et I/O-free. Le backend produit ne doit ni dépendre
du harness ni embarquer le SDK d'un judge de calibration. Les ports 12.14
reçoivent déjà un `scorer_ref` et des `EvaluationObservationValue` bornées ; ces
observations peuvent porter explicitement le critère et la projection à scorer.

Deux décisions durables restaient à formaliser : le propriétaire des
adaptateurs de scorer provider et le statut packaging de leurs SDK.

## Décision

1. Les scorers provider destinés à la calibration vivent sous
   `tests/providers/<provider>/`, hors du backend et hors du cœur
   `evaluation_harness`.
2. Ils implémentent directement l'`EvaluationScorerPort` existant sans modifier
   ce port, `ScorerOutcome`, `NormalizedScore` ou `ScoreStatus`.
3. Ils peuvent importer les value objects du harness et les contrats techniques
   provider-neutral de configuration et de secret du backend. La dépendance
   inverse est interdite : ni le backend ni le harness n'importent
   `tests.providers`.
4. Les SDK nécessaires seulement à la calibration sont déclarés dans un extra
   optionnel `calibration`; ils n'entrent pas dans les dépendances runtime de
   base. Pour E, le runtime reste `openai>=3.5,<4` et l'extra contient
   `anthropic>=1.2,<2`.
5. Le secret réutilise `ProviderCredentialRef`, `ProviderSecretResolver` et
   `ProviderSecretValue`. Aucun type de secret propre au harness ou à Anthropic
   n'est introduit.
6. Le transport Anthropic est privé à l'owner de calibration, utilise le SDK
   officiel avec retry SDK désactivé, timeout configuré, Structured Outputs,
   aucun outil et aucun paramètre de sampling ou thinking non requis.
7. Le scorer supporte uniquement le ref canonique
   `pedagogical-quality-fixture-scorer`; il n'effectue ni routage arbitraire, ni
   fallback OpenAI, ni retry.
8. Les informations propres au critère doivent être explicites dans un
   `ObservationObject` borné. L'absence d'information suffisante produit un
   résultat inconclusif, jamais une modification du port.
9. La sortie provider est post-validée et convertie en rationnel exact. Aucun
   float, metadata provider, coût, prompt, secret ou objet SDK n'entre dans
   `ScorerOutcome`.
10. Un score de calibration ne confère aucune autorité runtime, de validation,
    de gate ou de promotion.

## Conséquences

Le judge Anthropic reste techniquement indépendant du générateur OpenAI sans
polluer le runtime produit. Le harness conserve son algèbre et sa pureté ; les
tests d'intégration peuvent injecter le scorer concret dans le vrai
`ScoreEvaluator`. L'installation des tests provider exige explicitement l'extra
`calibration`, tandis qu'une installation runtime de base n'installe pas
Anthropic.

Les futurs lots G/J devront porter la provenance du judge par la configuration
du run et les artefacts de reporting, sans élargir `ScorerOutcome`. Tout futur
provider de calibration suit le même owner et nécessite une dépendance
optionnelle bornée. Un scorer destiné au runtime métier constituerait une autre
décision architecturale et n'est pas autorisé par cet ADR.
