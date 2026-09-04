# Phase 12.17.3D — OD-05/OD-06 schema evidence

## Evidence disposition

```text
OD_05_EVIDENCE_STATUS = PASS_AVAILABLE
OD_06_SCHEMA_EVIDENCE_STATUS = PASS_AVAILABLE
OD_06_DATA_MODEL_ALIGNMENT_IMPLEMENTED = NO
PEDAGOGICAL_ROWS_SELECTED_OR_EXPORTED = 0
```

OD-05's selected read-only evidence mode is satisfied for the authenticated seed. OD-06 now has the physical schema evidence needed for a later rationalization design, but this lot does not perform the separate vocabulary ownership/alignment implementation.

## OD-05 structural observations

- The canonical physical inventory is `98` tables, `20` explicit indexes, `7` triggers and `2` views.
- Full integrity and quick checks return `ok`; the global foreign-key check returns zero violations.
- The core tables required by the evidence contract exist: `notion`, `document`, `resource`, `pedagogical_context`, `session`, `task`, `production`, `validation_event`, `quality_evaluation`, `production_resource_promotion` and `audit_event`.
- Resource lineage/association structures exist, including `resource_version`, `resource_document`, `resource_notion`, `resource_context`, `resource_relation`, `resource_composition` and `production_resource_promotion`.
- `document.sha256` is nullable in the seed and has the explicit lookup index `idx_document_sha256`; the seed DDL does not itself constrain its format to 64 hexadecimal characters.
- `resource.id` is a primary key; `resource_type`, `canonical_title` and `identity_status` are non-null. `identity_status` defaults to `ACTIVE` but has no seed CHECK constraint.
- `session.updated_at` exists and `lifecycle_status` has an enumerated CHECK. Compare-and-set behaviour remains an Application/adapter query invariant rather than a schema constraint.
- Validation, quality, promotion and audit structures contain the required identity, attribution/status and timestamp columns. Several literal fields deliberately have no seed-level vocabulary CHECK.

This evidence records what the schema proves and what it does not prove; it makes no migration or business-authority claim.

## OD-06 literal/default-family observations

| Family | Physical schema evidence | Consequence for later alignment |
|---|---|---|
| Notion | `language_code DEFAULT 'fr'`; `identity_status DEFAULT 'CANONICAL'` with CHECK `CANONICAL/MERGED/DEPRECATED/ARCHIVED` | Adapter values are structurally supported |
| Document | `document_type DEFAULT 'OTHER'`, `language_code DEFAULT 'fr'`, `document_status DEFAULT 'ACTIVE'`; no enum CHECK on type/status | Defaults match; vocabulary ownership must remain outside SQLite |
| Resource | `resource_type` non-null without default/CHECK; `identity_status DEFAULT 'ACTIVE'` without CHECK | Adapter's `OTHER/CANONICAL` values are accepted but not made canonical by the schema |
| Context | `pedagogical_context.notes` is nullable and unconstrained; no dedicated source column/default | Adapter's `runtime` note is technical metadata, not a stored business vocabulary |
| Session | `lifecycle_status DEFAULT 'ACTIVE'` with CHECK `ACTIVE/PAUSED/COMPLETED/ARCHIVED` | Adapter's `ACTIVE` is supported |
| Task | `task_type` is non-null without vocabulary CHECK; `status DEFAULT 'CREATED'` with CHECK including `COMPLETED` | `RUNTIME_CONTRACT` is unconstrained; `COMPLETED` is supported |
| Production | `production_type` is non-null without CHECK; `title` nullable; lifecycle CHECK includes `VALIDATED` | `OTHER` and runtime title remain adapter choices; `VALIDATED` is supported |
| Validation | `validation_type` and `result` are non-null without defaults/CHECK; comment nullable | `RUNTIME_CONTRACT/PASS/sqlite adapter` remain adapter-owned |
| Quality/promotion | Quality `status DEFAULT 'DRAFT'` and unconstrained score; promotion `promotion_status DEFAULT 'PROMOTED'` without CHECK | `COMPLETED/1.0/PROMOTED/runtime contract` are structurally accepted but not schema-owned vocabulary |
| Audit | `event_type` non-null without default/CHECK; reason/payload nullable | `RUNTIME_PORT_CONTRACT/sqlite adapter/{}` remain adapter-owned |

The evidence supports the approved `OD-06 OPTION_A`: vocabularies belong to their bounded Domain/Application contexts, with explicit adapter translation. No schema observation grants business authority to the adapter.
