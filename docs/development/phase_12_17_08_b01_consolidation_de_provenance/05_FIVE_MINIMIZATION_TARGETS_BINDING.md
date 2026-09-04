# Phase 12.17.8-B01 — Binding des minimisations

The historical owner decision remains named `OPTION_A_MINIMIZE_FIVE_AND_CONSOLIDATE_165`. B01A is an explicit corrective rebound; it does not rewrite that historical label.

| ID | Target | PRE SHA-256 | POST SHA-256 | Preserved evidence |
|---|---|---|---|---|
| MIN-01 | `10_DESKTOP_PROJECT_V2_DISCOVERY.md` | `e3209757a7473176fa758c9a3b60313b282007f234e0a5d61ac665a85ba38f7b` | `7b93d46b169856abd40717d8fa264f3232eb7f1572e25d4bf9a7e0fa33edd581` | locator resolution, exact candidate, fail-closed discovery |
| MIN-02 | `12_READ_ONLY_INTEGRITY_EVIDENCE.md` | `72f400f711613a090cd34b7a868ec2b86b0e16d533d86ca557997b3c1a4e8e37` | `523fe9cce71f0b745888f86bd378021868a57f1f0144016db54a81ee0a5865ac` | read-only URI mode and integrity results |
| MIN-03 | `14_IMMUTABILITY_PRE_POST.md` | `c1ae2ff9b34cb8ccc9488a3f41454acfd36f02f958c58c1ba4cd0be784fc7ecd` | `22dbe9ce1996f9a2ae07e5ebe552369a2fd1e73518727bda8950e8c39a5d0b84` | PRE/POST size, time and checksum identity |
| MIN-04 | `16_FINAL_HANDOFF.md` | `774781732408e8486bf8a92aab869a338c39fce95a3e0301dc221a8c50c3c6fb` | `dceb2896fc19f02a862c94eab2fa18550e636e4e6ec18c554ab97b87e7a216c1` | seed authentication, read-only result and gate |
| MIN-05 | `12_FINDINGS_AND_RISKS.json` | `08dc0d8da4dd2e9684cf64e04098674a8ea4234a3b5e84e9e7e7385ed6ba9999` | `abc0bcef43daf9102122f9677b1d68f5780f3b026b35cd30166338c40c7af5b6` | RAT-007 non-portability finding and disposition |
| MIN-06 | `PHYSICAL_EVIDENCE.json` | `aa2acedd0e88c092cbfe02f49a926cf743ab7c1c1fdb1992f664fb284d3f4c13` | `46b4b07679693b6aeb91369c83b6c5c1bdcc33f09ec94e20fcdc42bbb3318206` | all discovery flags, identity, integrity, schema and immutability evidence |

```text
PREVIOUS_MINIMIZATION_TARGETS = 5/5
NEWLY_APPROVED_TARGETS = 1/1
TOTAL_MINIMIZATION_TARGETS = 6/6
MINIMIZATION_TARGETS_ACTUALLY_MODIFIED = 6
PERSONAL_LOCATORS_REMAINING = 0
```

Manifest transitions:

- 12.17.3D: `600a4bee…63b9a` → B01A `cbca0428…a0f5e` → six-target minimization `3ffbd2fb…0bb312` → B01B final `def554827543ad01d9bb45a35c7d72893216a2caff12b8960714ac8726d5aafa`;
- 12.17.4 design: `1aba15a7…c71b5` → final `5807f59131911902a7b8d1d828b25946682fbbdfd5f1dae379def999fb1d570b`.
