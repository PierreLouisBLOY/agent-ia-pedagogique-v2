# Phase 12.17.8-B01B — EOF normalization PRE/POST

| # | PRE SHA-256 | POST SHA-256 | POST trailing EOL | PRE reconstructed exactly |
|---:|---|---|---:|---|
| 1 | `34062abc…e0d57d` | `f39b2839d8d41774d7ea9c63933d1aeff40e4f3936422c80deb8b65779122713` | 1 | TRUE |
| 2 | `3db40abb…60b2d` | `77e389766f54ccb99d8e4bb2464c1d3c36d3e0e7003e6527ec41f2bab5b0780d` | 1 | TRUE |
| 3 | `94721d30…72d90` | `279e43eec2d852f1d328da5516544ee7da75f9fe379ea4fcea29cf57015d8fff` | 1 | TRUE |
| 4 | `528b38bb…f2d2b` | `2731d68f0d9c3e3abad97e6e0962e391f75e8cdc97136c5728320781c0f42796` | 1 | TRUE |
| 5 | `eba2a999…6ef20` | `c61232e951511794528b8c1fbdac2c7ff2d03b6d8f58f7f0f5181abfab7d29cc` | 1 | TRUE |
| 6 | `1c9edc2f…172d7` | `90ce6484122af4e3c403735bbfead5cd52a515e79909bf428305ca6cc3b891c8` | 1 | TRUE |
| 7 | `a33a77dc…1049c` | `92cd0623228285e5e24f2dabdd149893946e7ee1453dd00ca22488f5655dd866` | 1 | TRUE |
| 8 | `9dab465b…c7f0` | `92159347107209cbd98ed3e5594a85887fd0eb0953f41f46f8807d4ed9742caf` | 1 | TRUE |
| 9 | `6ce0da43…0864` | `939cdffe67541f05f459ea15dfa124e47b18883e42170783aa68caee5e4459da` | 1 | TRUE |
| 10 | `1dcfa10a…2a57` | `a7575dba6abbac1601a0c56a132e3d60310b74c8e3316e080c3d3d9a5bd64e0b` | 1 | TRUE |
| 11 | `a05e59a2…f270` | `a840e06a983415a1948f519acbd34fb68bab781782a26394042a2a712c879a8b` | 1 | TRUE |
| 12 | `06eecd09…c422` | `dd9f91eeb24862dce78ca97c6a025759d22830c0bebfc9665e5724a88fab6f94` | 1 | TRUE |
| 13 | `2a5229b2…fec3` | `924617d4210f838eeb8efaa7c3d569b42288d389050cfc1f32324d195eb5bdaa` | 1 | TRUE |
| 14 | `a31ba45e…b8ef` | `00e0037f0a375e316646fab945cc5ddfddd211390e75e6402643c29ae322e840` | 1 | TRUE |
| 15 | `ca959c41…493f` | `ade83a55fd41def50380c8a1a0445d8851bfa5e3fce807bc8ddefd6021cb0722` | 1 | TRUE |
| 16 | `003d7039…1d70` | `2e49f8887518319935acc9d4ee41211153eaad9953633844f5fa319828ecef34` | 1 | TRUE |
| 17 | `645cf6ac…773e` | `5f3b4fb7b16638fe6f549b850c90c29d7b56740edabe546967e85ada6ed19669` | 1 | TRUE |
| 18 | `483285a8…ade3` | `9ad89672acc88f52df4046ebf465b3c137a05265c90d6709d597ee8e187cff75` | 1 | TRUE |

For every row, appending the single removed EOL sequence reconstructs the exact recorded PRE SHA-256.

```text
EOF_NORMALIZED = 18/18
NON_EOF_CONTENT_CHANGES = 0
```
