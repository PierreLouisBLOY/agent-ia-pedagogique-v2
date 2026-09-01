# Pairwise runner correction

The durable offline compatibility adapter is:

`tests/calibration/pedagogical/pairwise_runner_v5_2_2.py`

It implements the following fail-closed sequence:

1. require a pairwise transfer envelope;
2. validate the unchanged canonical transfer scope;
3. verify the authorized projection SHA-256;
4. read nested `candidate_a` and `candidate_b` objects;
5. extract only opaque candidate IDs and SHA-256 hashes of the projections;
6. never mutate the canonical payload.

Legacy flat payloads are not supported. A nested/flat mixture is rejected as
`AMBIGUOUS_NESTED_AND_FLAT`; malformed nested candidates and projection-hash drift
are also rejected.

The local one-shot runner helper was wired to this adapter for offline compatibility
verification only. No live path was opened.

- New adapter file SHA-256: `ec72fd6d0e8ed7aa3fff0b8d05ce678148041e2be7de8b86478855cbfc57ecf0`
- Corrected helper source SHA-256: `513520a3a7254e86df2dd32d6b89ce48ce0769f17906f6781bf4c540725ab9ef`
- Corrected local runner file SHA-256: `72226acdfe7013166bf8d6c928c3f754f4cc89f0a22a5f3948c120c41f06cbb3`
- Canonical payload mutation: `NONE`
- Provider calls: `0`
