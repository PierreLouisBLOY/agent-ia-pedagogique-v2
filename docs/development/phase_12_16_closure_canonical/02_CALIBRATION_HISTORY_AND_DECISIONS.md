# Phase 12.16 — Calibration history and decisions

## Decision trail

| Version | Material outcome | Consequence |
| --- | --- | --- |
| V4 | Disposition-first anchor remediation and human reconciliation established the approved strong-only calibration basis. | Provider recalibration preparation became possible; no release threshold was adopted. |
| V4.1 | Corrective offline baseline and Git freeze passed after configuration, matrix, pricing and manifest reconciliation. | A bounded live recalibration baseline was frozen. |
| V4.2 | The repair tranche reused 63 certified results and completed 39 bounded provider calls (`20` OpenAI, `19` Anthropic). | Calibration evidence became complete, while `RELEASE_THRESHOLD = NONE` remained in force. |
| V4.3 | Offline metric analysis documented insufficient strict discrimination, including ties and inversions. | The evidence supported redesigning the scorer instead of adopting a threshold. |
| V5 | An evidence-first semantic scorer contract and integration were implemented offline. The initial live semantic pilot was inconclusive because the response/parser contract was not robust enough. | Parser remediation was required. |
| V5.1 | Parser remediation passed offline; the single micro-canary passed. The five-observation mini-pilot then failed its semantic discrimination gate. | The failure was retained as diagnostic evidence and analyzed rather than hidden or rerun. |
| V5.2 | The mixed-control gate was corrected and the reduced pilot was re-frozen. EOF-only documentary normalization preserved semantic equivalence. The live pilot remained inconclusive at the pairwise runner boundary. | Pairwise execution compatibility required a focused repair. |
| V5.2.2 | The nested pairwise runner fix and technical freeze passed. Live pairwise execution remained inconclusive because of bounded output extraction. | The output contract required widening without changing the semantic target. |
| V5.2.3 | Output-bound compatibility was implemented and frozen. SCN-06 pairwise became reusable as `A_BETTER`; SCN-01 still exceeded the observation locator bound and remained inconclusive. | A final, narrowly scoped contract hardening was justified. |
| V5.2.4 | Comprehensive pairwise observation bounds passed offline and were frozen. The one authorized SCN-01 call returned `A_BETTER`; the four carry-forward observations were not recalled or retransmitted. | `V5_2_4_MINI_PILOT_PASS` and `PHASE_12_16_CLOSURE_READINESS = READY`. |

## Final owner disposition

The canonical Phase 12.16 conclusion is based on the V5.2.4 evidence package, not on retroactive reinterpretation of earlier attempts. Failed and inconclusive runs remain part of the audit trail. They explain the versioned remediations and demonstrate the fail-closed policy.

The closure establishes calibration completion only. It does not adopt a release threshold, authorize further live execution, or initiate Phase 12.17.
