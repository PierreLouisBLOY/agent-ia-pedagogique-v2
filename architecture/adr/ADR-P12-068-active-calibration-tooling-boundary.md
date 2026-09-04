# ADR-P12-068 — Séparation runtime actif / preuves historiques de calibration

## Statut

Accepté pour la Phase 12.17.4E-B01.

## Contexte

La Phase 12.16 a produit plusieurs générations de runners, parsers, contrats,
matrices et adaptateurs de calibration sous `tests/calibration/pedagogical/` et
`tests/providers/anthropic/`. Quarante fichiers sont maintenant liés à des
manifests, hashes ou gels historiques. Sept de leurs chemins portent déjà une
version ultérieure issue de la remédiation de typing 12.17.2A ; les anciens
hashes restent néanmoins des références historiques non réécrites.

Le backend de production est propre sous mypy (`0/659`), tandis que l'ancienne
traversée import-driven de la calibration rencontre encore 15 diagnostics dans
10 fichiers. `MYPY-001` se trouve dans le transport Anthropic dont les octets
participent aux identités historiques : une correction locale a déjà provoqué
`MATRIX_MISMATCH`.

Le core `evaluation_harness` est provider-neutral selon ADR-P12-049. La
configuration et les secrets provider-neutral restent régis par ADR-P12-058.
La calibration 12.16 est close ; aucun résultat de scorer n'accorde d'autorité
métier et aucun seuil de release n'a été adopté.

## Décision

```text
ACTIVE_RUNTIME != HISTORICAL_CALIBRATION_EVIDENCE
```

1. Les quarante fichiers gelés restent à leur chemin actuel, en lecture seule
   du point de vue des futurs lots de rationalisation. Ils ne sont ni déplacés,
   ni renommés, ni réécrits.
2. Aucun code actif de `backend`, `evaluation_harness` ou du futur tooling de
   calibration n'importe `tests.calibration.pedagogical` ou
   `tests.providers.anthropic`.
3. Aucune implémentation nécessaire au tooling actif ne vit exclusivement sous
   `tests/`.
4. Le tooling actif futur appartient à un package top-level
   `calibration_tooling/`, distinct du runtime produit et du core
   `evaluation_harness`.
5. Le transport/scorer Anthropic actif sera une nouvelle implémentation sous
   `calibration_tooling/adapters/anthropic/`. Les fichiers historiques ne sont
   pas copiés ou modifiés par B01.
6. Les adaptateurs OpenAI de production restent sous
   `backend/adapters/outbound/`. Aucun duplicata OpenAI de calibration n'est
   créé sans une décision ultérieure.
7. La cible de runner/parser actif est une seule génération, avec un point
   d'entrée `calibration_tooling.runtime.cli` et un moteur
   `calibration_tooling.runtime.runner`.
8. `MYPY-001` et les quatorze autres diagnostics sont fermés dans le graphe
   actif par nouvelles frontières et contrats typés. Leurs sources historiques
   ne sont pas modifiées, masquées ou exclues par configuration.
9. L'ancienne traversée mypy historique reste une preuve informative distincte ;
   la gate `import-driven = 0` porte sur le graphe actif.
10. La policy durable conserve blind scoring, strong-only, autorisation
    one-shot/fail-closed, allowlist exacte, zéro retry/rerun, lignée certifiée et
    `RELEASE_THRESHOLD = NONE`.
11. La Phase 12.16 n'est pas réouverte. La rationalisation n'autorise aucun
    appel provider, rerun ou nouvelle conclusion de calibration.

## Direction des dépendances

```text
backend -X-> calibration_tooling
backend -X-> tests
evaluation_harness -X-> calibration_tooling
evaluation_harness -X-> tests
calibration_tooling -> evaluation_harness contracts/ports
calibration_tooling -> configuration/secrets sûrs injectés
calibration_tooling -X-> tests
tests -> backend / evaluation_harness / calibration_tooling
```

Les ports Application/Domain de production restent propriétaires de leurs
autorités. Le tooling ne peut ni valider un contenu métier, ni promouvoir une
production, ni approuver une gate.

## Immutabilité et dérive préexistante

Le freeze B01 enregistre pour chacun des 40 chemins le hash courant de la
baseline `6d0d66380757d7502fd967cd0246c5b6ff91d5f8`. Pour les sept dérives
12.17.2A, il conserve également le hash historique antérieur et le marqueur :

```text
RETROACTIVE_REPAIR = FORBIDDEN
```

Les lots futurs comparent le hash courant gelé. Les manifests historiques ne
sont jamais « corrigés » pour refléter un état plus récent.

## Conséquences

- Une architecture active propre peut être construite sans invalider les
  preuves V4/V5.x.
- Les deux implémentations Anthropic mal placées restent comme preuves ; leur
  remplacement actif sera du nouveau code indépendant.
- La cible mypy active peut atteindre zéro sans ignore, stub de masquage ou
  modification historique.
- Le coût est une nouvelle frontière top-level, des tests d'architecture et une
  période où tooling actif et preuves historiques coexistent volontairement.

## Options écartées

- Modifier directement `tests/providers/anthropic/transport.py` : rejeté,
  invalide les identités historiques.
- Déplacer les fichiers historiques : rejeté, casse chemins, imports et
  manifests de preuve.
- Mettre Anthropic dans `evaluation_harness` : rejeté, viole sa neutralité.
- Mettre le scorer de calibration dans le runtime produit : rejeté, mélange
  évaluation offline et autorité runtime.
- Masquer les diagnostics par configuration mypy ou `.pyi` : rejeté, ne résout
  pas la frontière.

## Portée de B01

B01 accepte cette décision et gèle les hashes. Il ne crée pas le package
`calibration_tooling`, ne change aucun import, ne modifie aucun runtime, n'ouvre
pas SQLite et n'appelle aucun provider. L'implémentation commence uniquement
dans un lot ultérieur explicitement ouvert.
