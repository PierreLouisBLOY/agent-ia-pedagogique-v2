# Politique de versioning des contrats runtime agentiques

## Baseline canonique

Tous les contrats C-01..C-19 utilisent `ContractSchemaVersion(1, 0)`, exporte par
la constante `AGENT_CONTRACT_SCHEMA_V1_0`. Le rendu canonique est `1.0` et le
format accepte est uniquement `MAJOR.MINOR`, sans patch, suffixe, espace ou zero
initial ambigu.

`ContractMeta.schema_version` exige ce value object. Une chaine, meme `"1.0"`,
est refusee : le parsing doit etre explicite a une frontiere ulterieure.

## Compatibilite

La policy baseline accepte exactement `1.0` pour chacune des 19 familles. Une
plage supportee est declaree par major et bornes minor inclusives. P11-CONTRACT-20
est applique sans fallback : major inconnu et minor hors plage produisent
`UnsupportedContractVersion` avant tout effet.

Les changements suivent ces regles :

| Changement | Bump requis | Transition valide |
|---|---|---|
| ajout non ambigu | MINOR | meme major et minor strictement superieur |
| suppression | MAJOR | major strictement superieur |
| renommage | MAJOR | major strictement superieur |
| changement semantique | MAJOR | major strictement superieur |

Le major suivant n'est pas necessairement le major courant plus un. Aucun bump
n'est infere automatiquement depuis le code ou un diff.

## Placement de la version

- DIRECT_META : C-01, C-02, C-05..C-18 lisent `meta.schema_version` ;
- COMPOSED_META : C-04 lit `agent_result.meta.schema_version` ;
- NESTED_VALUE : C-03 et C-19 utilisent la version explicite de leur parent.

C-03 `DelegationEnvelope` et C-19 `ErrorEnvelope` ne sont pas des messages
canoniques versionnes standalone. Leur extraction sans parent leve
`NestedContractVersionContextRequired`. Aucun `ContractMeta` n'est ajoute a ces
valeurs imbriquees.

## Migrations explicites

`MigrationCatalog` accepte seulement des migrations declarees avec famille,
version source, version cible et fonction pure sur un mapping. Un edge duplique
ou absent est refuse. Les entrees et sorties passent par le gel agent-safe.

La baseline ne contient aucune migration de production, car aucune version
historique canonique n'existe. Le harness est valide par une migration factice
definie uniquement dans les tests.

## Frontieres

La serialisation JSON, Pydantic ou autre n'appartient pas au core de versioning.
Elle sera traitee dans un boundary ou adaptateur explicite. Le catalogue
C-01..C-19 decrit des familles contractuelles et leurs versions ; il n'est ni
l'`AgentRegistry`, ni le `CapabilityRegistry`, ni l'evaluator de permissions de
12.4. Il ne contient aucun scheduler, provider, HTTP, ORM ou mecanisme de
persistance.
