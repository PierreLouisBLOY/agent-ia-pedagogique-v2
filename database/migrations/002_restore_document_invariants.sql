-- Phase 12.17.5B corrective migration: restore document invariants lost by 001.
-- Apply only through the migration runner. Never mutate the canonical seed in tests.
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;

CREATE TABLE document__p12_17_05b_new (
    id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL DEFAULT 'OTHER',
    title TEXT NOT NULL,
    file_name TEXT,
    mime_type TEXT,
    publication_date TEXT,
    accessed_at TEXT,
    url TEXT,
    size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
    sha256 TEXT CHECK (
        sha256 IS NULL OR (
            length(sha256) = 64 AND
            sha256 NOT GLOB '*[^0-9A-Fa-f]*'
        )
    ),
    storage_uri TEXT,
    language_code TEXT NOT NULL DEFAULT 'fr',
    license_code TEXT,
    document_status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO document__p12_17_05b_new (
    id, document_type, title, file_name, mime_type, publication_date,
    accessed_at, url, size_bytes, sha256, storage_uri, language_code,
    license_code, document_status, created_at
)
SELECT
    id, document_type, title, file_name, mime_type, publication_date,
    accessed_at, url, size_bytes, sha256, storage_uri, language_code,
    license_code, document_status, created_at
FROM document;

DROP TABLE document;
ALTER TABLE document__p12_17_05b_new RENAME TO document;
CREATE INDEX idx_document_sha256 ON document(sha256);
CREATE INDEX idx_document_url ON document(url);

COMMIT;
PRAGMA foreign_keys = ON;
