# Trace rétrospective — réutilisation du runtime SQLite Phase 7

```text
REVIEW_KIND = RETROSPECTIVE_TRACE
RETROSPECTIVE_DOCUMENTATION = TRUE
RETROACTIVE_APPROVAL = FALSE
PAST_APPROVAL_EVIDENCE = NOT_ASSERTED
SOURCE_PHASE = PHASE_7
RECONCILED_IN = PHASE_12_17_4
```

Cette trace applique désormais la convention de
[`docs/legacy-review`](README.md) et la règle de non-héritage V1 du
[`README.md`](../../README.md). Elle est créée après l'intégration décrite en
Phase 12.15 ; elle ne prouve ni la date, ni l'acteur, ni la décision d'une
approbation contemporaine aux faits.

## Actifs concernés et provenance

Le composant legacy réutilisé est la persistance SQLite Phase 7 du dépôt
historique `agent-ia-pedagogique` :

| Actif | Identité historique | Traitement V2 en Phase 12.15-C0 |
|---|---|---|
| `database/migrations/001_document_sha256_check.sql` | commit `98d8464232f3cea21f7ac911c268b1ad8e675e0d`, blob Git `38b369d73be55f8c90dca62544a64b1277190c14`, SHA-256 `5b4c603d19e9eb195ca1d0d19d5e6755d136d6d13399aeb33c0e90b5bb9b0102` | copie octet-identique sous `database/migrations/` |
| implémentation SQLite historique `backend/persistence_v2.py` | commit `deb751d5b103023d13c8713d9aa663e0e44476e8` | adaptation aux packages outbound, ports et frontières V2 ; aucune dépendance runtime au dépôt historique |
| kit de contrats OP-01 à OP-13 historique | commit `a57b95f06d47677728da5a6f9ecc0b403b118c70` | adaptation aux contrats et gates C0 de V2 |

Le point d'adaptation V2 est le commit C0
`af4a9243e50fd5932698da4023c03a1bd12f525f`. Les faits publiés et leurs
validations restent ceux de la
[baseline C0](../development/PHASE_12_15_C0_SQLITE_RUNTIME_INTEGRATION_BASELINE.md)
et du
[livrable final Phase 12.15](../development/PHASE_12_15_LIVRABLE_COMPLET_CANONIQUE_FINAL.md).
Aucune de ces preuves n'est modifiée par cette trace.

## Connu au moment de l'intégration

Les preuves Phase 12.15 publient déjà :

- le modèle `seed canonique immuable -> copie runtime -> migrations Phase 7` ;
- l'identité exacte de la migration 001 et sa copie octet-identique ;
- l'adaptation de l'implémentation et des contrats aux boundaries V2 ;
- le confinement de SQLite aux adapters/infrastructure ;
- les contrôles seed/runtime, ledger, transaction, rollback et idempotence ;
- l'absence de base runtime, WAL ou SHM suivi dans Git.

Les tests attestés en C0 et dans la clôture 12.15 restent des preuves
historiques liées. B09 ne les rejoue pas et n'annonce aucun nouveau PASS pour
eux.

## Documenté rétrospectivement

L'écart documentaire était l'absence de la revue exigée sous
`docs/legacy-review/`. La présente trace ferme uniquement cet emplacement et
rend explicites la source, la justification, la portée, les risques et la
supersession. Elle ne requalifie pas l'intégration passée en approbation passée.

La justification V2 était de conserver le seed canonique immuable, de créer
une runtime dérivée et d'appliquer les migrations exclusivement à cette copie.
La portée exclut toute source V1 implicite, tout accès direct des agents à SQL,
toute mutation du seed et toute dépendance runtime au dépôt historique.

## Risques, tests et supersession

- Risque principal : confondre copie de la migration et reprise de
  l'architecture historique. La première est octet-identique ; la seconde a été
  adaptée aux owners, ports et packages V2.
- Risque de provenance : les trois commits et les deux hashes ci-dessus sont
  les identités de référence ; aucune origine supplémentaire n'est déduite.
- Tests de référence : gates unitaires, intégration réelle et architecture
  publiées par C0, puis suite canonique 12.15.
- Supersession : les adapters et la composition V2 du commit C0 remplacent
  l'implémentation historique comme runtime actif. La source historique reste
  une preuve, pas une dépendance.

Toute future affirmation sur cette réutilisation doit citer cette trace et les
preuves Phase 12.15 liées. Toute nouvelle réutilisation legacy doit suivre la
[convention préalable](README.md).
