# Phase 12.17.5 — Audit des dix familles de vocabulaire SQLite

```text
SQLITE_VOCABULARY_FAMILIES = 10/10
NONE_REQUIRED = 7
ALREADY_COVERED_BY_001 = 0
REQUIRED_APPROVED = 0
REQUIRED_NOT_APPROVED = 1
UNKNOWN = 2
```

| # | Famille | Owner / représentation | Mapping et preuve SQLite | Default/contrainte | Classification migration | Tests |
|---:|---|---|---|---|---|---|
| 1 | notion | `knowledge_reference` Domain : `KnowledgeLanguageCode`, `NotionIdentityStatus` | `encode/decode_notion`; seed=runtime | `fr`; identité CHECK fermée | `NONE_REQUIRED` | round-trip + unknown |
| 2 | document | `documents_provenance` Domain : type/langue/statut | `encode/decode_document`; DDL runtime altéré par 001 | quatre defaults et CHECK taille perdus; SHA CHECK ajouté | `REQUIRED_NOT_APPROVED` | codec + SHA, préservation incomplète |
| 3 | resource | `resource_library` Domain : type/identité | `encode/decode_resource`; seed=runtime | default `ACTIVE`, insertion possible `CANONICAL` | `UNKNOWN` | deux valeurs distinctes + réel READ-15 |
| 4 | context | `pedagogical_context` Application : `ContextOrigin` | origine validée mais non persistée; seed=runtime | aucune colonne origin, `notes` nullable | `UNKNOWN` | non-écriture dans notes |
| 5 | session | `work_orchestration` Domain : lifecycle | `encode/decode_session`; seed=runtime | default `ACTIVE`, CHECK 4 états | `NONE_REQUIRED` | round-trip exhaustif |
| 6 | task | `work_orchestration` Application : type/objectif/statut | `encode/decode_task`; seed=runtime | default physique `CREATED`, CHECK lifecycle | `NONE_REQUIRED` | round-trip + unknown |
| 7 | production | `transformation_assembly` Domain : type/titre/lifecycle | `encode/decode_production`; seed=runtime | default `DRAFT`, CHECK lifecycle | `NONE_REQUIRED` | round-trip + unknown |
| 8 | validation | `validation_control` Application : type/résultat/validator | `encode/decode_validation`; seed=runtime | champs requis, vocabulaire SQLite permissif | `NONE_REQUIRED` | round-trip + unknown |
| 9 | qualité/promotion | deux owners Domain séparés | `encode/decode_quality`, `encode/decode_promotion`; seed=runtime | score borné dans Domain; promotion default `PROMOTED` | `NONE_REQUIRED` | deux mappings séparés |
| 10 | audit | `audit_traceability` Application : event/actor/payload | `encode/decode_audit`; seed=runtime | payload JSON canonique borné à 4096 octets | `NONE_REQUIRED` | round-trip, canonicalité, borne |

La classification de `document` exprime l'état conservateur actuel : la règle
SHA est bien matérialisée par `001`, mais ses effets collatéraux exigent une
remédiation de migration non approuvée. Elle ne peut donc pas être classée
`ALREADY_COVERED_BY_001` comme si le schéma final était aligné.

Aucune migration n'est créée ou autorisée par cet audit.
