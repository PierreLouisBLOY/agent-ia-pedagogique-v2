# V5.2.2 inconclusive closure

Status: `CLOSED_INCONCLUSIVE`.

- Baseline: `f9e50c7b757af5017b9762790930086f45ad954a`
- Absolute carry-forward: Strong `4`, Weak `1`, Mixed `0`
- SCN-06 pairwise: response received, parser `FAIL`
- Safe diagnostic: `$.differences[3].observation`, observed length `191`, accepted maximum `180`
- SCN-01 pairwise: not executed
- Exploitable pairwise results: `0/2`
- Attempted/completed/failed/skipped: `1/0/1/1`
- Retry/rerun: `0/0`
- Historical exact cost: `0.011518 USD`
- Historical live authorization: `CONSUMED`
- Current live authorization: `FALSE`

Safe evidence only:

- ledger: `artifacts/calibration/12.16-g2-v5-2-2-live-pairwise/ledger.json`, SHA-256 `adf0e5b2237ee15debf98407f53d32619518f695154fd377dc678513cb3b7553`
- report: `artifacts/calibration/12.16-g2-v5-2-2-live-pairwise/safe_report.json`, SHA-256 `583d6fa5556bbee06f57e2cb5622fb1f70695b884ea182e67eae1da7ba27b068`

The V5.2.3 test fixture is synthetic. It contains four valid differences and an
exactly 191-character fourth observation. It reproduces the safe diagnostic but
does not reconstruct, read, or persist the historical provider response.

`PAIRWISE_191_CHAR_OBSERVATION_REPRODUCED = TRUE`

Provider calls performed by this remediation: `0`.
