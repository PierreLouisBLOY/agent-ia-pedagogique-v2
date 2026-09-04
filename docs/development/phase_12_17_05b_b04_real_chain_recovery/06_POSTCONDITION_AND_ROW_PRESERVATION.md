# Phase 12.17.5B-B04 — Postconditions et préservation

| Invariant | Résultat |
|---|---|
| `CHECK (size_bytes IS NULL OR size_bytes >= 0)` | présent; valeur négative rejetée |
| `document_type DEFAULT 'OTHER'` | présent et effectif |
| `language_code DEFAULT 'fr'` | présent et effectif |
| `document_status DEFAULT 'ACTIVE'` | présent et effectif |
| `created_at DEFAULT CURRENT_TIMESTAMP` | présent et effectif |

Le CHECK SHA-256 de `001` est conservé et rejette une valeur invalide. La PK
`document.id`, les index `idx_document_sha256` et `idx_document_url`, l'absence
attendue de trigger `document` et l'absence de FK sortante sont préservés.

```text
FIVE_INVARIANTS = 5/5 PASS
CHECK_SHA256_RETAINED = TRUE
DOCUMENT_COUNT_PRE = 15
DOCUMENT_COUNT_POST = 15
DOCUMENT_IDENTITY_DIGEST_PRE = b5270b322e168d7b8d8e55e977a3cd32a30f4539d49686d86dafb2cf41ff8279
DOCUMENT_IDENTITY_DIGEST_POST = b5270b322e168d7b8d8e55e977a3cd32a30f4539d49686d86dafb2cf41ff8279
ROW_PRESERVATION = PASS
IDENTITY_PRESERVATION = PASS
INTEGRITY_CHECK = ok
QUICK_CHECK = ok
FOREIGN_KEY_VIOLATIONS = 0
```

Les insertions de preuve ont été effectuées dans un savepoint puis annulées.
Seuls les compteurs et un digest des identifiants triés sont consignés; aucun
contenu pédagogique n'a été exporté.
