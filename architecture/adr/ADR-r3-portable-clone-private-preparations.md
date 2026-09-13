# R3 — Portable clone and explicit private attestation

Status: approved bounded correction to 9474f8dbdf493d1bf56fee4ce8743deb424a47c6.

Portable source validation and private preparation attestation are distinct.
All 27 private preparations absent yields NOT_PERFORMED_ABSENT, never an
integrity PASS. Explicit author attestation requires all 27 original exact
files in place. A partial, unreadable, redirected or changed set fails closed.
Tracked/indexed preparations remain forbidden even when absent on disk.
No preparation is copied to a clone or a fixture; tests use synthetic bytes
and an explicitly synthetic reference map, separate from the canonical entry.

Tracked sources, READ_ONLY identities and historical guard predicates remain
mandatory. The portable successor freezes an exact baseline, path/symbol
inventory and normalized source identities. Historical PRE/POST/oracle tables
remain unchanged. Historical AST views are used only after authentication of
the exact successor. Staged bytes are checked independently.

The editorial authentication function pins the successor digest. Only that
single binding value is canonicalized to break the hash cycle; its actual
value is independently checked against the frozen successor identity. A
candidate file or modified manifest cannot declare its own trusted hash.
No runtime behavior, business contract, R2, CAP rule or A16 status changes.
