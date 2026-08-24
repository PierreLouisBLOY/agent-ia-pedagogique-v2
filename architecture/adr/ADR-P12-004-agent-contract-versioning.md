# ADR P12-004 - Versioning des contrats runtime agentiques

## Statut

Accepte.

## Contexte

P11-CONTRACT-02 exige une version explicite pour chaque contrat canonique et
P11-CONTRACT-20 impose le refus propre d'une version non supportee. C3 a fige la
matrice C-01..C-19 et les modes de metadata DIRECT_META, COMPOSED_META et
NESTED_VALUE, sans encore materialiser la policy de compatibilite.

Les labels de lots `12.3-C1`, `12.3-C2` et `12.3-C3` ne sont pas des versions de
schema wire. La baseline n'a aucune version historique de production a migrer.

## Decision

La baseline canonique des contrats runtime agentiques est `1.0`. Le format de
coeur est strictement `MAJOR.MINOR`. Un segment patch, une pre-release ou une
build metadata ne sont pas introduits sans besoin canonique : ils ajouteraient
des etats et des regles de comparaison sans decision semantique correspondante.

`ContractMeta.schema_version` porte le value object immutable
`ContractSchemaVersion`, jamais une chaine libre. Ce type garantit le format
canonique, refuse toute coercition silencieuse et rend les comparaisons explicites.

Une modification additive non ambigue est compatible dans le meme major si la
policy declare le nouveau minor comme supporte. Une suppression, un renommage ou
un changement semantique exige un major strictement superieur. La version n'est
jamais inferee automatiquement depuis un diff Python.

Une version dont le major est inconnu ou le minor hors plage est rejetee par
`UnsupportedContractVersion` avant tout effet. Il n'existe aucun fallback vers
une autre version.

C-03 `DelegationEnvelope` et C-19 `ErrorEnvelope` restent des valeurs imbriquees
versionnees par leur parent. Elles ne recoivent pas de `ContractMeta` duplique.
C-04 `DelegationResult` est versionne via `agent_result.meta.schema_version`.

Le mecanisme de migration n'execute que des edges explicitement enregistres. La
baseline ne contient aucune migration de production ; son catalogue est vide et
les tests utilisent uniquement une migration factice locale.

La serialisation JSON, Pydantic ou autre reste hors du core. Elle appartiendra a
un boundary ou adaptateur ulterieur, et aucun schema natif provider ne devient
canonique. Le catalogue de versions de D1 ne constitue
ni `AgentRegistry`, ni `CapabilityRegistry`, ni evaluator de permissions de 12.4.

## Consequences

- les 19 familles ont `1.0` comme version courante et seule version supportee ;
- une extension additive future peut ouvrir une plage minor explicitement ;
- tout changement breaking exige une nouvelle version majeure ;
- les contrats imbriques exigent un contexte de version parent explicite ;
- une migration absente ou dupliquee est refusee proprement ;
- les fitness functions figent la matrice, les modes de metadata et les frontieres
  de dependance.
