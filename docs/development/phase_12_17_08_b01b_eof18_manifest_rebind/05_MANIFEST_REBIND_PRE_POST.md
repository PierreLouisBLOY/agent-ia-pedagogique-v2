# Phase 12.17.8-B01B — Manifest rebind PRE/POST

| Manifest | PRE SHA-256 | POST SHA-256 | Entries PRE/POST | Target entries | Non-target entries |
|---|---|---|---|---:|---:|
| 12.17.3 business-rule | `bb48467ad1bc6cdb4e0c768788f537651607c5e25d95dff122bb458b18375b2a` | `be3357f92cf71c6f52725118959e3200428f46e16c9d523f53eb76001d47b5a0` | 12/12 | 1 | 0 |
| 12.17.3D external SQLite evidence | `3ffbd2fb82d2da538f2db1a9ddb04fd8fe944b1db9839652c4db6e3cb30bb312` | `def554827543ad01d9bb45a35c7d72893216a2caff12b8960714ac8726d5aafa` | 8/8 | 3 | 0 |
| 12.17.4E-B01 | `de4903fa9a78d4cbbcc0c792a0d4e46d3805874c686b9e03d75350e694466e8e` | `2bdb3e6caa3624986ac1577104f93a6c39800e94af0369b6154ceb5f66663ad4` | 8/8 | 2 | 0 |
| 12.17.6 security/observability/repo hygiene | `23f6f6ce1cfabbfe7c9aa24ccafdd04a500737a83b0cd0ff6218844b3219049e` | `ff41ed09f507c98fce01b333378b9c51f6696846d5ac930e28823d0a2553f4c7` | 14/14 | 12 | 0 |

Reversing only the 18 authorized target lines reconstructs all four exact PRE manifest hashes.

```text
MANIFEST_COUNT = 4
MANIFEST_TARGET_ENTRIES_CHANGED = 18
NON_TARGET_MANIFEST_ENTRIES_CHANGED = 0
FIFTH_MANIFEST_IMPACT = 0
```
