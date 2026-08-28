-- Phase 7 corrective migration: enforce SYNC-001 at DB_IMMEDIATE level.
-- Apply only through the migration runner / backup workflow. Never mutate the canonical DB in tests.
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;

CREATE TABLE document__p7_new (
    id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL,
    title TEXT NOT NULL,
    file_name TEXT,
    mime_type TEXT,
    publication_date TEXT,
    accessed_at TEXT,
    url TEXT,
    size_bytes INTEGER,
    sha256 TEXT CHECK (
        sha256 IS NULL OR (
            length(sha256) = 64 AND
            sha256 NOT GLOB '*[^0-9A-Fa-f]*'
        )
    ),
    storage_uri TEXT,
    language_code TEXT NOT NULL,
    license_code TEXT,
    document_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

INSERT INTO document__p7_new
SELECT id, document_type, title, file_name, mime_type, publication_date, accessed_at,
       url, size_bytes, sha256, storage_uri, language_code, license_code,
       document_status, created_at
FROM document;

DROP TABLE document;
ALTER TABLE document__p7_new RENAME TO document;
CREATE INDEX idx_document_sha256 ON document(sha256);
CREATE INDEX idx_document_url ON document(url);

COMMIT;
PRAGMA foreign_keys = ON;
